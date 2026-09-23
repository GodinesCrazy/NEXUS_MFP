#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MFP-3 Adaptive v1.5 — TIME MACHINE TOURNAMENT
==============================================

Objetivo
--------
Hacer "viajes en el tiempo" legítimos. Para cada año de prueba:
1. Sólo usa información anterior a ese año.
2. Reserva ~1 año anterior como validación.
3. Purga/embarga las etiquetas que necesitarían conocer el futuro.
4. Hace competir varios modelos y horizontes.
5. Selecciona el ganador usando SOLO la validación pasada.
6. Congela la elección y la prueba durante el año siguiente.
7. Simula una cartera en CLP con QQQ, ECH y CPER.
8. Registra qué modelo/horizonte funcionó en cada época.

No ejecuta operaciones reales. Es investigación/paper trading.

Dependencias:
    pandas numpy scikit-learn yfinance

Instalación:
    py -m pip install yfinance

Ejecución:
    py mfp3_time_machine_v1_5.py
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple, List, Optional

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    raise SystemExit(
        "\nFalta yfinance.\n"
        "Ejecuta primero:\n"
        "  py -m pip install yfinance\n"
        "y luego vuelve a ejecutar este archivo.\n"
    )

from sklearn.base import clone
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    brier_score_loss,
    roc_auc_score,
    accuracy_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------
# CONFIGURACION
# ---------------------------------------------------------------------

TARGETS = {
    "QQQ": "NASDAQ / tecnología",
    "ECH": "Chile",
    "CPER": "Cobre",
}

# Variables de mercado disponibles al cierre de t.
MARKET_PREDICTORS = [
    "SPY", "EEM", "FXI", "HG=F", "GC=F", "CL=F",
    "^VIX", "TLT", "UUP", "CLP=X"
]

FRED_SERIES = {
    "US2Y": "DGS2",
    "US10Y": "DGS10",
    "FEDFUNDS": "DFF",
    "WTI_FRED": "DCOILWTICO",
    "USD_BROAD": "DTWEXBGS",
}

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"

START_DATE = "2006-01-01"
FIRST_TEST_YEAR = 2017
HORIZONS = [1, 5, 20]

INITIAL_CAPITAL_CLP = 10_000_000
MAX_WEIGHT_PER_ASSET = 0.30
ONE_WAY_COST = 0.0015       # 0,15%
VALIDATION_DAYS = 252
RANDOM_STATE = 42

OUTPUT = Path("mfp3_output_v15")

# ---------------------------------------------------------------------
# DESCARGA DE DATOS
# ---------------------------------------------------------------------

