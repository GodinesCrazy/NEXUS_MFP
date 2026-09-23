#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MFP-3 Adaptive v1.6.1 — ROBUST TIME MACHINE
=========================================

Objetivo:
- corregir los problemas detectados en v1.5;
- auditar y limpiar anomalías de datos;
- seleccionar estrategias con validación MULTI-AÑO, no con un solo año;
- mantener separación estricta entre pasado y futuro;
- medir regret, sensibilidad a costos y Monte Carlo;
- NO declarar Champion salvo que pase reglas mínimas.

Instrumentos paper:
- QQQ
- ECH
- CPER

Capital base:
- 10.000.000 CLP

IMPORTANTE:
- investigación/paper trading;
- no ejecuta operaciones reales;
- las señales actuales son simuladas.
"""

from __future__ import annotations

import math
import json
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    raise SystemExit(
        "\nFalta yfinance.\n"
        "Ejecuta:\n"
        "  py -m pip install yfinance\n"
        "y vuelve a ejecutar este archivo.\n"
    )

from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score, accuracy_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------------------------

TARGETS = {
    "QQQ": "NASDAQ / tecnología",
    "ECH": "Chile",
    "CPER": "Cobre",
}

PREDICTORS = [
    "SPY", "EEM", "FXI", "HG=F", "GC=F", "CL=F",
    "^VIX", "TLT", "UUP", "CLP=X"
]

FRED_SERIES = {
    "US2Y": "DGS2",
    "US10Y": "DGS10",
    "FEDFUNDS": "DFF",
    "WTI_FRED": "DCOILWTICO",
    "USD_BROAD": "DTWEXBGS",
    # Sólo para CONTROL DE CALIDAD mensual del USD/CLP:
    "CLP_OECD_MONTHLY": "CCUSMA02CLM618N",
}

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"

START_DATE = "2006-01-01"
FIRST_TEST_YEAR = 2017
HORIZONS = [1, 5, 20]
VALIDATION_YEARS = 3

INITIAL_CAPITAL_CLP = 10_000_000
MAX_WEIGHT_PER_ASSET = 0.30
BASE_ONE_WAY_COST = 0.0015   # 0,15%
COST_GRID = [0.0, 0.0005, 0.0015, 0.0030]

MIN_TRAIN_ROWS = 500
RANDOM_STATE = 42

# Umbrales fijos = menos grados de libertad, menor riesgo de overfit.
ML_THRESHOLDS = [0.52, 0.56, 0.60, 0.64]

# Calidad de datos FX
FX_MIN = 300.0
FX_MAX = 2000.0
FX_MAX_DAILY_MOVE = 0.15
FX_MAX_ROLLING_DEVIATION = 0.20

OUTPUT = Path("mfp3_output_v16")

# ---------------------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------------------

def perf(ret: pd.Series) -> dict:
    r = pd.Series(ret).fillna(0.0)
    if len(r) == 0:
        return {
            "total_return": 0.0,
            "cagr": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "ann_vol": 0.0,
            "fitness": -999.0,
        }

    curve = (1.0 + r).cumprod()
    total = float(curve.iloc[-1] - 1.0)
    years = max(len(r) / 252.0, 1 / 252.0)
    cagr = float(curve.iloc[-1] ** (1.0 / years) - 1.0)
    ann_vol = float(r.std() * np.sqrt(252))
    sharpe = float(r.mean() * 252 / ann_vol) if ann_vol > 1e-12 else 0.0
    dd = curve / curve.cummax() - 1.0
    mdd = float(dd.min())

    # Score interno para comparar candidatos.
    fitness = sharpe + 0.35 * total - 0.65 * abs(mdd)

    return {
        "total_return": total,
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": mdd,
        "ann_vol": ann_vol,
        "fitness": float(fitness),
    }

def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)

def feature_block(s: pd.Series, prefix: str) -> pd.DataFrame:
    x = pd.DataFrame(index=s.index)
    daily = s.pct_change(fill_method=None)

    for n in [1, 2, 5, 10, 20, 60]:
        x[f"{prefix}_ret{n}"] = s.pct_change(n, fill_method=None)

    for n in [5, 20, 60]:
        x[f"{prefix}_vol{n}"] = daily.rolling(n).std() * np.sqrt(252)
        x[f"{prefix}_sma{n}"] = s / s.rolling(n).mean() - 1.0

    x[f"{prefix}_rsi14"] = rsi(s, 14) / 100.0
    x[f"{prefix}_dd60"] = s / s.rolling(60).max() - 1.0
    return x

# ---------------------------------------------------------------------
# DESCARGA
# ---------------------------------------------------------------------

def extract_ticker(downloaded: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if isinstance(downloaded.columns, pd.MultiIndex):
        l0 = downloaded.columns.get_level_values(0)
        l1 = downloaded.columns.get_level_values(1)

        if ticker in l0:
            d = downloaded[ticker].copy()
        elif ticker in l1:
            d = downloaded.xs(ticker, axis=1, level=1).copy()
        else:
            raise KeyError(ticker)
    else:
        d = downloaded.copy()

    d.index = pd.to_datetime(d.index).tz_localize(None)
    d.columns = [str(c).title() for c in d.columns]
    return d.sort_index()

def download_market() -> Dict[str, pd.DataFrame]:
    tickers = list(TARGETS) + PREDICTORS
    print("Descargando mercado desde Yahoo Finance...")

    raw = yf.download(
        tickers=tickers,
        start=START_DATE,
        auto_adjust=True,
        progress=False,
        group_by="column",
        threads=True,
    )

    out = {}
    for t in tickers:
        try:
            d = extract_ticker(raw, t)
            if "Close" in d and not d["Close"].dropna().empty:
                out[t] = d
                s = d["Close"].dropna()
                print(
                    f"  {t:8s}: {s.index.min().date()} -> "
                    f"{s.index.max().date()} ({len(s)} filas)"
                )
            else:
                print(f"  ADVERTENCIA: {t} sin Close útil")
        except Exception as e:
            print(f"  ADVERTENCIA {t}: {e}")

    missing = [x for x in TARGETS if x not in out]
    if missing:
        raise SystemExit(f"Faltan objetivos esenciales: {missing}")

    if "CLP=X" not in out:
        raise SystemExit("No se pudo descargar USD/CLP (CLP=X).")

    return out

def download_fred() -> Dict[str, pd.Series]:
    out = {}
    print("\nDescargando FRED...")
    for name, sid in FRED_SERIES.items():
        try:
            df = pd.read_csv(FRED_URL.format(sid=sid))
            dcol, vcol = df.columns[0], df.columns[1]
            df[dcol] = pd.to_datetime(df[dcol])
            df[vcol] = pd.to_numeric(df[vcol], errors="coerce")
            out[name] = df.set_index(dcol)[vcol].sort_index()
            print(f"  {name:18s} {sid}")
        except Exception as e:
            print(f"  ADVERTENCIA {name}: {e}")
    return out

# ---------------------------------------------------------------------
# CONTROL DE CALIDAD
# ---------------------------------------------------------------------

def clean_fx(
    fx: pd.Series,
    fred: Dict[str, pd.Series],
) -> Tuple[pd.Series, pd.DataFrame]:

    s = fx.astype(float).copy().sort_index()
    audit = []

    roll_med = s.rolling(21, min_periods=5).median()
    daily = s.pct_change(fill_method=None)

    bad_level = (s < FX_MIN) | (s > FX_MAX)
    bad_move = daily.abs() > FX_MAX_DAILY_MOVE
    bad_deviation = ((s / roll_med - 1.0).abs() > FX_MAX_ROLLING_DEVIATION)

    bad = bad_level | bad_move | bad_deviation

    for dt in s.index[bad.fillna(False)]:
        audit.append({
            "date": dt,
            "series": "CLP=X",
            "raw_value": s.loc[dt],
            "reason": "|".join([
                x for x, cond in [
                    ("level", bool(bad_level.loc[dt])),
                    ("daily_move", bool(bad_move.loc[dt])),
                    ("rolling_deviation", bool(bad_deviation.loc[dt])),
                ] if cond
            ]),
        })

    cleaned = s.mask(bad).ffill(limit=10)

    # Comparación mensual con OECD/FRED como alarma adicional.
    oecd = fred.get("CLP_OECD_MONTHLY")
    if oecd is not None:
        ym = cleaned.resample("MS").mean()
        o = oecd.reindex(ym.index)
        ratio = ym / o
        mismatch = (ratio - 1.0).abs() > 0.10

        for dt in ym.index[mismatch.fillna(False)]:
            audit.append({
                "date": dt,
                "series": "CLP=X_MONTHLY_CROSSCHECK",
                "raw_value": ym.loc[dt],
                "reason": f"OECD_mismatch; OECD={o.loc[dt]:.4f}",
            })

    audit_df = pd.DataFrame(audit)
    return cleaned, audit_df

def clean_price(
    s: pd.Series,
    ticker: str,
) -> Tuple[pd.Series, pd.DataFrame]:

    x = s.astype(float).copy().sort_index()
    ret = x.pct_change(fill_method=None)

    # ETFs/futuros ajustados no deberían presentar saltos >50% diarios.
    bad = ret.abs() > 0.50
    audit = []

    for dt in x.index[bad.fillna(False)]:
        audit.append({
            "date": dt,
            "series": ticker,
            "raw_value": x.loc[dt],
            "reason": f"daily_return={ret.loc[dt]:.4f}",
        })

    cleaned = x.mask(bad).ffill(limit=5)
    return cleaned, pd.DataFrame(audit)

# ---------------------------------------------------------------------
# FRAME POR ACTIVO
# ---------------------------------------------------------------------

def build_frame(
    asset: str,
    market: Dict[str, pd.DataFrame],
    fred: Dict[str, pd.Series],
    cleaned_fx: pd.Series,
) -> Tuple[pd.DataFrame, List[pd.DataFrame]]:

    audits = []

    usd_raw = market[asset]["Close"].dropna()
    usd, audit_asset = clean_price(usd_raw, asset)
    if not audit_asset.empty:
        audits.append(audit_asset)

    fx = cleaned_fx.reindex(usd.index).ffill(limit=5)

    clp_price = usd * fx
    clp_price.name = "price_clp"

    idx = clp_price.index
    blocks = [
        feature_block(clp_price, "self"),
        feature_block(usd, "usd_asset"),
        feature_block(fx, "usdclp"),
    ]

    for ticker in PREDICTORS:
        if ticker == "CLP=X" or ticker not in market:
            continue

        raw = market[ticker]["Close"].reindex(idx)
        clean, audit_p = clean_price(raw.dropna(), ticker)
        if not audit_p.empty:
            audits.append(audit_p)

        clean = clean.reindex(idx).ffill(limit=5)

        safe = (
            ticker.replace("^", "")
                  .replace("=", "_")
                  .replace("-", "_")
                  .replace(".", "_")
                  .lower()
        )
        blocks.append(feature_block(clean, safe))

    X = pd.concat(blocks, axis=1)

    # Macro de mercado con desfase conservador de 1 día.
    for name, s in fred.items():
        if name == "CLP_OECD_MONTHLY":
            continue

        z = s.reindex(idx).ffill(limit=7).shift(1)
        X[f"{name.lower()}_level"] = z
        X[f"{name.lower()}_chg5"] = z.diff(5)
        X[f"{name.lower()}_chg20"] = z.diff(20)

    if "us10y_level" in X and "us2y_level" in X:
        X["curve_10y_2y"] = X["us10y_level"] - X["us2y_level"]

    X["dow_sin"] = np.sin(2 * np.pi * X.index.dayofweek / 5)
    X["dow_cos"] = np.cos(2 * np.pi * X.index.dayofweek / 5)
    X["month_sin"] = np.sin(2 * np.pi * X.index.month / 12)
    X["month_cos"] = np.cos(2 * np.pi * X.index.month / 12)

    X["price_clp"] = clp_price
    X["price_usd"] = usd
    X["usdclp"] = fx
    X["daily_ret_clp"] = clp_price.pct_change(fill_method=None)

    for h in HORIZONS:
        # señal cierre t -> ejecución cierre t+1 -> h sesiones capturables
        entry = clp_price.shift(-1)
        exit_ = clp_price.shift(-(h + 1))
        fwd = exit_ / entry - 1.0

        X[f"fwd_ret_{h}"] = fwd
        X[f"y_up_{h}"] = np.where(
            fwd.notna(),
            (fwd > 0).astype(float),
            np.nan,
        )

    return X, audits

def feature_columns(df: pd.DataFrame) -> List[str]:
    excluded = {"price_clp", "price_usd", "usdclp", "daily_ret_clp"}
    for h in HORIZONS:
        excluded.add(f"fwd_ret_{h}")
        excluded.add(f"y_up_{h}")
    return [c for c in df.columns if c not in excluded]

# ---------------------------------------------------------------------
# ESTRATEGIAS
# ---------------------------------------------------------------------

def models() -> dict:
    return {
        "LOGIT": Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("sc", StandardScaler()),
            ("m", LogisticRegression(
                C=0.20,
                max_iter=1200,
                class_weight="balanced",
                random_state=RANDOM_STATE,
            )),
        ]),
        "RF": Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("m", RandomForestClassifier(
                n_estimators=100,
                max_depth=5,
                min_samples_leaf=20,
                max_features="sqrt",
                class_weight="balanced_subsample",
                n_jobs=-1,
                random_state=RANDOM_STATE,
            )),
        ]),
        "HGB": Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("m", HistGradientBoostingClassifier(
                max_iter=100,
                learning_rate=0.04,
                max_leaf_nodes=10,
                min_samples_leaf=22,
                l2_regularization=3.0,
                random_state=RANDOM_STATE,
            )),
        ]),
    }

SIMPLE = ["BUYHOLD", "CASH", "MOMENTUM", "MEANREV", "TREND"]

def simple_signal(name: str, df: pd.DataFrame) -> pd.Series:
    if name == "BUYHOLD":
        return pd.Series(1.0, index=df.index)

    if name == "CASH":
        return pd.Series(0.0, index=df.index)

    if name == "MOMENTUM":
        return (
            (df["self_ret20"] > 0)
            & (df["self_sma60"] > 0)
            & (df["self_rsi14"] < 0.80)
        ).astype(float)

    if name == "MEANREV":
        return (
            (df["self_rsi14"] < 0.35)
            & (df["self_ret5"] < 0)
        ).astype(float)

    if name == "TREND":
        return (
            (df["self_sma20"] > 0)
            & (df["self_sma60"] > 0)
            & (df["self_ret20"] > 0)
        ).astype(float)

    raise ValueError(name)

def strategy_components(
    signal: pd.Series,
    daily_ret: pd.Series,
) -> Tuple[pd.Series, pd.Series, pd.Series]:

    sig = signal.astype(float).clip(0, 1)

    # señal t -> ejecución cierre t+1
    exec_pos = sig.shift(1).fillna(0.0)

    # primer retorno capturable: t+1 -> t+2
    held_pos = sig.shift(2).fillna(0.0)

    turnover = exec_pos.diff().abs().fillna(exec_pos.abs())
    gross = held_pos * daily_ret.fillna(0.0)

    return gross, held_pos, turnover

def apply_cost(
    gross: pd.Series,
    turnover: pd.Series,
    one_way_cost: float,
) -> pd.Series:
    return gross - turnover * one_way_cost

# ---------------------------------------------------------------------
# VALIDACIÓN ROBUSTA MULTI-AÑO
# ---------------------------------------------------------------------

@dataclass(frozen=True)
class CandidateKey:
    strategy: str
    horizon: int
    threshold: float

@dataclass
class Selection:
    asset: str
    test_year: int
    strategy: str
    horizon: int
    threshold: float
    robust_score: float
    validation_positive_rate: float
    median_val_return: float
    median_val_sharpe: float
    worst_val_return: float
    worst_val_drawdown: float

def train_ml_before_year(
    df: pd.DataFrame,
    model_name: str,
    h: int,
    year: int,
):
    feats = feature_columns(df)
    first = df.index[df.index.year == year]

    if len(first) == 0:
        return None

    pos = df.index.get_loc(first[0])
    known_end = pos - (h + 1)

    if known_end <= 0:
        return None

    train = df.iloc[:known_end].dropna(
        subset=[f"y_up_{h}", f"fwd_ret_{h}"]
    )

    if len(train) < MIN_TRAIN_ROWS:
        return None

    y = train[f"y_up_{h}"].astype(int)
    if y.nunique() < 2:
        return None

    model = clone(models()[model_name])
    model.fit(train[feats], y)
    return model, train

def eval_simple_year(
    df: pd.DataFrame,
    strategy: str,
    year: int,
    cost: float,
) -> dict:

    z = df[df.index.year == year]
    if z.empty:
        return {}

    sig = simple_signal(strategy, z)
    gross, _, turn = strategy_components(sig, z["daily_ret_clp"])
    net = apply_cost(gross, turn, cost)
    p = perf(net)

    return {
        **p,
        "active_rate": float(sig.mean()),
        "brier": np.nan,
        "auc": np.nan,
        "accuracy": np.nan,
    }

def eval_ml_year(
    df: pd.DataFrame,
    model,
    h: int,
    year: int,
    threshold: float,
    cost: float,
) -> dict:

    z = df[df.index.year == year].copy()
    if z.empty:
        return {}

    feats = feature_columns(df)
    p_up = pd.Series(
        model.predict_proba(z[feats])[:, 1],
        index=z.index,
    )

    sig = (p_up >= threshold).astype(float)
    gross, _, turn = strategy_components(sig, z["daily_ret_clp"])
    net = apply_cost(gross, turn, cost)
    out = perf(net)

    valid = z[f"y_up_{h}"].notna()
    y = z.loc[valid, f"y_up_{h}"].astype(int)
    p = p_up.loc[valid]

    if len(y) and y.nunique() > 1:
        brier = float(brier_score_loss(y, p))
        auc = float(roc_auc_score(y, p))
        acc = float(accuracy_score(y, p >= 0.5))
    else:
        brier = auc = acc = np.nan

    return {
        **out,
        "active_rate": float(sig.mean()),
        "brier": brier,
        "auc": auc,
        "accuracy": acc,
    }

def robust_candidate_table(
    asset: str,
    test_year: int,
    df: pd.DataFrame,
) -> pd.DataFrame:

    val_years = [
        y for y in range(test_year - VALIDATION_YEARS, test_year)
        if np.any(df.index.year == y)
    ]

    if len(val_years) < 2:
        return pd.DataFrame()

    rows = []

    # Estrategias simples.
    for h in HORIZONS:
        for strategy in SIMPLE:
            fold_metrics = []

            for vy in val_years:
                m = eval_simple_year(df, strategy, vy, BASE_ONE_WAY_COST)
                if m:
                    fold_metrics.append((vy, m))

            if len(fold_metrics) < 2:
                continue

            returns = np.array([m["total_return"] for _, m in fold_metrics])
            sharpes = np.array([m["sharpe"] for _, m in fold_metrics])
            mdds = np.array([m["max_drawdown"] for _, m in fold_metrics])

            pos_rate = float(np.mean(returns > 0))
            med_ret = float(np.median(returns))
            med_sh = float(np.median(sharpes))
            worst_ret = float(np.min(returns))
            worst_dd = float(np.min(mdds))
            instability = float(np.std(sharpes))

            robust_score = (
                med_sh
                + 0.35 * med_ret
                - 0.50 * instability
                - 0.50 * abs(worst_dd)
                - 0.35 * max(0.0, -worst_ret)
            )

            rows.append({
                "asset": asset,
                "test_year": test_year,
                "strategy": strategy,
                "horizon": h,
                "threshold": np.nan,
                "robust_score": robust_score,
                "validation_positive_rate": pos_rate,
                "median_val_return": med_ret,
                "median_val_sharpe": med_sh,
                "worst_val_return": worst_ret,
                "worst_val_drawdown": worst_dd,
                "n_folds": len(fold_metrics),
            })

    # ML: cada validación entrena sólo con datos ANTERIORES a esa validación.
    for h in HORIZONS:
        for model_name in models():
            fold_cache = {}

            for vy in val_years:
                trained = train_ml_before_year(df, model_name, h, vy)
                if trained is None:
                    continue
                model, _ = trained
                fold_cache[vy] = model

            for th in ML_THRESHOLDS:
                fold_metrics = []

                for vy, model in fold_cache.items():
                    m = eval_ml_year(
                        df, model, h, vy, th,
                        BASE_ONE_WAY_COST
                    )
                    if m:
                        fold_metrics.append((vy, m))

                if len(fold_metrics) < 2:
                    continue

                returns = np.array([m["total_return"] for _, m in fold_metrics])
                sharpes = np.array([m["sharpe"] for _, m in fold_metrics])
                mdds = np.array([m["max_drawdown"] for _, m in fold_metrics])

                pos_rate = float(np.mean(returns > 0))
                med_ret = float(np.median(returns))
                med_sh = float(np.median(sharpes))
                worst_ret = float(np.min(returns))
                worst_dd = float(np.min(mdds))
                instability = float(np.std(sharpes))

                robust_score = (
                    med_sh
                    + 0.35 * med_ret
                    - 0.50 * instability
                    - 0.50 * abs(worst_dd)
                    - 0.35 * max(0.0, -worst_ret)
                )

                rows.append({
                    "asset": asset,
                    "test_year": test_year,
                    "strategy": model_name,
                    "horizon": h,
                    "threshold": th,
                    "robust_score": robust_score,
                    "validation_positive_rate": pos_rate,
                    "median_val_return": med_ret,
                    "median_val_sharpe": med_sh,
                    "worst_val_return": worst_ret,
                    "worst_val_drawdown": worst_dd,
                    "n_folds": len(fold_metrics),
                })

    return pd.DataFrame(rows)

def select_candidate(
    asset: str,
    test_year: int,
    df: pd.DataFrame,
) -> Tuple[Selection, pd.DataFrame]:

    table = robust_candidate_table(asset, test_year, df)

    fallback = Selection(
        asset=asset,
        test_year=test_year,
        strategy="CASH",
        horizon=5,
        threshold=np.nan,
        robust_score=0.0,
        validation_positive_rate=1.0,
        median_val_return=0.0,
        median_val_sharpe=0.0,
        worst_val_return=0.0,
        worst_val_drawdown=0.0,
    )

    if table.empty:
        return fallback, table

    # Reglas mínimas de estabilidad.
    eligible = table[
        (table["validation_positive_rate"] >= 2/3)
        & (table["median_val_sharpe"] > 0)
        & (table["robust_score"] > 0.05)
    ].copy()

    if eligible.empty:
        return fallback, table

    best = eligible.sort_values(
        ["robust_score", "median_val_sharpe", "median_val_return"],
        ascending=False,
    ).iloc[0]

    sel = Selection(
        asset=asset,
        test_year=test_year,
        strategy=str(best["strategy"]),
        horizon=int(best["horizon"]),
        threshold=(
            float(best["threshold"])
            if pd.notna(best["threshold"]) else np.nan
        ),
        robust_score=float(best["robust_score"]),
        validation_positive_rate=float(best["validation_positive_rate"]),
        median_val_return=float(best["median_val_return"]),
        median_val_sharpe=float(best["median_val_sharpe"]),
        worst_val_return=float(best["worst_val_return"]),
        worst_val_drawdown=float(best["worst_val_drawdown"]),
    )

    return sel, table

# ---------------------------------------------------------------------
# TEST FUTURO
# ---------------------------------------------------------------------

def test_selection(
    sel: Selection,
    df: pd.DataFrame,
) -> Tuple[pd.DataFrame, dict]:

    year = sel.test_year
    z = df[df.index.year == year].copy()

    if z.empty:
        return pd.DataFrame(), {}

    if sel.strategy in SIMPLE:
        sig = simple_signal(sel.strategy, z)
        p_up = pd.Series(np.nan, index=z.index)
    else:
        trained = train_ml_before_year(
            df, sel.strategy, sel.horizon, year
        )

        if trained is None:
            sig = pd.Series(0.0, index=z.index)
            p_up = pd.Series(np.nan, index=z.index)
        else:
            model, _ = trained
            feats = feature_columns(df)
            p_up = pd.Series(
                model.predict_proba(z[feats])[:, 1],
                index=z.index,
            )
            sig = (p_up >= sel.threshold).astype(float)

    gross, held, turnover = strategy_components(
        sig, z["daily_ret_clp"]
    )
    net = apply_cost(gross, turnover, BASE_ONE_WAY_COST)
    pm = perf(net)

    out = pd.DataFrame(index=z.index)
    out["asset"] = sel.asset
    out["year"] = year
    out["strategy"] = sel.strategy
    out["horizon"] = sel.horizon
    out["threshold"] = sel.threshold
    out["signal"] = sig
    out["p_up"] = p_up
    out["gross_asset_ret"] = gross
    out["turnover_asset"] = turnover
    out["net_asset_ret"] = net
    out["position_asset"] = held
    out["daily_ret_clp"] = z["daily_ret_clp"]
    out["price_usd"] = z["price_usd"]
    out["usdclp"] = z["usdclp"]
    out["price_clp"] = z["price_clp"]

    summary = {
        **sel.__dict__,
        "test_return": pm["total_return"],
        "test_sharpe": pm["sharpe"],
        "test_mdd": pm["max_drawdown"],
        "test_ann_vol": pm["ann_vol"],
    }

    return out, summary

# ---------------------------------------------------------------------
# REGRET
# ---------------------------------------------------------------------

def simple_regret_table(
    asset: str,
    year: int,
    df: pd.DataFrame,
    selected_return: float,
) -> dict:

    results = {}

    for s in SIMPLE:
        z = df[df.index.year == year]
        if z.empty:
            continue

        sig = simple_signal(s, z)
        gross, _, turn = strategy_components(sig, z["daily_ret_clp"])
        net = apply_cost(gross, turn, BASE_ONE_WAY_COST)
        results[s] = perf(net)["total_return"]

    oracle_name = max(results, key=results.get)
    oracle_ret = results[oracle_name]

    return {
        "asset": asset,
        "year": year,
        "selected_return": selected_return,
        "best_simple_hindsight": oracle_name,
        "best_simple_hindsight_return": oracle_ret,
        "regret_vs_best_simple": oracle_ret - selected_return,
        "buyhold_return": results.get("BUYHOLD", np.nan),
        "regret_vs_buyhold": results.get("BUYHOLD", np.nan) - selected_return,
    }

# ---------------------------------------------------------------------
# TORNEO
# ---------------------------------------------------------------------

def run_tournament(frames: Dict[str, pd.DataFrame]):
    latest_year = max(x.index.max().year for x in frames.values())
    years = range(FIRST_TEST_YEAR, latest_year + 1)

    all_daily = []
    selections = []
    candidate_tables = []
    regrets = []

    for year in years:
        print("\n" + "=" * 92)
        print(f"TIME MACHINE ROBUSTO -> AÑO FUTURO {year}")
        print("=" * 92)

        for asset, df in frames.items():
            if not np.any(df.index.year == year):
                continue

            print(f"\n{asset}: validando en múltiples años anteriores...")
            sel, table = select_candidate(asset, year, df)

            if not table.empty:
                candidate_tables.append(table)

            print(
                f"  Elegida: {sel.strategy} | H={sel.horizon} | "
                f"score={sel.robust_score:.3f} | "
                f"val+={sel.validation_positive_rate:.0%}"
            )

            daily, summary = test_selection(sel, df)

            if not daily.empty:
                all_daily.append(daily)
                selections.append(summary)

                regrets.append(
                    simple_regret_table(
                        asset,
                        year,
                        df,
                        summary["test_return"],
                    )
                )

                print(
                    f"  FUTURO REAL: {summary['test_return']:+.2%} | "
                    f"Sharpe {summary['test_sharpe']:.2f} | "
                    f"DD {summary['test_mdd']:.2%}"
                )

    return (
        pd.concat(all_daily).sort_index()
        if all_daily else pd.DataFrame(),
        pd.DataFrame(selections),
        pd.concat(candidate_tables, ignore_index=True)
        if candidate_tables else pd.DataFrame(),
        pd.DataFrame(regrets),
    )

# ---------------------------------------------------------------------
# CARTERA
# ---------------------------------------------------------------------

def build_portfolio(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame()

    idx = pd.DatetimeIndex(sorted(daily.index.unique()))
    out = pd.DataFrame(index=idx)

    gross_total = pd.Series(0.0, index=idx)
    turnover_total = pd.Series(0.0, index=idx)

    for asset in TARGETS:
        z = daily[daily["asset"] == asset].copy()

        gross = (
            z["gross_asset_ret"]
            .groupby(z.index)
            .last()
            .reindex(idx)
            .fillna(0.0)
        )

        turnover = (
            z["turnover_asset"]
            .groupby(z.index)
            .last()
            .reindex(idx)
            .fillna(0.0)
        )

        gross_total += MAX_WEIGHT_PER_ASSET * gross
        turnover_total += MAX_WEIGHT_PER_ASSET * turnover

    out["portfolio_gross_ret"] = gross_total
    out["portfolio_turnover"] = turnover_total
    out["portfolio_net_ret"] = (
        gross_total - turnover_total * BASE_ONE_WAY_COST
    )
    out["capital_clp"] = (
        INITIAL_CAPITAL_CLP
        * (1 + out["portfolio_net_ret"]).cumprod()
    )

    return out

def build_benchmark(
    frames: Dict[str, pd.DataFrame],
    index: pd.DatetimeIndex,
) -> pd.Series:

    b = pd.Series(0.0, index=index)

    for asset, df in frames.items():
        r = df["daily_ret_clp"].reindex(index).fillna(0.0)
        b += MAX_WEIGHT_PER_ASSET * r

    return b

# ---------------------------------------------------------------------
# SENSIBILIDAD A COSTOS
# ---------------------------------------------------------------------

def cost_sensitivity(portfolio: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for cost in COST_GRID:
        r = (
            portfolio["portfolio_gross_ret"]
            - portfolio["portfolio_turnover"] * cost
        )

        p = perf(r)
        rows.append({
            "one_way_cost": cost,
            **p,
            "final_capital_clp":
                INITIAL_CAPITAL_CLP * (1 + r).prod(),
        })

    return pd.DataFrame(rows)

# ---------------------------------------------------------------------
# MONTE CARLO BOOTSTRAP
# ---------------------------------------------------------------------

def monte_carlo_monthly(
    ret: pd.Series,
    n_sims: int = 2000,
) -> pd.DataFrame:

    r = ret.copy()
    r.index = pd.to_datetime(r.index)

    monthly = (1 + r).resample("M").prod() - 1
    monthly = monthly.dropna().values

    if len(monthly) < 12:
        return pd.DataFrame()

    rng = np.random.default_rng(RANDOM_STATE)
    finals = []
    mdds = []

    for _ in range(n_sims):
        sample = rng.choice(
            monthly,
            size=len(monthly),
            replace=True,
        )

        curve = INITIAL_CAPITAL_CLP * np.cumprod(1 + sample)
        peak = np.maximum.accumulate(curve)
        dd = curve / peak - 1.0

        finals.append(curve[-1])
        mdds.append(dd.min())

    return pd.DataFrame({
        "final_capital_clp": finals,
        "max_drawdown": mdds,
    })

# ---------------------------------------------------------------------
# CHAMPION RULE
# ---------------------------------------------------------------------

def champion_decision(
    portfolio: pd.DataFrame,
    benchmark: pd.Series,
    selections: pd.DataFrame,
    cost_table: pd.DataFrame,
    unresolved_quality_flags: int,
) -> dict:

    p = perf(portfolio["portfolio_net_ret"])
    b = perf(benchmark)

    annual = (
        portfolio["portfolio_net_ret"]
        .groupby(portfolio.index.year)
        .apply(lambda s: (1 + s).prod() - 1)
    )
    positive_year_rate = float((annual > 0).mean())

    high_cost = cost_table.loc[
        np.isclose(cost_table["one_way_cost"], 0.0030)
    ]

    high_cost_return = (
        float(high_cost.iloc[0]["total_return"])
        if len(high_cost) else -999
    )

    tests = {
        "data_quality_clean":
            unresolved_quality_flags == 0,
        "positive_total_return":
            p["total_return"] > 0,
        "sharpe_at_least_0_60":
            p["sharpe"] >= 0.60,
        "max_drawdown_better_than_-25pct":
            p["max_drawdown"] >= -0.25,
        "positive_year_rate_at_least_60pct":
            positive_year_rate >= 0.60,
        "still_positive_at_double_cost":
            high_cost_return > 0,
        # Puede ser Champion si iguala/mejora Sharpe del benchmark,
        # o si ofrece una reducción material de DD manteniendo >=70% de CAGR.
        "competitive_vs_benchmark":
            (
                p["sharpe"] >= b["sharpe"]
                or (
                    abs(p["max_drawdown"]) <= 0.75 * abs(b["max_drawdown"])
                    and p["cagr"] >= 0.70 * b["cagr"]
                )
            ),
    }

    passed = all(tests.values())

    return {
        "status": "CHAMPION" if passed else "CANDIDATE_NOT_CHAMPION",
        "tests": tests,
        "mfp": p,
        "benchmark": b,
        "positive_year_rate": positive_year_rate,
        "high_cost_total_return": high_cost_return,
    }

# ---------------------------------------------------------------------
# SEÑALES ACTUALES
# ---------------------------------------------------------------------

def current_signals(
    selections: pd.DataFrame,
    daily: pd.DataFrame,
) -> pd.DataFrame:

    if selections.empty or daily.empty:
        return pd.DataFrame()

    latest_year = int(selections["test_year"].max())
    rows = []

    for asset in TARGETS:
        s = selections[
            (selections["asset"] == asset)
            & (selections["test_year"] == latest_year)
        ]

        d = daily[
            (daily["asset"] == asset)
            & (daily["year"] == latest_year)
        ].sort_index()

        if s.empty or d.empty:
            continue

        sel = s.iloc[-1]
        last = d.iloc[-1]
        prev = d.iloc[-2] if len(d) > 1 else last

        sig = float(last["signal"])
        prev_sig = float(prev["signal"])

        if sig > 0 and prev_sig <= 0:
            action = "COMPRAR (paper)"
        elif sig > 0:
            action = "MANTENER (paper)"
        elif prev_sig > 0:
            action = "VENDER / CASH (paper)"
        else:
            action = "CASH / NO OPERAR"

        rows.append({
            "date": d.index[-1],
            "asset": asset,
            "strategy": sel["strategy"],
            "horizon": int(sel["horizon"]),
            "threshold": sel["threshold"],
            "paper_action": action,
            "p_up": last["p_up"],
            "price_usd": last["price_usd"],
            "usdclp": last["usdclp"],
            "price_clp": last["price_clp"],
        })

    return pd.DataFrame(rows)

# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main():
    OUTPUT.mkdir(exist_ok=True)

    market = download_market()
    fred = download_fred()

    # FX audit
    fx_raw = market["CLP=X"]["Close"].dropna()
    fx_clean, fx_audit = clean_fx(fx_raw, fred)

    audits = []
    if not fx_audit.empty:
        audits.append(fx_audit)

    frames = {}
    print("\nConstruyendo frames y auditando datos...")

    for asset in TARGETS:
        df, a = build_frame(
            asset, market, fred, fx_clean
        )
        frames[asset] = df
        audits.extend(a)

        print(
            f"  {asset}: {df.index.min().date()} -> "
            f"{df.index.max().date()} ({len(df)} filas)"
        )

    audit_df = (
        pd.concat(audits, ignore_index=True)
        if audits else
        pd.DataFrame(columns=["date", "series", "raw_value", "reason"])
    )
    audit_df.to_csv(
        OUTPUT / "data_quality_report.csv",
        index=False
    )

    # Tras la limpieza, "unresolved" = sólo cross-check mensual OECD,
    # porque los spikes diarios sí fueron corregidos automáticamente.
    unresolved = int(
        audit_df["series"]
        .astype(str)
        .str.contains("MONTHLY_CROSSCHECK", na=False)
        .sum()
    ) if len(audit_df) else 0

    daily, selections, candidates, regrets = run_tournament(frames)

    daily.to_csv(
        OUTPUT / "time_machine_daily.csv"
    )
    selections.to_csv(
        OUTPUT / "fold_selections.csv",
        index=False
    )
    candidates.to_csv(
        OUTPUT / "validation_candidates.csv",
        index=False
    )
    regrets.to_csv(
        OUTPUT / "regret_analysis.csv",
        index=False
    )

    portfolio = build_portfolio(daily)
    benchmark = build_benchmark(
        frames, portfolio.index
    )

    portfolio["benchmark_ret"] = benchmark
    portfolio["benchmark_capital_clp"] = (
        INITIAL_CAPITAL_CLP
        * (1 + benchmark).cumprod()
    )

    portfolio.to_csv(
        OUTPUT / "portfolio_daily.csv"
    )

    costs = cost_sensitivity(portfolio)
    costs.to_csv(
        OUTPUT / "cost_sensitivity.csv",
        index=False
    )

    mc = monte_carlo_monthly(
        portfolio["portfolio_net_ret"]
    )
    mc.to_csv(
        OUTPUT / "monte_carlo.csv",
        index=False
    )

    metrics = pd.DataFrame([
        {"name": "MFP3_v16_ROBUST", **perf(portfolio["portfolio_net_ret"])},
        {"name": "BENCHMARK_30_30_30_CLP", **perf(benchmark)},
    ])
    metrics.to_csv(
        OUTPUT / "metrics.csv",
        index=False
    )

    sig = current_signals(
        selections, daily
    )
    sig.to_csv(
        OUTPUT / "current_signals.csv",
        index=False
    )

    decision = champion_decision(
        portfolio,
        benchmark,
        selections,
        costs,
        unresolved,
    )

    (OUTPUT / "champion_decision.json").write_text(
        json.dumps(
            decision,
            indent=2,
            ensure_ascii=False,
            default=float,
        ),
        encoding="utf-8",
    )

    # Resumen Monte Carlo
    if len(mc):
        mc_summary = pd.DataFrame([{
            "p05_final_capital":
                np.quantile(mc["final_capital_clp"], 0.05),
            "median_final_capital":
                np.quantile(mc["final_capital_clp"], 0.50),
            "p95_final_capital":
                np.quantile(mc["final_capital_clp"], 0.95),
            "p05_max_drawdown":
                np.quantile(mc["max_drawdown"], 0.05),
            "median_max_drawdown":
                np.quantile(mc["max_drawdown"], 0.50),
        }])
    else:
        mc_summary = pd.DataFrame()

    mc_summary.to_csv(
        OUTPUT / "monte_carlo_summary.csv",
        index=False
    )

    print("\n" + "=" * 92)
    print("RESULTADO MFP-3 v1.6.1 ROBUST TIME MACHINE")
    print("=" * 92)

    with pd.option_context(
        "display.max_columns", None,
        "display.width", 180
    ):
        print(metrics)

    print(
        "\nCapital inicial:",
        f"${INITIAL_CAPITAL_CLP:,.0f} CLP"
    )
    print(
        "Capital final MFP-3:",
        f"${portfolio['capital_clp'].iloc[-1]:,.0f} CLP"
    )
    print(
        "Capital final benchmark:",
        f"${portfolio['benchmark_capital_clp'].iloc[-1]:,.0f} CLP"
    )

    print("\nDECISIÓN:")
    print(decision["status"])
    for k, v in decision["tests"].items():
        print(f"  {'OK' if v else 'FALLA':5s}  {k}")

    print("\nSEÑALES PAPER ACTUALES")
    with pd.option_context(
        "display.max_columns", None,
        "display.width", 180
    ):
        print(sig)

    print("\nREGRET PROMEDIO")
    if len(regrets):
        print(
            "  vs mejor estrategia simple a posteriori:",
            f"{regrets['regret_vs_best_simple'].mean():.2%}"
        )
        print(
            "  vs Buy & Hold:",
            f"{regrets['regret_vs_buyhold'].mean():.2%}"
        )

    print("\nCALIDAD DE DATOS")
    print(
        f"  anomalías/flags registrados: {len(audit_df)}"
    )
    print(
        f"  cross-check mensuales no resueltos: {unresolved}"
    )

    print("\nArchivos creados en:", OUTPUT.resolve())
    print(
        "\nNo conviertas ninguna señal paper en dinero real. "
        "Primero debe pasar todas las pruebas Champion."
    )

if __name__ == "__main__":
    main()
