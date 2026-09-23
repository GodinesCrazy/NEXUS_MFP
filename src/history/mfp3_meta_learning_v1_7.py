#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MFP-3 Adaptive v1.7 — META-LEARNING ENSEMBLE
=============================================

Objetivos principales
---------------------
1. Aprender no sólo "qué activo", sino QUÉ ESTRATEGIA funciona en cada época.
2. Usar información futura de años YA TERMINADOS para entrenar un meta-selector,
   sin permitir que vea el año que está tratando de predecir.
3. Reducir la rotación mediante rebalanceo semanal + histéresis.
4. Dejar de escoger un único ganador: combinar hasta 3 candidatos robustos.
5. Introducir candidatos "core + trend" para evitar perder toda la tendencia alcista.
6. Conservar auditoría walk-forward estricta y capital expresado en CLP.
7. No limpiar eventos reales como saltos del VIX o petróleo negativo.

Paper trading / investigación. No ejecuta operaciones reales.

Dependencias:
    pandas numpy scikit-learn yfinance
"""

from __future__ import annotations

import json
import math
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
        "\nFalta yfinance.\nEjecuta:\n"
        "  py -m pip install yfinance\n"
    )

from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import brier_score_loss, roc_auc_score, accuracy_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------

TARGETS = {
    "QQQ": "NASDAQ/tecnología",
    "ECH": "Chile",
    "CPER": "Cobre",
}

# Se elimina CL=F: el petróleo negativo de 2020 fue real y el pct_change
# alrededor de cero/negativos es una mala feature. Usamos WTI de FRED.
PREDICTORS_POSITIVE = [
    "SPY", "EEM", "FXI", "HG=F", "GC=F",
    "TLT", "UUP", "IWM", "HYG"
]
VIX_TICKER = "^VIX"
FX_TICKER = "CLP=X"

FRED_SERIES = {
    "US2Y": "DGS2",
    "US10Y": "DGS10",
    "FEDFUNDS": "DFF",
    "WTI": "DCOILWTICO",
    "USD_BROAD": "DTWEXBGS",
    "CLP_OECD_MONTHLY": "CCUSMA02CLM618N",
}

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"

START_DATE = "2006-01-01"
FIRST_TEST_YEAR = 2017
VALIDATION_YEARS = 3
HORIZONS = [1, 5, 20]
ML_THRESHOLDS = [0.52, 0.56, 0.60, 0.64]

INITIAL_CAPITAL_CLP = 10_000_000
MAX_WEIGHT_ASSET = 0.30
BASE_ONE_WAY_COST = 0.0015
COST_GRID = [0.0, 0.0005, 0.0015, 0.0030]

REBALANCE_EVERY = 5
HYSTERESIS = 0.08
TOP_K = 3
MIN_TRAIN_ROWS = 500
RANDOM_STATE = 42

OUTPUT = Path("mfp3_output_v17")

# ---------------------------------------------------------------------
# MÉTRICAS
# ---------------------------------------------------------------------

def perf(ret: pd.Series) -> dict:
    r = pd.Series(ret).fillna(0.0)
    if len(r) == 0:
        return {
            "total_return": 0.0, "cagr": 0.0, "sharpe": 0.0,
            "max_drawdown": 0.0, "ann_vol": 0.0, "utility": -999.0
        }

    curve = (1 + r).cumprod()
    total = float(curve.iloc[-1] - 1)
    years = max(len(r) / 252.0, 1 / 252.0)
    cagr = float(curve.iloc[-1] ** (1 / years) - 1)
    vol = float(r.std() * np.sqrt(252))
    sharpe = float(r.mean() * 252 / vol) if vol > 1e-12 else 0.0
    dd = curve / curve.cummax() - 1
    mdd = float(dd.min())

    # Utilidad usada para comparar estrategias históricas.
    utility = sharpe + 0.35 * total - 0.65 * abs(mdd)

    return {
        "total_return": total,
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": mdd,
        "ann_vol": vol,
        "utility": float(utility),
    }

# ---------------------------------------------------------------------
# DATOS
# ---------------------------------------------------------------------

def extract_ticker(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if isinstance(raw.columns, pd.MultiIndex):
        l0 = raw.columns.get_level_values(0)
        l1 = raw.columns.get_level_values(1)
        if ticker in l0:
            d = raw[ticker].copy()
        elif ticker in l1:
            d = raw.xs(ticker, axis=1, level=1).copy()
        else:
            raise KeyError(ticker)
    else:
        d = raw.copy()

    d.index = pd.to_datetime(d.index).tz_localize(None)
    d.columns = [str(c).title() for c in d.columns]
    return d.sort_index()

def download_market() -> Dict[str, pd.DataFrame]:
    tickers = (
        list(TARGETS)
        + PREDICTORS_POSITIVE
        + [VIX_TICKER, FX_TICKER]
    )

    print("Descargando Yahoo Finance...")
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
                    f"  {t:8s} {s.index.min().date()} -> "
                    f"{s.index.max().date()} ({len(s)})"
                )
            else:
                print(f"  ADVERTENCIA: {t} sin datos")
        except Exception as e:
            print(f"  ADVERTENCIA {t}: {e}")

    for t in list(TARGETS) + [FX_TICKER]:
        if t not in out:
            raise SystemExit(f"Falta serie esencial: {t}")

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
# CALIDAD DE DATOS
# ---------------------------------------------------------------------

def clean_fx(
    fx: pd.Series,
    fred: Dict[str, pd.Series],
) -> Tuple[pd.Series, pd.DataFrame]:

    s = fx.astype(float).sort_index().copy()
    med = s.rolling(21, min_periods=5).median()
    r = s.pct_change(fill_method=None)

    # Reglas específicas para CLP/USD. Aquí sí sabemos que 5 CLP/USD es
    # un error de escala y un salto >15% diario es extraordinariamente sospechoso.
    bad = (
        (s < 300)
        | (s > 2000)
        | (r.abs() > 0.15)
        | ((s / med - 1).abs() > 0.20)
    )

    audit = []
    for dt in s.index[bad.fillna(False)]:
        audit.append({
            "date": dt,
            "series": FX_TICKER,
            "raw_value": s.loc[dt],
            "action": "replaced",
            "reason": "FX_scale_or_jump",
        })

    cleaned = s.mask(bad).ffill(limit=10)

    # Control mensual independiente; sólo FLAG, no reemplaza automáticamente.
    oecd = fred.get("CLP_OECD_MONTHLY")
    if oecd is not None:
        m = cleaned.resample("MS").mean()
        ref = oecd.reindex(m.index)
        mismatch = ((m / ref - 1).abs() > 0.10)

        for dt in m.index[mismatch.fillna(False)]:
            audit.append({
                "date": dt,
                "series": "CLP_MONTHLY_CROSSCHECK",
                "raw_value": m.loc[dt],
                "action": "flag_only",
                "reason": f"OECD={ref.loc[dt]}",
            })

    return cleaned, pd.DataFrame(audit)

def clean_positive_price(
    s: pd.Series,
    name: str,
) -> Tuple[pd.Series, pd.DataFrame]:
    """
    Para ETFs/metales que físicamente deben tener precio positivo.
    No elimina saltos grandes: un crash o rally puede ser real.
    """
    x = s.astype(float).sort_index().copy()
    bad = (~np.isfinite(x)) | (x <= 0)

    audit = []
    for dt in x.index[bad.fillna(False)]:
        audit.append({
            "date": dt,
            "series": name,
            "raw_value": x.loc[dt],
            "action": "replaced",
            "reason": "non_positive_or_non_finite",
        })

    return x.mask(bad).ffill(limit=5), pd.DataFrame(audit)

# ---------------------------------------------------------------------
# FEATURES
# ---------------------------------------------------------------------

def rsi(s: pd.Series, n=14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)

def price_features(s: pd.Series, prefix: str) -> pd.DataFrame:
    x = pd.DataFrame(index=s.index)
    daily = s.pct_change(fill_method=None)

    for n in [1, 2, 5, 10, 20, 60, 120]:
        x[f"{prefix}_ret{n}"] = s.pct_change(n, fill_method=None)

    for n in [5, 20, 60]:
        x[f"{prefix}_vol{n}"] = daily.rolling(n).std() * np.sqrt(252)

    for n in [20, 60, 200]:
        x[f"{prefix}_sma{n}"] = s / s.rolling(n).mean() - 1

    x[f"{prefix}_rsi14"] = rsi(s, 14) / 100.0
    x[f"{prefix}_dd60"] = s / s.rolling(60).max() - 1
    x[f"{prefix}_dd252"] = s / s.rolling(252).max() - 1
    return x

def level_features(s: pd.Series, prefix: str) -> pd.DataFrame:
    """
    Para VIX/WTI/rates: evitamos depender sólo de pct_change.
    Permite episodios extremos legítimos y WTI negativo.
    """
    x = pd.DataFrame(index=s.index)
    x[f"{prefix}_level"] = s
    for n in [1, 5, 20]:
        x[f"{prefix}_diff{n}"] = s.diff(n)

    mean20 = s.rolling(20).mean()
    std20 = s.rolling(20).std()
    x[f"{prefix}_z20"] = (s - mean20) / std20.replace(0, np.nan)
    return x

def build_frame(
    asset: str,
    market: Dict[str, pd.DataFrame],
    fred: Dict[str, pd.Series],
    fx_clean: pd.Series,
) -> Tuple[pd.DataFrame, List[pd.DataFrame]]:

    audits = []

    usd, a = clean_positive_price(
        market[asset]["Close"].dropna(), asset
    )
    if len(a):
        audits.append(a)

    fx = fx_clean.reindex(usd.index).ffill(limit=5)
    clp = usd * fx
    idx = clp.index

    blocks = [
        price_features(clp, "self"),
        price_features(usd, "usd_asset"),
        price_features(fx, "usdclp"),
    ]

    for ticker in PREDICTORS_POSITIVE:
        if ticker not in market:
            continue

        s, aa = clean_positive_price(
            market[ticker]["Close"].dropna(), ticker
        )
        if len(aa):
            audits.append(aa)

        s = s.reindex(idx).ffill(limit=5)
        safe = (
            ticker.replace("^", "")
            .replace("=", "_")
            .replace("-", "_")
            .replace(".", "_")
            .lower()
        )
        blocks.append(price_features(s, safe))

    if VIX_TICKER in market:
        # NO limpiar grandes saltos del VIX: son información real.
        vix = (
            market[VIX_TICKER]["Close"]
            .reindex(idx).ffill(limit=5)
        )
        blocks.append(level_features(vix, "vix"))

    X = pd.concat(blocks, axis=1)

    for name, s in fred.items():
        if name == "CLP_OECD_MONTHLY":
            continue

        # Desfase conservador.
        z = s.reindex(idx).ffill(limit=7).shift(1)

        if name in {"WTI", "US2Y", "US10Y", "FEDFUNDS"}:
            lf = level_features(z, name.lower())
            X = X.join(lf)
        else:
            X[f"{name.lower()}_level"] = z
            X[f"{name.lower()}_chg5"] = z.diff(5)
            X[f"{name.lower()}_chg20"] = z.diff(20)

    if "us10y_level" in X and "us2y_level" in X:
        X["curve_10y_2y"] = (
            X["us10y_level"] - X["us2y_level"]
        )

    X["dow_sin"] = np.sin(2 * np.pi * X.index.dayofweek / 5)
    X["dow_cos"] = np.cos(2 * np.pi * X.index.dayofweek / 5)
    X["month_sin"] = np.sin(2 * np.pi * X.index.month / 12)
    X["month_cos"] = np.cos(2 * np.pi * X.index.month / 12)

    X["price_clp"] = clp
    X["price_usd"] = usd
    X["usdclp"] = fx
    X["daily_ret_clp"] = clp.pct_change(fill_method=None)

    for h in HORIZONS:
        entry = clp.shift(-1)
        exit_ = clp.shift(-(h + 1))
        fwd = exit_ / entry - 1

        X[f"fwd_ret_{h}"] = fwd
        X[f"y_up_{h}"] = np.where(
            fwd.notna(), (fwd > 0).astype(float), np.nan
        )

    return X, audits

def feature_columns(df: pd.DataFrame) -> List[str]:
    exclude = {"price_clp", "price_usd", "usdclp", "daily_ret_clp"}
    for h in HORIZONS:
        exclude |= {f"fwd_ret_{h}", f"y_up_{h}"}
    return [c for c in df.columns if c not in exclude]

# ---------------------------------------------------------------------
# POSICIONES / REBALANCEO
# ---------------------------------------------------------------------

def weeklyize(raw: pd.Series) -> pd.Series:
    """
    Sólo permite modificar posición cada ~5 sesiones.
    """
    raw = raw.fillna(0.0).clip(0, 1)
    out = pd.Series(index=raw.index, dtype=float)
    state = 0.0

    for i, (dt, val) in enumerate(raw.items()):
        if i == 0 or i % REBALANCE_EVERY == 0:
            state = float(val)
        out.loc[dt] = state

    return out

def ml_hysteresis_position(
    p: pd.Series,
    enter: float,
) -> pd.Series:

    exit_th = max(0.35, enter - HYSTERESIS)
    out = pd.Series(index=p.index, dtype=float)
    state = 0.0

    for i, (dt, prob) in enumerate(p.items()):
        if i == 0 or i % REBALANCE_EVERY == 0:
            if prob >= enter:
                state = 1.0
            elif prob <= exit_th:
                state = 0.0
            # banda intermedia: mantener estado

        out.loc[dt] = state

    return out

def strategy_components(
    target_position: pd.Series,
    daily_ret: pd.Series,
) -> Tuple[pd.Series, pd.Series, pd.Series]:

    target = target_position.fillna(0.0).clip(0, 1)

    # señal cierre t -> ejecución cierre t+1
    exec_pos = target.shift(1).fillna(0.0)
    # primer retorno capturable t+1 -> t+2
    held = target.shift(2).fillna(0.0)

    turnover = exec_pos.diff().abs().fillna(exec_pos.abs())
    gross = held * daily_ret.fillna(0.0)

    return gross, held, turnover

# ---------------------------------------------------------------------
# ESTRATEGIAS SIMPLES
# ---------------------------------------------------------------------

SIMPLE = [
    "BUYHOLD",
    "CASH",
    "MOMENTUM",
    "MEANREV",
    "TREND60",
    "TREND200_0",
    "TREND200_33",
    "TREND200_50",
    "TREND200_67",
    "VOLTARGET10",
    "VOLTARGET15",
    "VOLTARGET20",
]

def simple_position(name: str, z: pd.DataFrame) -> pd.Series:

    if name == "BUYHOLD":
        return pd.Series(1.0, index=z.index)

    if name == "CASH":
        return pd.Series(0.0, index=z.index)

    if name == "MOMENTUM":
        raw = (
            (z["self_ret20"] > 0)
            & (z["self_sma60"] > 0)
            & (z["self_rsi14"] < 0.80)
        ).astype(float)
        return weeklyize(raw)

    if name == "MEANREV":
        raw = (
            (z["self_rsi14"] < 0.35)
            & (z["self_ret5"] < 0)
        ).astype(float)
        return weeklyize(raw)

    if name == "TREND60":
        raw = (
            (z["self_sma60"] > 0)
            & (z["self_ret20"] > 0)
        ).astype(float)
        return weeklyize(raw)

    if name.startswith("TREND200_"):
        floor_txt = name.split("_")[-1]
        floor = {
            "0": 0.0,
            "33": 0.33,
            "50": 0.50,
            "67": 0.67,
        }[floor_txt]

        raw = pd.Series(
            np.where(z["self_sma200"] > 0, 1.0, floor),
            index=z.index,
        )
        # cuando aún no hay SMA200, usar el floor.
        raw[z["self_sma200"].isna()] = floor
        return weeklyize(raw)

    if name.startswith("VOLTARGET"):
        target = float(name.replace("VOLTARGET", "")) / 100.0
        vol = z["self_vol20"].replace(0, np.nan)
        raw = (target / vol).clip(lower=0.20, upper=1.0)
        return weeklyize(raw.fillna(0.5))

    raise ValueError(name)

# ---------------------------------------------------------------------
# ML
# ---------------------------------------------------------------------

def models():
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
                n_estimators=110,
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
                max_iter=110,
                learning_rate=0.04,
                max_leaf_nodes=10,
                min_samples_leaf=22,
                l2_regularization=3.0,
                random_state=RANDOM_STATE,
            )),
        ]),
    }

@dataclass(frozen=True)
class Candidate:
    strategy: str
    horizon: int = 0
    threshold: float = np.nan

def candidate_universe() -> List[Candidate]:
    c = [Candidate(s, 0, np.nan) for s in SIMPLE]

    for m in models():
        for h in HORIZONS:
            for th in ML_THRESHOLDS:
                c.append(Candidate(m, h, th))

    return c

class ModelCache:
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.cache = {}

    def probabilities(
        self,
        model_name: str,
        h: int,
        year: int,
    ) -> Optional[pd.Series]:

        key = (model_name, h, year)
        if key in self.cache:
            return self.cache[key]

        test = self.df[self.df.index.year == year]
        if test.empty:
            self.cache[key] = None
            return None

        first = test.index[0]
        pos = self.df.index.get_loc(first)
        known_end = pos - (h + 1)

        if known_end <= 0:
            self.cache[key] = None
            return None

        train = self.df.iloc[:known_end].dropna(
            subset=[f"y_up_{h}", f"fwd_ret_{h}"]
        )

        if len(train) < MIN_TRAIN_ROWS:
            self.cache[key] = None
            return None

        y = train[f"y_up_{h}"].astype(int)
        if y.nunique() < 2:
            self.cache[key] = None
            return None

        feats = feature_columns(self.df)
        model = clone(models()[model_name])
        model.fit(train[feats], y)

        p = pd.Series(
            model.predict_proba(test[feats])[:, 1],
            index=test.index,
        )
        self.cache[key] = p
        return p

# ---------------------------------------------------------------------
# CANDIDATE YEAR
# ---------------------------------------------------------------------

def candidate_position_year(
    candidate: Candidate,
    year: int,
    df: pd.DataFrame,
    cache: ModelCache,
) -> Tuple[Optional[pd.Series], Optional[pd.Series]]:

    z = df[df.index.year == year]
    if z.empty:
        return None, None

    if candidate.strategy in SIMPLE:
        return simple_position(candidate.strategy, z), None

    p = cache.probabilities(
        candidate.strategy,
        candidate.horizon,
        year,
    )
    if p is None:
        return None, None

    pos = ml_hysteresis_position(p, candidate.threshold)
    return pos, p

def evaluate_candidate_year(
    candidate: Candidate,
    year: int,
    df: pd.DataFrame,
    cache: ModelCache,
    cost: float = BASE_ONE_WAY_COST,
) -> Optional[dict]:

    z = df[df.index.year == year]
    if z.empty:
        return None

    pos, p = candidate_position_year(
        candidate, year, df, cache
    )
    if pos is None:
        return None

    gross, held, turnover = strategy_components(
        pos, z["daily_ret_clp"]
    )
    net = gross - turnover * cost
    pm = perf(net)

    result = {
        **pm,
        "turnover": float(turnover.sum()),
        "mean_position": float(held.mean()),
        "brier": np.nan,
        "auc": np.nan,
        "accuracy": np.nan,
    }

    if (
        p is not None
        and candidate.horizon in HORIZONS
    ):
        valid = z[f"y_up_{candidate.horizon}"].notna()
        y = z.loc[valid, f"y_up_{candidate.horizon}"].astype(int)
        pp = p.loc[valid]

        if len(y):
            result["brier"] = float(brier_score_loss(y, pp))
            result["accuracy"] = float(accuracy_score(y, pp >= 0.5))
            if y.nunique() > 1:
                result["auc"] = float(roc_auc_score(y, pp))

    return result

# ---------------------------------------------------------------------
# CONTEXTO / REGIME FEATURES
# ---------------------------------------------------------------------

def context_before_year(
    df: pd.DataFrame,
    year: int,
) -> dict:

    hist = df[df.index.year < year]
    if hist.empty:
        return {}

    row = hist.iloc[-1]

    wanted = [
        "self_ret20", "self_ret60", "self_ret120",
        "self_sma60", "self_sma200",
        "self_vol20", "self_dd252",
        "usdclp_ret20",
        "vix_level", "vix_diff5",
        "us2y_level", "us10y_level",
        "curve_10y_2y",
        "wti_level", "wti_diff20",
        "usd_broad_chg20",
    ]

    out = {}
    for c in wanted:
        out[f"ctx_{c}"] = (
            float(row[c]) if c in row and pd.notna(row[c]) else np.nan
        )
    return out

# ---------------------------------------------------------------------
# ROBUST VALIDATION
# ---------------------------------------------------------------------

def validation_table(
    asset: str,
    test_year: int,
    df: pd.DataFrame,
    cache: ModelCache,
) -> pd.DataFrame:

    val_years = [
        y for y in range(test_year - VALIDATION_YEARS, test_year)
        if np.any(df.index.year == y)
    ]

    if len(val_years) < 2:
        return pd.DataFrame()

    ctx = context_before_year(df, test_year)
    rows = []

    for cand in candidate_universe():
        fold = []

        for vy in val_years:
            m = evaluate_candidate_year(cand, vy, df, cache)
            if m is not None:
                fold.append(m)

        if len(fold) < 2:
            continue

        returns = np.array([x["total_return"] for x in fold])
        sharpes = np.array([x["sharpe"] for x in fold])
        dds = np.array([x["max_drawdown"] for x in fold])
        turns = np.array([x["turnover"] for x in fold])

        robust = (
            np.median(sharpes)
            + 0.35 * np.median(returns)
            - 0.50 * np.std(sharpes)
            - 0.50 * abs(np.min(dds))
            - 0.25 * max(0, -np.min(returns))
            - 0.015 * np.median(turns)
        )

        row = {
            "asset": asset,
            "test_year": test_year,
            "strategy": cand.strategy,
            "horizon": cand.horizon,
            "threshold": cand.threshold,
            "robust_score": float(robust),
            "positive_rate": float(np.mean(returns > 0)),
            "median_val_return": float(np.median(returns)),
            "median_val_sharpe": float(np.median(sharpes)),
            "worst_val_return": float(np.min(returns)),
            "worst_val_drawdown": float(np.min(dds)),
            "median_turnover": float(np.median(turns)),
            "n_folds": len(fold),
        }
        row.update(ctx)
        rows.append(row)

    return pd.DataFrame(rows)

# ---------------------------------------------------------------------
# META-LEARNING
# ---------------------------------------------------------------------

META_BASE_COLS = [
    "robust_score", "positive_rate",
    "median_val_return", "median_val_sharpe",
    "worst_val_return", "worst_val_drawdown",
    "median_turnover", "n_folds",
    "horizon", "threshold",
]

def meta_matrix(
    df: pd.DataFrame,
    columns: Optional[List[str]] = None,
) -> Tuple[pd.DataFrame, List[str]]:

    base = [c for c in META_BASE_COLS if c in df.columns]
    ctx = [c for c in df.columns if c.startswith("ctx_")]

    X = df[base + ctx].copy()
    X["threshold"] = X.get("threshold", np.nan).fillna(-1.0)

    dummies = pd.get_dummies(
        df["strategy"].astype(str),
        prefix="strategy",
        dtype=float,
    )

    X = pd.concat([X.reset_index(drop=True), dummies.reset_index(drop=True)], axis=1)
    X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)

    if columns is None:
        columns = list(X.columns)
    else:
        X = X.reindex(columns=columns, fill_value=0.0)

    return X, columns

def meta_is_useful(
    history: pd.DataFrame,
) -> Tuple[bool, dict]:

    if history.empty or history["realized_year"].nunique() < 3:
        return False, {"reason": "historia insuficiente"}

    years = sorted(history["realized_year"].unique())
    meta_utilities = []
    robust_utilities = []

    for y in years[2:]:
        train = history[history["realized_year"] < y]
        test = history[history["realized_year"] == y]

        if len(train) < 20 or test.empty:
            continue

        Xtr, cols = meta_matrix(train)
        Xte, _ = meta_matrix(test, cols)

        pipe = Pipeline([
            ("sc", StandardScaler()),
            ("ridge", Ridge(alpha=10.0)),
        ])
        pipe.fit(Xtr, train["future_utility"])
        pred = pipe.predict(Xte)

        meta_idx = int(np.argmax(pred))
        robust_idx = int(np.argmax(test["robust_score"].values))

        meta_utilities.append(
            float(test.iloc[meta_idx]["future_utility"])
        )
        robust_utilities.append(
            float(test.iloc[robust_idx]["future_utility"])
        )

    if len(meta_utilities) < 2:
        return False, {"reason": "pocas pruebas meta"}

    delta = float(
        np.mean(meta_utilities) - np.mean(robust_utilities)
    )

    useful = (
        np.mean(meta_utilities) > 0
        and delta > 0
    )

    return useful, {
        "meta_backtest_mean_utility": float(np.mean(meta_utilities)),
        "robust_backtest_mean_utility": float(np.mean(robust_utilities)),
        "meta_advantage": delta,
        "n_meta_folds": len(meta_utilities),
    }

def score_current_candidates(
    table: pd.DataFrame,
    history: pd.DataFrame,
) -> Tuple[pd.DataFrame, dict]:

    t = table.copy()

    # Filtrado mínimo.
    t["eligible"] = (
        (t["positive_rate"] >= 2/3)
        & (t["median_val_sharpe"] > 0)
        & (t["robust_score"] > 0)
    )

    useful, audit = meta_is_useful(history)

    t["meta_pred"] = np.nan
    t["final_score"] = t["robust_score"]

    if useful and len(history) >= 20:
        Xtr, cols = meta_matrix(history)
        Xte, _ = meta_matrix(t, cols)

        model = Pipeline([
            ("sc", StandardScaler()),
            ("ridge", Ridge(alpha=10.0)),
        ])
        model.fit(Xtr, history["future_utility"])
        pred = model.predict(Xte)
        t["meta_pred"] = pred

        # Mezcla por percentiles para evitar que una escala domine.
        r1 = t["robust_score"].rank(pct=True)
        r2 = pd.Series(pred, index=t.index).rank(pct=True)
        t["final_score"] = 0.50 * r1 + 0.50 * r2

    audit["meta_used"] = bool(useful)
    return t, audit

# ---------------------------------------------------------------------
# ENSEMBLE TOP-K
# ---------------------------------------------------------------------

def choose_top(
    scored: pd.DataFrame,
) -> pd.DataFrame:

    e = scored[scored["eligible"]].copy()

    if e.empty:
        cash = scored[scored["strategy"] == "CASH"].copy()
        if len(cash):
            cash["ensemble_weight"] = 1.0
            return cash.head(1)

        return pd.DataFrame([{
            "strategy": "CASH", "horizon": 0,
            "threshold": np.nan, "final_score": 0.0,
            "ensemble_weight": 1.0,
        }])

    top = e.sort_values(
        ["final_score", "robust_score"],
        ascending=False,
    ).head(TOP_K).copy()

    s = top["final_score"].values.astype(float)
    s = s - np.max(s)
    w = np.exp(s / 0.25)
    w = w / w.sum()

    top["ensemble_weight"] = w
    return top

def candidate_from_row(row) -> Candidate:
    return Candidate(
        strategy=str(row["strategy"]),
        horizon=int(row["horizon"]),
        threshold=(
            float(row["threshold"])
            if pd.notna(row["threshold"])
            else np.nan
        ),
    )

def ensemble_year(
    top: pd.DataFrame,
    year: int,
    df: pd.DataFrame,
    cache: ModelCache,
) -> Tuple[pd.DataFrame, dict]:

    z = df[df.index.year == year]
    if z.empty:
        return pd.DataFrame(), {}

    target = pd.Series(0.0, index=z.index)
    probability = pd.Series(0.0, index=z.index)
    probability_weight = 0.0
    members = []

    for _, row in top.iterrows():
        cand = candidate_from_row(row)
        weight = float(row["ensemble_weight"])

        pos, p = candidate_position_year(
            cand, year, df, cache
        )
        if pos is None:
            continue

        target += weight * pos

        if p is not None:
            probability += weight * p
            probability_weight += weight

        members.append({
            "strategy": cand.strategy,
            "horizon": cand.horizon,
            "threshold": cand.threshold,
            "weight": weight,
        })

    if probability_weight > 0:
        probability = probability / probability_weight
    else:
        probability[:] = np.nan

    gross, held, turnover = strategy_components(
        target, z["daily_ret_clp"]
    )
    net = gross - turnover * BASE_ONE_WAY_COST
    pm = perf(net)

    out = pd.DataFrame(index=z.index)
    out["year"] = year
    out["target_position"] = target
    out["position_asset"] = held
    out["turnover_asset"] = turnover
    out["gross_asset_ret"] = gross
    out["net_asset_ret"] = net
    out["ensemble_p_up"] = probability
    out["daily_ret_clp"] = z["daily_ret_clp"]
    out["price_usd"] = z["price_usd"]
    out["usdclp"] = z["usdclp"]
    out["price_clp"] = z["price_clp"]

    summary = {
        **pm,
        "members_json": json.dumps(members),
        "mean_position": float(held.mean()),
        "turnover": float(turnover.sum()),
    }

    return out, summary

# ---------------------------------------------------------------------
# FUTURE OUTCOMES FOR META LEARNING
# ---------------------------------------------------------------------

def future_candidate_outcomes(
    validation: pd.DataFrame,
    year: int,
    df: pd.DataFrame,
    cache: ModelCache,
) -> pd.DataFrame:

    rows = []

    for _, r in validation.iterrows():
        cand = candidate_from_row(r)
        m = evaluate_candidate_year(
            cand, year, df, cache
        )
        if m is None:
            continue

        row = r.to_dict()
        row["realized_year"] = year
        row["future_return"] = m["total_return"]
        row["future_sharpe"] = m["sharpe"]
        row["future_drawdown"] = m["max_drawdown"]
        row["future_turnover"] = m["turnover"]
        row["future_utility"] = m["utility"]
        rows.append(row)

    return pd.DataFrame(rows)

# ---------------------------------------------------------------------
# TOURNAMENT
# ---------------------------------------------------------------------

def run_asset(
    asset: str,
    df: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:

    cache = ModelCache(df)

    all_daily = []
    selections = []
    candidate_audit = []
    meta_history = pd.DataFrame()
    meta_audit_rows = []

    latest_year = int(df.index.max().year)

    for year in range(FIRST_TEST_YEAR, latest_year + 1):
        if not np.any(df.index.year == year):
            continue

        print(f"\n{asset} — futuro {year}")

        vt = validation_table(asset, year, df, cache)
        if vt.empty:
            continue

        scored, meta_audit = score_current_candidates(
            vt, meta_history
        )
        top = choose_top(scored)

        daily_y, summary = ensemble_year(
            top, year, df, cache
        )
        if daily_y.empty:
            continue

        daily_y["asset"] = asset
        all_daily.append(daily_y)

        top_desc = " + ".join(
            f"{r.strategy}:{r.ensemble_weight:.2f}"
            for r in top.itertuples()
        )

        summary_row = {
            "asset": asset,
            "test_year": year,
            "ensemble": top_desc,
            **summary,
        }
        selections.append(summary_row)

        scored["selected_topk"] = False
        scored.loc[top.index.intersection(scored.index), "selected_topk"] = True
        scored["asset"] = asset
        scored["test_year"] = year
        candidate_audit.append(scored)

        meta_audit_rows.append({
            "asset": asset,
            "test_year": year,
            **meta_audit,
        })

        print(
            f"  Ensemble: {top_desc}\n"
            f"  FUTURO REAL: {summary['total_return']:+.2%} | "
            f"Sharpe {summary['sharpe']:.2f} | "
            f"DD {summary['max_drawdown']:.2%} | "
            f"turnover {summary['turnover']:.1f}"
        )

        # Sólo DESPUÉS de observar el año terminado, sus resultados
        # pueden entrar al meta-learning del año siguiente.
        realized = future_candidate_outcomes(
            vt, year, df, cache
        )

        if not realized.empty:
            meta_history = pd.concat(
                [meta_history, realized],
                ignore_index=True,
            )

    return (
        pd.concat(all_daily).sort_index()
        if all_daily else pd.DataFrame(),
        pd.DataFrame(selections),
        pd.concat(candidate_audit, ignore_index=True)
        if candidate_audit else pd.DataFrame(),
        pd.DataFrame(meta_audit_rows),
    )

# ---------------------------------------------------------------------
# PORTFOLIO
# ---------------------------------------------------------------------

def build_portfolio(
    daily_all: pd.DataFrame,
    frames: Dict[str, pd.DataFrame],
) -> pd.DataFrame:

    idx = pd.DatetimeIndex(
        sorted(daily_all.index.unique())
    )

    gross = pd.Series(0.0, index=idx)
    turnover = pd.Series(0.0, index=idx)

    for asset in TARGETS:
        z = daily_all[daily_all["asset"] == asset]

        g = (
            z["gross_asset_ret"]
            .groupby(z.index).last()
            .reindex(idx).fillna(0)
        )

        t = (
            z["turnover_asset"]
            .groupby(z.index).last()
            .reindex(idx).fillna(0)
        )

        gross += MAX_WEIGHT_ASSET * g
        turnover += MAX_WEIGHT_ASSET * t

    net = gross - turnover * BASE_ONE_WAY_COST

    out = pd.DataFrame(index=idx)
    out["portfolio_gross_ret"] = gross
    out["portfolio_turnover"] = turnover
    out["portfolio_net_ret"] = net
    out["capital_clp"] = (
        INITIAL_CAPITAL_CLP * (1 + net).cumprod()
    )

    # 30/30/30 buy & hold
    bench = pd.Series(0.0, index=idx)
    for asset, df in frames.items():
        bench += (
            MAX_WEIGHT_ASSET
            * df["daily_ret_clp"].reindex(idx).fillna(0)
        )

    out["benchmark_ret"] = bench
    out["benchmark_capital_clp"] = (
        INITIAL_CAPITAL_CLP * (1 + bench).cumprod()
    )

    return out

# ---------------------------------------------------------------------
# COST + MONTE CARLO
# ---------------------------------------------------------------------

def cost_sensitivity(port: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for cost in COST_GRID:
        r = (
            port["portfolio_gross_ret"]
            - port["portfolio_turnover"] * cost
        )
        m = perf(r)
        rows.append({
            "one_way_cost": cost,
            **m,
            "final_capital_clp":
                INITIAL_CAPITAL_CLP * (1 + r).prod(),
        })

    return pd.DataFrame(rows)

def monte_carlo(ret: pd.Series, n=2000) -> pd.DataFrame:
    r = ret.copy()
    r.index = pd.to_datetime(r.index)

    monthly = (1 + r).resample("M").prod() - 1
    vals = monthly.dropna().values

    if len(vals) < 12:
        return pd.DataFrame()

    rng = np.random.default_rng(RANDOM_STATE)
    rows = []

    for _ in range(n):
        sample = rng.choice(vals, len(vals), replace=True)
        curve = INITIAL_CAPITAL_CLP * np.cumprod(1 + sample)
        dd = curve / np.maximum.accumulate(curve) - 1
        rows.append({
            "final_capital_clp": curve[-1],
            "max_drawdown": dd.min(),
        })

    return pd.DataFrame(rows)

# ---------------------------------------------------------------------
# CURRENT PAPER SIGNALS
# ---------------------------------------------------------------------

def current_signals(
    daily: pd.DataFrame,
    selections: pd.DataFrame,
) -> pd.DataFrame:

    rows = []

    for asset in TARGETS:
        z = daily[daily["asset"] == asset].sort_index()
        if z.empty:
            continue

        latest_year = int(z["year"].max())
        zz = z[z["year"] == latest_year]
        last = zz.iloc[-1]

        sel = selections[
            (selections["asset"] == asset)
            & (selections["test_year"] == latest_year)
        ]

        position_fraction = float(last["target_position"])
        desired_portfolio_weight = (
            MAX_WEIGHT_ASSET * position_fraction
        )

        if desired_portfolio_weight >= 0.25:
            action = "ALTA EXPOSICIÓN (paper)"
        elif desired_portfolio_weight >= 0.10:
            action = "EXPOSICIÓN PARCIAL (paper)"
        elif desired_portfolio_weight > 0:
            action = "EXPOSICIÓN BAJA (paper)"
        else:
            action = "CASH / NO OPERAR"

        rows.append({
            "date": zz.index[-1],
            "asset": asset,
            "ensemble": (
                sel.iloc[-1]["ensemble"]
                if len(sel) else ""
            ),
            "paper_action": action,
            "target_portfolio_weight":
                desired_portfolio_weight,
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

    fx_clean, fx_audit = clean_fx(
        market[FX_TICKER]["Close"].dropna(),
        fred,
    )

    audits = []
    if len(fx_audit):
        audits.append(fx_audit)

    frames = {}
    for asset in TARGETS:
        df, aa = build_frame(
            asset, market, fred, fx_clean
        )
        frames[asset] = df
        audits.extend(aa)

    quality = (
        pd.concat(audits, ignore_index=True)
        if audits else
        pd.DataFrame(
            columns=["date", "series", "raw_value", "action", "reason"]
        )
    )
    quality.to_csv(
        OUTPUT / "data_quality_report.csv",
        index=False
    )

    all_daily = []
    all_sel = []
    all_candidates = []
    all_meta_audit = []

    for asset, df in frames.items():
        print("\n" + "=" * 90)
        print("META TIME MACHINE:", asset)
        print("=" * 90)

        d, s, c, ma = run_asset(asset, df)

        if len(d):
            all_daily.append(d)
        if len(s):
            all_sel.append(s)
        if len(c):
            all_candidates.append(c)
        if len(ma):
            all_meta_audit.append(ma)

    daily = pd.concat(all_daily).sort_index()
    selections = pd.concat(all_sel, ignore_index=True)
    candidates = pd.concat(all_candidates, ignore_index=True)
    meta_audit = pd.concat(all_meta_audit, ignore_index=True)

    daily.to_csv(
        OUTPUT / "time_machine_daily.csv"
    )
    selections.to_csv(
        OUTPUT / "yearly_ensembles.csv",
        index=False
    )
    candidates.to_csv(
        OUTPUT / "candidate_audit.csv",
        index=False
    )
    meta_audit.to_csv(
        OUTPUT / "meta_audit.csv",
        index=False
    )

    portfolio = build_portfolio(
        daily, frames
    )
    portfolio.to_csv(
        OUTPUT / "portfolio_daily.csv"
    )

    costs = cost_sensitivity(portfolio)
    costs.to_csv(
        OUTPUT / "cost_sensitivity.csv",
        index=False
    )

    mc = monte_carlo(
        portfolio["portfolio_net_ret"]
    )
    mc.to_csv(
        OUTPUT / "monte_carlo.csv",
        index=False
    )

    metrics = pd.DataFrame([
        {
            "name": "MFP3_v17_META_ENSEMBLE",
            **perf(portfolio["portfolio_net_ret"]),
        },
        {
            "name": "BENCHMARK_30_30_30_CLP",
            **perf(portfolio["benchmark_ret"]),
        },
    ])
    metrics.to_csv(
        OUTPUT / "metrics.csv",
        index=False
    )

    sig = current_signals(
        daily, selections
    )
    sig.to_csv(
        OUTPUT / "current_signals.csv",
        index=False
    )

    # Quality unresolved = flag_only, no replaced.
    unresolved = int(
        (quality.get("action", pd.Series(dtype=str)) == "flag_only").sum()
    )

    p = perf(portfolio["portfolio_net_ret"])
    b = perf(portfolio["benchmark_ret"])

    annual = (
        portfolio["portfolio_net_ret"]
        .groupby(portfolio.index.year)
        .apply(lambda s: (1 + s).prod() - 1)
    )

    high_cost = costs[
        np.isclose(costs["one_way_cost"], 0.0030)
    ]

    historical_tests = {
        "data_quality_no_unresolved_flags":
            unresolved == 0,
        "positive_return":
            p["total_return"] > 0,
        "sharpe_at_least_0_60":
            p["sharpe"] >= 0.60,
        "max_drawdown_better_than_-25pct":
            p["max_drawdown"] >= -0.25,
        "positive_year_rate_at_least_60pct":
            float((annual > 0).mean()) >= 0.60,
        "positive_at_double_cost":
            (
                len(high_cost)
                and float(high_cost.iloc[0]["total_return"]) > 0
            ),
        "competitive_vs_benchmark":
            (
                p["sharpe"] >= b["sharpe"]
                or (
                    abs(p["max_drawdown"])
                    <= 0.75 * abs(b["max_drawdown"])
                    and p["cagr"] >= 0.70 * b["cagr"]
                )
            ),
    }

    passed = all(historical_tests.values())

    # Incluso si pasa, no lo llamamos Champion definitivo sin forward paper.
    status = (
        "HISTORICAL_CHAMPION_CANDIDATE"
        if passed
        else "RESEARCH_CANDIDATE"
    )

    decision = {
        "status": status,
        "historical_tests": historical_tests,
        "mfp": p,
        "benchmark": b,
        "forward_paper_required": True,
        "note":
            "Champion definitivo requiere validación futura no usada "
            "en ninguna decisión de diseño.",
    }

    (OUTPUT / "decision.json").write_text(
        json.dumps(
            decision, indent=2,
            ensure_ascii=False, default=float
        ),
        encoding="utf-8",
    )

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
        mc_summary.to_csv(
            OUTPUT / "monte_carlo_summary.csv",
            index=False
        )

    print("\n" + "=" * 90)
    print("RESULTADO MFP-3 v1.7 META-LEARNING ENSEMBLE")
    print("=" * 90)
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

    print("\nESTADO:", status)
    for k, v in historical_tests.items():
        print(f"  {'OK' if v else 'FALLA':5s} {k}")

    print("\nSEÑALES PAPER ACTUALES")
    with pd.option_context(
        "display.max_columns", None,
        "display.width", 180
    ):
        print(sig)

    print("\nROTACIÓN")
    print(
        "  turnover cartera:",
        f"{portfolio['portfolio_turnover'].sum():.2f}"
    )

    print("\nArchivos:", OUTPUT.resolve())
    print(
        "\nNo usar las señales con dinero real. "
        "Incluso si supera las pruebas históricas, "
        "la siguiente fase debe ser forward paper."
    )

if __name__ == "__main__":
    main()