def _extract_ohlcv(downloaded: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Normaliza la salida de yfinance para un ticker."""
    if isinstance(downloaded.columns, pd.MultiIndex):
        # yfinance puede devolver (Price,Ticker) o (Ticker,Price)
        lev0 = downloaded.columns.get_level_values(0)
        lev1 = downloaded.columns.get_level_values(1)

        if ticker in lev0:
            d = downloaded[ticker].copy()
        elif ticker in lev1:
            d = downloaded.xs(ticker, axis=1, level=1).copy()
        else:
            raise KeyError(f"No se encontró {ticker} en descarga.")
    else:
        d = downloaded.copy()

    d.index = pd.to_datetime(d.index).tz_localize(None)
    d.columns = [str(c).title() for c in d.columns]
    return d.sort_index()

def download_market_data() -> Dict[str, pd.DataFrame]:
    tickers = list(TARGETS) + MARKET_PREDICTORS
    print("Descargando mercado desde Yahoo Finance...")
    raw = yf.download(
        tickers=tickers,
        start=START_DATE,
        progress=False,
        auto_adjust=True,
        group_by="column",
        threads=True,
    )

    out = {}
    for t in tickers:
        try:
            d = _extract_ohlcv(raw, t)
            if "Close" not in d or d["Close"].dropna().empty:
                print(f"  ADVERTENCIA: sin datos útiles para {t}")
                continue
            out[t] = d
            print(f"  {t:8s}: {d['Close'].dropna().index.min().date()} -> "
                  f"{d['Close'].dropna().index.max().date()} "
                  f"({d['Close'].dropna().shape[0]} filas)")
        except Exception as e:
            print(f"  ADVERTENCIA {t}: {e}")

    missing = [t for t in TARGETS if t not in out]
    if missing:
        raise SystemExit(f"Faltan objetivos esenciales: {missing}")

    if "CLP=X" not in out:
        raise SystemExit(
            "No se pudo descargar USD/CLP (CLP=X). "
            "Es necesario para medir la cartera en pesos chilenos."
        )
    return out

def download_fred() -> Dict[str, pd.Series]:
    out = {}
    print("\nDescargando macro desde FRED...")
    for name, sid in FRED_SERIES.items():
        try:
            df = pd.read_csv(FRED_URL.format(sid=sid))
            dcol, vcol = df.columns[0], df.columns[1]
            df[dcol] = pd.to_datetime(df[dcol])
            df[vcol] = pd.to_numeric(df[vcol], errors="coerce")
            s = df.set_index(dcol)[vcol].sort_index()
            out[name] = s
            print(f"  {name:10s} {sid}")
        except Exception as e:
            print(f"  ADVERTENCIA {name}: {e}")
    return out

# ---------------------------------------------------------------------
# SERIES EN CLP Y FEATURES
# ---------------------------------------------------------------------

def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)

def basic_features(s: pd.Series, prefix: str) -> pd.DataFrame:
    x = pd.DataFrame(index=s.index)
    daily = s.pct_change(fill_method=None)

    for n in [1, 2, 5, 10, 20, 60]:
        x[f"{prefix}_ret{n}"] = s.pct_change(n, fill_method=None)

    for n in [5, 20, 60]:
        x[f"{prefix}_vol{n}"] = daily.rolling(n).std() * np.sqrt(252)
        x[f"{prefix}_sma{n}"] = s / s.rolling(n).mean() - 1

    x[f"{prefix}_rsi14"] = rsi(s, 14) / 100.0
    x[f"{prefix}_dd60"] = s / s.rolling(60).max() - 1
    return x

def build_asset_frame(
    asset: str,
    market: Dict[str, pd.DataFrame],
    fred: Dict[str, pd.Series],
) -> pd.DataFrame:

    usd = market[asset]["Close"].dropna()
    fx = market["CLP=X"]["Close"].reindex(usd.index).ffill(limit=5)

    # Valor sintético de una participación expresado en CLP.
    clp_price = usd * fx
    clp_price.name = "price_clp"

    idx = clp_price.index
    blocks = [basic_features(clp_price, "self")]

    # Retorno del propio ETF en USD y del FX por separado.
    blocks.append(basic_features(usd, "usd_asset"))
    blocks.append(basic_features(fx, "usdclp"))

    # Mercado global: sólo datos del mismo cierre o anteriores.
    for ticker in MARKET_PREDICTORS:
        if ticker == "CLP=X" or ticker not in market:
            continue
        s = market[ticker]["Close"].reindex(idx).ffill(limit=5)
        safe = (
            ticker.replace("^", "")
                  .replace("=", "_")
                  .replace("-", "_")
                  .replace(".", "_")
                  .lower()
        )
        blocks.append(basic_features(s, safe))

    X = pd.concat(blocks, axis=1)

    # Macro: por prudencia se desplaza un día. Nunca usamos el valor "de hoy"
    # para evitar suponer que ya estaba publicado al generar la señal.
    for name, s in fred.items():
        z = s.reindex(idx).ffill(limit=7).shift(1)
        X[f"{name.lower()}_level"] = z
        X[f"{name.lower()}_chg5"] = z.diff(5)
        X[f"{name.lower()}_chg20"] = z.diff(20)

    if "us10y_level" in X and "us2y_level" in X:
        X["curve_10y_2y"] = X["us10y_level"] - X["us2y_level"]

    # Calendario.
    X["dow_sin"] = np.sin(2 * np.pi * X.index.dayofweek / 5)
    X["dow_cos"] = np.cos(2 * np.pi * X.index.dayofweek / 5)
    X["month_sin"] = np.sin(2 * np.pi * X.index.month / 12)
    X["month_cos"] = np.cos(2 * np.pi * X.index.month / 12)

    X["price_clp"] = clp_price
    X["price_usd"] = usd
    X["usdclp"] = fx

    # Retorno diario del instrumento medido en CLP.
    X["daily_ret_clp"] = clp_price.pct_change(fill_method=None)

    # Etiquetas ejecutables:
    # señal al cierre t -> ejecución conservadora al cierre t+1 ->
    # salida h sesiones después del cierre de ejecución.
    for h in HORIZONS:
        entry = clp_price.shift(-1)
        exit_ = clp_price.shift(-(h + 1))
        fwd = exit_ / entry - 1
        X[f"fwd_ret_{h}"] = fwd
        X[f"y_up_{h}"] = np.where(fwd.notna(), (fwd > 0).astype(float), np.nan)

    return X

# ---------------------------------------------------------------------
# MODELOS
# ---------------------------------------------------------------------

def models():
    return {
        "LOGIT": Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("sc", StandardScaler()),
            ("m", LogisticRegression(
                C=0.20,
                max_iter=1600,
                class_weight="balanced",
                random_state=RANDOM_STATE,
            )),
        ]),
        "RF": Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("m", RandomForestClassifier(
                n_estimators=140,
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
                max_iter=130,
                learning_rate=0.04,
                max_leaf_nodes=10,
                min_samples_leaf=22,
                l2_regularization=3.0,
                random_state=RANDOM_STATE,
            )),
        ]),
    }

# ---------------------------------------------------------------------
# SIMULACION DE UNA SEÑAL
# ---------------------------------------------------------------------

def strategy_returns(
    signal: pd.Series,
    daily_ret: pd.Series,
    weight: float = 1.0,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    señal en cierre t.
    target_position se ejecuta en cierre t+1.
    El primer retorno capturable es t+1 -> t+2.

    Retorno en fecha d:
      posición determinada por señal d-2
    Costo en fecha d:
      cambio de posición ejecutado por señal d-1
    """
    signal = signal.astype(float).clip(0, 1)

    held_pos = signal.shift(2).fillna(0.0) * weight
    exec_pos = signal.shift(1).fillna(0.0) * weight
    turnover = exec_pos.diff().abs().fillna(exec_pos.abs())

    gross = held_pos * daily_ret.fillna(0.0)
    costs = turnover * ONE_WAY_COST
    net = gross - costs
    return net, held_pos, turnover

def perf(ret: pd.Series) -> dict:
    r = ret.fillna(0.0)
    if len(r) == 0:
        return dict(total_return=0.0, sharpe=np.nan, max_drawdown=0.0,
                    ann_vol=0.0, fitness=-999)

    curve = (1 + r).cumprod()
    total = float(curve.iloc[-1] - 1)
    vol = float(r.std() * np.sqrt(252))
    sharpe = float(r.mean() * 252 / vol) if vol > 1e-12 else 0.0
    dd = curve / curve.cummax() - 1
    mdd = float(dd.min())

    # CASH tiene fitness 0. Sólo estrategias con combinación riesgo/retorno
    # positiva pueden ganarle.
    fitness = sharpe + 0.50 * total - 0.50 * abs(mdd)

    return {
        "total_return": total,
        "sharpe": sharpe,
        "max_drawdown": mdd,
        "ann_vol": vol,
        "fitness": float(fitness),
    }

# ---------------------------------------------------------------------
# CANDIDATOS SIMPLES
# ---------------------------------------------------------------------

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

SIMPLE = ["BUYHOLD", "CASH", "MOMENTUM", "MEANREV", "TREND"]

# ---------------------------------------------------------------------
# VALIDACION Y SELECCION
# ---------------------------------------------------------------------

@dataclass
class Choice:
    asset: str
    year: int
    strategy: str
    horizon: int
    threshold: float
    val_fitness: float
    val_return: float
    val_sharpe: float
    val_mdd: float
    val_brier: float
    val_auc: float
    val_accuracy: float
    val_base_rate: float
    expected_horizon_return: float

def feature_columns(df: pd.DataFrame) -> List[str]:
    exclude = {
        "price_clp", "price_usd", "usdclp", "daily_ret_clp",
    }
    for h in HORIZONS:
        exclude.add(f"fwd_ret_{h}")
        exclude.add(f"y_up_{h}")
    return [c for c in df.columns if c not in exclude]

def evaluate_validation(
    asset: str,
    year: int,
    df: pd.DataFrame,
    h: int,
    model_name: str,
) -> Optional[Tuple[Choice, object]]:

    test_positions = np.flatnonzero(df.index.year == year)
    if len(test_positions) == 0:
        return None

    test_start_pos = int(test_positions[0])

    # Última fila cuya etiqueta h ya era completamente conocida antes del año test.
    known_end_exclusive = test_start_pos - (h + 1)
    if known_end_exclusive <= 0:
        return None

    known = df.iloc[:known_end_exclusive].dropna(
        subset=[f"y_up_{h}", f"fwd_ret_{h}"]
    )
    if len(known) < 650:
        return None

    val_n = min(VALIDATION_DAYS, max(126, len(known) // 4))
    embargo = h + 1

    if len(known) <= val_n + embargo + 252:
        return None

    core = known.iloc[:-(val_n + embargo)]
    val = known.iloc[-val_n:]

    feats = feature_columns(df)
    Xc = core[feats]
    yc = core[f"y_up_{h}"].astype(int)
    Xv = val[feats]
    yv = val[f"y_up_{h}"].astype(int)

    if yc.nunique() < 2 or yv.nunique() < 2:
        return None

    m = clone(models()[model_name])
    m.fit(Xc, yc)
    p = m.predict_proba(Xv)[:, 1]

    base_rate = float(yc.mean())
    base_prob = np.full(len(yv), base_rate)
    brier_ref = brier_score_loss(yv, base_prob)
    brier = brier_score_loss(yv, p)
    bss = 1 - brier / max(brier_ref, 1e-12)

    try:
        auc = float(roc_auc_score(yv, p))
    except Exception:
        auc = 0.5

    acc = float(accuracy_score(yv, p >= 0.5))

    # Si el clasificador no supera mínimamente el azar y el baseline, se invalida.
    if bss <= 0 or auc <= 0.50:
        return None

    # Tres umbrales discretos: pocos grados de libertad para reducir overfit.
    thresholds = sorted(set([
        round(min(0.75, max(0.52, base_rate + 0.01)), 3),
        round(min(0.75, max(0.56, base_rate + 0.05)), 3),
        round(min(0.75, max(0.60, base_rate + 0.10)), 3),
    ]))

    best = None
    for th in thresholds:
        sig = pd.Series((p >= th).astype(float), index=val.index)
        net, _, _ = strategy_returns(sig, val["daily_ret_clp"])
        pm = perf(net)

        active = sig > 0
        expected = (
            float(val.loc[active, f"fwd_ret_{h}"].mean())
            if active.any() else np.nan
        )

        # Exigir suficiente actividad para evitar "ganar" con 1 o 2 señales.
        if int(active.sum()) < 8:
            continue

        choice = Choice(
            asset=asset,
            year=year,
            strategy=model_name,
            horizon=h,
            threshold=float(th),
            val_fitness=pm["fitness"],
            val_return=pm["total_return"],
            val_sharpe=pm["sharpe"],
            val_mdd=pm["max_drawdown"],
            val_brier=float(brier),
            val_auc=auc,
            val_accuracy=acc,
            val_base_rate=base_rate,
            expected_horizon_return=expected,
        )

        if best is None or choice.val_fitness > best.val_fitness:
            best = choice

    if best is None:
        return None

    # Reentrena el ganador con toda la información cuya etiqueta ya se conocía.
    final_model = clone(models()[model_name])
    final_model.fit(known[feats], known[f"y_up_{h}"].astype(int))
    return best, final_model

def evaluate_simple_validation(
    asset: str,
    year: int,
    df: pd.DataFrame,
    strategy: str,
    h: int,
) -> Optional[Choice]:

    test_positions = np.flatnonzero(df.index.year == year)
    if len(test_positions) == 0:
        return None
    test_start_pos = int(test_positions[0])

    known_end_exclusive = test_start_pos - (h + 1)
    if known_end_exclusive <= 0:
        return None

    known = df.iloc[:known_end_exclusive].dropna(
        subset=[f"fwd_ret_{h}"]
    )
    if len(known) < 650:
        return None

    val_n = min(VALIDATION_DAYS, max(126, len(known) // 4))
    val = known.iloc[-val_n:]

    sig = simple_signal(strategy, val)
    net, _, _ = strategy_returns(sig, val["daily_ret_clp"])
    pm = perf(net)
    active = sig > 0

    expected = (
        float(val.loc[active, f"fwd_ret_{h}"].mean())
        if active.any() else 0.0
    )

    # CASH siempre tiene fitness 0.
    return Choice(
        asset=asset,
        year=year,
        strategy=strategy,
        horizon=h,
        threshold=np.nan,
        val_fitness=pm["fitness"],
        val_return=pm["total_return"],
        val_sharpe=pm["sharpe"],
        val_mdd=pm["max_drawdown"],
        val_brier=np.nan,
        val_auc=np.nan,
        val_accuracy=np.nan,
        val_base_rate=float(val[f"y_up_{h}"].mean()),
        expected_horizon_return=expected,
    )

def select_choice(
    asset: str,
    year: int,
    df: pd.DataFrame,
) -> Tuple[Choice, Optional[object], pd.DataFrame]:

    candidates = []
    fitted_by_key = {}

    for h in HORIZONS:
        # Simples
        for s in SIMPLE:
            c = evaluate_simple_validation(asset, year, df, s, h)
            if c is not None:
                candidates.append(c)

        # ML
        for model_name in models():
            out = evaluate_validation(asset, year, df, h, model_name)
            if out is not None:
                c, m = out
                candidates.append(c)
                fitted_by_key[(model_name, h, c.threshold)] = m

    if not candidates:
        # Fallback: CASH
        c = Choice(
            asset, year, "CASH", 5, np.nan,
            0.0, 0.0, 0.0, 0.0,
            np.nan, np.nan, np.nan, 0.5, 0.0
        )
        return c, None, pd.DataFrame()

    table = pd.DataFrame([c.__dict__ for c in candidates])

    # CASH debe existir y tener fitness aproximadamente 0.
    # Sólo promovemos algo si supera CASH por margen.
    table = table.sort_values(
        ["val_fitness", "val_sharpe", "val_return"],
        ascending=False
    )
    best_row = table.iloc[0]
    best = Choice(**{k: best_row[k] for k in Choice.__annotations__})

    if best.val_fitness <= 0.05:
        # Si ninguna estrategia demuestra ventaja suficientemente clara, CASH.
        cash_rows = table[table["strategy"] == "CASH"]
        if len(cash_rows):
            cr = cash_rows.iloc[0]
            best = Choice(**{k: cr[k] for k in Choice.__annotations__})
        else:
            best = Choice(
                asset, year, "CASH", 5, np.nan,
                0.0, 0.0, 0.0, 0.0,
                np.nan, np.nan, np.nan, 0.5, 0.0
            )

    fitted = None
    if best.strategy in models():
        key = (best.strategy, int(best.horizon), float(best.threshold))
        fitted = fitted_by_key.get(key)

    return best, fitted, table

# ---------------------------------------------------------------------
# PRUEBA DEL AÑO FUTURO
# ---------------------------------------------------------------------

def test_choice(
    choice: Choice,
    fitted_model: Optional[object],
    df: pd.DataFrame,
) -> Tuple[pd.DataFrame, dict]:

    test = df[df.index.year == int(choice.year)].copy()
    if test.empty:
        return pd.DataFrame(), {}

    h = int(choice.horizon)

    if choice.strategy in SIMPLE:
        sig = simple_signal(choice.strategy, test)
        p = pd.Series(np.nan, index=test.index)
    else:
        feats = feature_columns(df)
        pvals = fitted_model.predict_proba(test[feats])[:, 1]
        p = pd.Series(pvals, index=test.index)
        sig = (p >= float(choice.threshold)).astype(float)

    net, pos, turnover = strategy_returns(sig, test["daily_ret_clp"])
    pm = perf(net)

    out = pd.DataFrame(index=test.index)
    out["asset"] = choice.asset
    out["year"] = choice.year
    out["strategy"] = choice.strategy
    out["horizon"] = choice.horizon
    out["threshold"] = choice.threshold
    out["signal"] = sig
    out["p_up"] = p
    out["position_asset_level"] = pos
    out["turnover_asset_level"] = turnover
    out["daily_ret_clp"] = test["daily_ret_clp"]
    out["strategy_ret_asset_level"] = net
    out["price_usd"] = test["price_usd"]
    out["usdclp"] = test["usdclp"]
    out["price_clp"] = test["price_clp"]

    test_summary = {
        "asset": choice.asset,
        "year": choice.year,
        "strategy": choice.strategy,
        "horizon": choice.horizon,
        "threshold": choice.threshold,
        "val_fitness": choice.val_fitness,
        "val_return": choice.val_return,
        "val_sharpe": choice.val_sharpe,
        "val_mdd": choice.val_mdd,
        "val_brier": choice.val_brier,
        "val_auc": choice.val_auc,
        "val_accuracy": choice.val_accuracy,
        "expected_horizon_return_from_validation":
            choice.expected_horizon_return,
        "test_return": pm["total_return"],
        "test_sharpe": pm["sharpe"],
        "test_mdd": pm["max_drawdown"],
        "test_ann_vol": pm["ann_vol"],
    }
    return out, test_summary

# ---------------------------------------------------------------------
# TORNEO COMPLETO
# ---------------------------------------------------------------------

def run_tournament(frames: Dict[str, pd.DataFrame]):
    latest_year = max(df.index.max().year for df in frames.values())
    years = list(range(FIRST_TEST_YEAR, latest_year + 1))

    all_daily = []
    selections = []
    validation_candidates = []

    for year in years:
        print("\n" + "=" * 88)
        print(f"VIAJE EN EL TIEMPO -> AÑO DE PRUEBA {year}")
        print("=" * 88)

        for asset, df in frames.items():
            if not np.any(df.index.year == year):
                continue

            print(f"\n{asset}: seleccionando estrategia sólo con pasado...")
            best, fitted, table = select_choice(asset, year, df)

            if not table.empty:
                table["asset"] = asset
                table["test_year"] = year
                validation_candidates.append(table)

            print(
                f"  Ganador validación: {best.strategy} | "
                f"H={int(best.horizon)} | "
                f"fitness={best.val_fitness:.3f} | "
                f"Sharpe={best.val_sharpe:.3f}"
            )

            daily, summary = test_choice(best, fitted, df)
            if len(daily):
                all_daily.append(daily)
                selections.append(summary)
                print(
                    f"  Resultado FUTURO {year}: "
                    f"{summary['test_return']:+.2%} | "
                    f"Sharpe {summary['test_sharpe']:.2f} | "
                    f"DD {summary['test_mdd']:.2%}"
                )

    daily = pd.concat(all_daily).sort_index() if all_daily else pd.DataFrame()
    sel = pd.DataFrame(selections)

    cand = (
        pd.concat(validation_candidates, ignore_index=True)
        if validation_candidates else pd.DataFrame()
    )
    return daily, sel, cand

# ---------------------------------------------------------------------
# CARTERA MULTIACTIVO 30/30/30
# ---------------------------------------------------------------------

def build_portfolio(
    daily: pd.DataFrame,
    frames: Dict[str, pd.DataFrame],
) -> pd.DataFrame:

    if daily.empty:
        return pd.DataFrame()

    # pivot de retorno de estrategia asset-level.
    r = daily.pivot_table(
        index=daily.index,
        columns="asset",
        values="strategy_ret_asset_level",
        aggfunc="last",
    ).fillna(0.0)

    # La estrategia individual está calculada a 100%.
    # La cartera limita cada activo a 30%.
    portfolio_ret = pd.Series(0.0, index=r.index)
    for asset in TARGETS:
        if asset in r:
            portfolio_ret += MAX_WEIGHT_PER_ASSET * r[asset]

    out = pd.DataFrame(index=r.index)
    out["portfolio_ret_net"] = portfolio_ret
    out["capital_clp"] = INITIAL_CAPITAL_CLP * (1 + portfolio_ret).cumprod()

    # Benchmarks 30/30/30 en CLP, misma ventana de fechas.
    bench = pd.Series(0.0, index=out.index)
    for asset, df in frames.items():
        rr = df["daily_ret_clp"].reindex(out.index).fillna(0.0)
        bench += MAX_WEIGHT_PER_ASSET * rr

    out["benchmark_30_30_30_ret"] = bench
    out["benchmark_capital_clp"] = (
        INITIAL_CAPITAL_CLP * (1 + bench).cumprod()
    )
    return out

# ---------------------------------------------------------------------
# METRICAS Y SEÑAL ACTUAL
# ---------------------------------------------------------------------

def metric_row(name: str, r: pd.Series) -> dict:
    p = perf(r)
    return {
        "name": name,
        **p,
    }

def current_signals(
    selections: pd.DataFrame,
    daily: pd.DataFrame,
) -> pd.DataFrame:

    if selections.empty or daily.empty:
        return pd.DataFrame()

    latest_year = int(selections["year"].max())
    rows = []

    for asset in TARGETS:
        s = selections[
            (selections["asset"] == asset)
            & (selections["year"] == latest_year)
        ]
        if s.empty:
            continue

        row = s.iloc[-1]
        d = daily[
            (daily["asset"] == asset)
            & (daily["year"] == latest_year)
        ].sort_index()

        if d.empty:
            continue

        last = d.iloc[-1]
        sig = float(last["signal"])
        prev = float(d.iloc[-2]["signal"]) if len(d) > 1 else 0.0

        if sig > 0 and prev <= 0:
            action = "COMPRAR (paper)"
        elif sig > 0 and prev > 0:
            action = "MANTENER (paper)"
        elif sig <= 0 and prev > 0:
            action = "VENDER / PASAR A CASH (paper)"
        else:
            action = "CASH / NO OPERAR"

        expected = row["expected_horizon_return_from_validation"]
        price_clp = float(last["price_clp"])
        projected = (
            price_clp * (1 + expected)
            if pd.notna(expected) else np.nan
        )

        rows.append({
            "date": d.index[-1],
            "asset": asset,
            "strategy": row["strategy"],
            "horizon_sessions": int(row["horizon"]),
            "threshold": row["threshold"],
            "p_up": last["p_up"],
            "paper_action": action,
            "current_usd_price": last["price_usd"],
            "usdclp": last["usdclp"],
            "current_clp_value_per_share": price_clp,
            "expected_clp_return_from_validation": expected,
            "projected_clp_value_horizon": projected,
        })

    return pd.DataFrame(rows)

# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main():
    OUTPUT.mkdir(exist_ok=True)

    market = download_market_data()
    fred = download_fred()

    frames = {}
    print("\nConstruyendo variables...")
    for asset in TARGETS:
        df = build_asset_frame(asset, market, fred)
        frames[asset] = df
        print(
            f"  {asset}: {df.index.min().date()} -> {df.index.max().date()} "
            f"({len(df)} filas)"
        )

    daily, selections, candidates = run_tournament(frames)

    daily.to_csv(OUTPUT / "time_machine_daily.csv")
    selections.to_csv(OUTPUT / "fold_selections.csv", index=False)
    candidates.to_csv(OUTPUT / "validation_candidates.csv", index=False)

    portfolio = build_portfolio(daily, frames)
    portfolio.to_csv(OUTPUT / "portfolio_daily.csv")

    metrics = []
    if not portfolio.empty:
        metrics.append(
            metric_row("MFP3_v15_TIME_MACHINE",
                       portfolio["portfolio_ret_net"])
        )
        metrics.append(
            metric_row("BENCHMARK_30_30_30_CLP",
                       portfolio["benchmark_30_30_30_ret"])
        )

    # Resultados individuales de las estrategias realmente seleccionadas.
    if not daily.empty:
        for asset in TARGETS:
            z = daily[daily["asset"] == asset]
            if len(z):
                metrics.append(
                    metric_row(
                        f"SELECTED_{asset}",
                        z["strategy_ret_asset_level"]
                    )
                )

    metrics_df = pd.DataFrame(metrics)
    metrics_df.to_csv(OUTPUT / "metrics.csv", index=False)

    sig = current_signals(selections, daily)
    sig.to_csv(OUTPUT / "current_signals.csv", index=False)

    # Frecuencia con que cada estrategia fue elegida y resultado futuro medio.
    if not selections.empty:
        leaderboard = (
            selections
            .groupby(["asset", "strategy", "horizon"], dropna=False)
            .agg(
                times_selected=("year", "count"),
                avg_validation_fitness=("val_fitness", "mean"),
                avg_test_return=("test_return", "mean"),
                median_test_return=("test_return", "median"),
                avg_test_sharpe=("test_sharpe", "mean"),
                positive_test_year_rate=("test_return", lambda s: (s > 0).mean()),
                worst_test_return=("test_return", "min"),
                avg_test_drawdown=("test_mdd", "mean"),
            )
            .reset_index()
            .sort_values(
                ["asset", "times_selected", "avg_test_return"],
                ascending=[True, False, False],
            )
        )
    else:
        leaderboard = pd.DataFrame()

    leaderboard.to_csv(OUTPUT / "leaderboard.csv", index=False)

    print("\n" + "=" * 88)
    print("RESULTADO TIME MACHINE v1.5")
    print("=" * 88)
    with pd.option_context("display.max_columns", None, "display.width", 180):
        print(metrics_df)

    if not portfolio.empty:
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

    print("\nSEÑALES PAPER ACTUALES")
    with pd.option_context("display.max_columns", None, "display.width", 180):
        print(sig)

    print("\nArchivos creados en:", OUTPUT.resolve())
    print(
        "\nIMPORTANTE: el ganador del torneo todavía es un CANDIDATO. "
        "No se convierte en Champion hasta superar pruebas de estabilidad, "
        "Monte Carlo y sensibilidad a costos en la siguiente versión."
    )

if __name__ == "__main__":
    main()
