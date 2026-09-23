#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MFP-3 Adaptive v1.2
Laboratorio cuantitativo walk-forward para predicción y paper trading.

IMPORTANTE:
- Diseñado para investigación/paper trading, no para operar dinero real.
- No usa información futura en el entrenamiento: para una señal en t, las etiquetas
  del set de entrenamiento terminan al menos HORIZON sesiones antes de t.
- Señal calculada con cierre t; ejecución conservadora aproximada al cierre t+1.
- Datos: FRED (CSV público sin API key) para índices Nasdaq y variables macro/mercado.

Salida:
  mfp3_output/
    predictions_<asset>.csv
    portfolio_daily.csv
    metrics.csv
    model_weights.csv
"""

from __future__ import annotations
import math
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from sklearn.base import clone
from sklearn.calibration import calibration_curve
from sklearn.ensemble import (
    RandomForestClassifier,
    HistGradientBoostingClassifier,
    GradientBoostingClassifier,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import brier_score_loss, accuracy_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

# ----------------------------- CONFIG ---------------------------------

FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"

TARGETS = {
    # largos historiales
    "NASDAQ100_TR": "NASDAQXNDX",
    "CHILE_LARGECAP_NTR": "NASDAQNQCLLCN",
    # historia más corta: usar mayor regularización y cautela
    "COPPER_MINERS_TR": "NASDAQNSCOPPT",
}

EXOGENOUS = {
    "VIX": "VIXCLS",
    "FEDFUNDS": "DFF",
    "US2Y": "DGS2",
    "US10Y": "DGS10",
    "WTI": "DCOILWTICO",
    "USD_BROAD": "DTWEXBGS",
    "NASDAQ_COMPOSITE": "NASDAQCOM",
}

TEST_START = "2025-09-22"
HORIZON = 5
MAX_POSITION = 0.30
ROUND_TRIP_COST = 0.0030      # 0.15% entrada + 0.15% salida
ONE_WAY_COST = ROUND_TRIP_COST / 2
MIN_TRAIN = 350
VALIDATION_SIZE = 252
ROLLING_TRAIN_DAYS = 6 * 252  # adaptación: aprox 6 años
RETRAIN_EVERY = "M"           # mensual
RANDOM_STATE = 42

OUTPUT_DIR = Path("mfp3_output")

# ----------------------------- DATA -----------------------------------

def load_fred(series_id: str) -> pd.Series:
    url = FRED_BASE.format(series=series_id)
    df = pd.read_csv(url)
    date_col = df.columns[0]
    val_col = df.columns[1]
    df[date_col] = pd.to_datetime(df[date_col])
    df[val_col] = pd.to_numeric(df[val_col], errors="coerce")
    s = df.set_index(date_col)[val_col].dropna().sort_index()
    s.name = series_id
    return s

def download_all() -> Dict[str, pd.Series]:
    raw: Dict[str, pd.Series] = {}
    for name, sid in {**TARGETS, **EXOGENOUS}.items():
        print(f"Descargando {name:22s} {sid} ...")
        raw[name] = load_fred(sid)
    return raw

# -------------------------- FEATURES ----------------------------------

def rsi(series: pd.Series, n: int = 14) -> pd.Series:
    d = series.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)

def price_features(s: pd.Series, prefix: str) -> pd.DataFrame:
    x = pd.DataFrame(index=s.index)
    for n in [1, 2, 5, 10, 20, 60]:
        x[f"{prefix}_ret_{n}"] = s.pct_change(n, fill_method=None)
    daily = s.pct_change(fill_method=None)
    for n in [5, 10, 20, 60]:
        x[f"{prefix}_vol_{n}"] = daily.rolling(n).std() * math.sqrt(252)
        sma = s.rolling(n).mean()
        x[f"{prefix}_sma_dist_{n}"] = s / sma - 1
    x[f"{prefix}_drawdown_60"] = s / s.rolling(60).max() - 1
    x[f"{prefix}_rsi14"] = rsi(s, 14) / 100.0
    x[f"{prefix}_accel"] = x[f"{prefix}_ret_5"] - x[f"{prefix}_ret_20"] / 4
    return x

def rate_features(s: pd.Series, prefix: str) -> pd.DataFrame:
    x = pd.DataFrame(index=s.index)
    x[f"{prefix}_level"] = s
    for n in [1, 5, 20]:
        x[f"{prefix}_diff_{n}"] = s.diff(n)
    return x

def build_frame(asset: str, raw: Dict[str, pd.Series]) -> pd.DataFrame:
    target = raw[asset].copy()
    base_index = target.index
    blocks = [price_features(target, "self")]

    # cross-market: cada serie calcula sus variables en su propio calendario;
    # luego se lleva al calendario del objetivo usando sólo el último dato conocido.
    for other in TARGETS:
        if other == asset:
            continue
        b = price_features(raw[other], other.lower())
        b = b.reindex(base_index).ffill(limit=5)
        blocks.append(b)

    # Mercado/macro
    for name in ["VIX", "FEDFUNDS", "US2Y", "US10Y", "WTI", "USD_BROAD", "NASDAQ_COMPOSITE"]:
        s = raw[name]
        if name in ["FEDFUNDS", "US2Y", "US10Y", "VIX"]:
            b = rate_features(s, name.lower())
            if name == "VIX":
                b[f"{name.lower()}_pct_5"] = s.pct_change(5, fill_method=None)
                b[f"{name.lower()}_pct_20"] = s.pct_change(20, fill_method=None)
        else:
            b = price_features(s, name.lower())
        b = b.reindex(base_index).ffill(limit=5)
        blocks.append(b)

    X = pd.concat(blocks, axis=1)

    # Diferencial de tasas 10Y-2Y, útil como variable de régimen.
    if "us10y_level" in X and "us2y_level" in X:
        X["curve_10y_2y"] = X["us10y_level"] - X["us2y_level"]

    # Variables de calendario (sin codificar el año, para reducir sobreajuste)
    X["dow_sin"] = np.sin(2 * np.pi * X.index.dayofweek / 5.0)
    X["dow_cos"] = np.cos(2 * np.pi * X.index.dayofweek / 5.0)
    X["month_sin"] = np.sin(2 * np.pi * X.index.month / 12.0)
    X["month_cos"] = np.cos(2 * np.pi * X.index.month / 12.0)

    # Etiquetas
    X["price"] = target
    X["fwd_ret"] = target.shift(-HORIZON) / target - 1
    X["y_up"] = (X["fwd_ret"] > 0).astype(float)
    X.loc[X["fwd_ret"].isna(), "y_up"] = np.nan
    return X

# --------------------------- MODELS -----------------------------------

def model_templates():
    return {
        "logit": Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("sc", StandardScaler()),
            ("m", LogisticRegression(
                C=0.35, max_iter=2000, class_weight="balanced",
                random_state=RANDOM_STATE
            )),
        ]),
        "rf": Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("m", RandomForestClassifier(
                n_estimators=350, max_depth=5, min_samples_leaf=18,
                max_features="sqrt", class_weight="balanced_subsample",
                n_jobs=-1, random_state=RANDOM_STATE
            )),
        ]),
        "hgb": Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("m", HistGradientBoostingClassifier(
                max_iter=220, learning_rate=0.035, max_leaf_nodes=12,
                min_samples_leaf=22, l2_regularization=2.0,
                random_state=RANDOM_STATE
            )),
        ]),
        "gb": Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("m", GradientBoostingClassifier(
                n_estimators=160, learning_rate=0.03, max_depth=2,
                min_samples_leaf=18, subsample=0.80,
                random_state=RANDOM_STATE
            )),
        ]),
    }

def ridge_template():
    return Pipeline([
        ("imp", SimpleImputer(strategy="median")),
        ("sc", StandardScaler()),
        ("m", Ridge(alpha=20.0)),
    ])

@dataclass
class FitState:
    classifiers: Dict[str, object]
    ridge: object
    weights: Dict[str, float]
    threshold: float
    validation_brier: float
    validation_accuracy: float
    train_start: pd.Timestamp
    train_end: pd.Timestamp

def choose_threshold(p: np.ndarray, fwd: np.ndarray) -> float:
    """
    Umbral aprendido sólo en validación.
    Fitness penaliza variabilidad y costos. Se exige mínimo de señales.
    """
    best_t, best_score = 0.60, -np.inf
    for t in np.arange(0.52, 0.681, 0.02):
        sig = (p >= t).astype(float)
        n = int(sig.sum())
        if n < max(12, int(len(sig) * 0.06)):
            continue
        # retorno medio por observación etiquetada; costo aprox al entrar/salir.
        gross = sig * fwd
        # penalización simple por cambios de estado
        turnover = np.abs(np.diff(np.r_[0, sig]))
        net = gross.copy()
        net -= ONE_WAY_COST * np.r_[turnover, 0][:len(net)]
        mu = np.nanmean(net)
        sd = np.nanstd(net)
        downside = np.sqrt(np.nanmean(np.minimum(net, 0) ** 2)) + 1e-9
        score = (mu / (sd + 1e-9)) + 0.25 * (mu / downside)
        if score > best_score:
            best_score, best_t = score, float(t)
    return best_t

def fit_state(df: pd.DataFrame, pred_pos: int, feature_cols: List[str]) -> FitState:
    # Para señal en t, una etiqueta de fila r sólo puede usarse si r+HORIZON < t.
    train_last_pos = pred_pos - HORIZON - 1
    if train_last_pos < MIN_TRAIN:
        raise ValueError("Historia insuficiente")

    start_pos = max(0, train_last_pos - ROLLING_TRAIN_DAYS + 1)
    hist = df.iloc[start_pos:train_last_pos + 1].dropna(subset=["y_up", "fwd_ret"]).copy()

    if len(hist) < MIN_TRAIN:
        raise ValueError("Historia útil insuficiente")

    val_n = min(VALIDATION_SIZE, max(84, len(hist) // 4))
    core = hist.iloc[:-val_n]
    val = hist.iloc[-val_n:]

    Xc, yc = core[feature_cols], core["y_up"].astype(int)
    Xv, yv = val[feature_cols], val["y_up"].astype(int)

    templates = model_templates()
    briers = {}
    val_probs = {}
    trained = {}

    for name, tmpl in templates.items():
        m = clone(tmpl)
        m.fit(Xc, yc)
        pv = m.predict_proba(Xv)[:, 1]
        b = brier_score_loss(yv, pv)
        briers[name] = max(b, 1e-4)
        val_probs[name] = pv

    # Pesos adaptativos: mejor calibración reciente = mayor peso.
    inv = {k: 1.0 / v for k, v in briers.items()}
    z = sum(inv.values())
    weights = {k: v / z for k, v in inv.items()}

    ensemble_v = sum(weights[k] * val_probs[k] for k in weights)
    vb = brier_score_loss(yv, ensemble_v)
    va = accuracy_score(yv, ensemble_v >= 0.5)
    threshold = choose_threshold(ensemble_v, val["fwd_ret"].values)

    # Reentrena cada modelo con toda la historia permitida.
    Xh, yh = hist[feature_cols], hist["y_up"].astype(int)
    for name, tmpl in templates.items():
        m = clone(tmpl)
        m.fit(Xh, yh)
        trained[name] = m

    rr = clone(ridge_template())
    rr.fit(Xh, hist["fwd_ret"].values)

    return FitState(
        classifiers=trained,
        ridge=rr,
        weights=weights,
        threshold=threshold,
        validation_brier=vb,
        validation_accuracy=va,
        train_start=hist.index.min(),
        train_end=hist.index.max(),
    )

# -------------------------- WALK FORWARD -------------------------------

def position_from_signal(p: float, pred_ret: float, threshold: float) -> float:
    # Gating: la rentabilidad prevista debe superar el round-trip cost.
    if not np.isfinite(p) or not np.isfinite(pred_ret):
        return 0.0
    if pred_ret <= ROUND_TRIP_COST:
        return 0.0
    if p < threshold:
        return 0.0
    # tamaño incremental, nunca >30%
    excess = p - threshold
    if excess < 0.04:
        return 0.10
    if excess < 0.09:
        return 0.20
    return MAX_POSITION

def walk_forward(asset: str, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    feature_cols = [c for c in df.columns if c not in {"price", "fwd_ret", "y_up"}]
    test_mask = df.index >= pd.Timestamp(TEST_START)
    test_positions = np.flatnonzero(test_mask)

    rows = []
    weight_rows = []
    state = None
    last_fit_month = None

    for pos in test_positions:
        date = df.index[pos]
        # sólo predecimos si existe al menos precio actual
        if not np.isfinite(df.iloc[pos]["price"]):
            continue

        month_key = (date.year, date.month)
        need_refit = state is None or month_key != last_fit_month

        if need_refit:
            try:
                state = fit_state(df, pos, feature_cols)
                last_fit_month = month_key
                wr = {
                    "date": date, "asset": asset,
                    "threshold": state.threshold,
                    "val_brier": state.validation_brier,
                    "val_accuracy": state.validation_accuracy,
                    "train_start": state.train_start,
                    "train_end": state.train_end,
                }
                wr.update({f"w_{k}": v for k, v in state.weights.items()})
                weight_rows.append(wr)
            except ValueError:
                continue

        x = df.iloc[[pos]][feature_cols]
        probs = {
            k: state.classifiers[k].predict_proba(x)[:, 1][0]
            for k in state.classifiers
        }
        p = float(sum(state.weights[k] * probs[k] for k in probs))
        pred_ret = float(state.ridge.predict(x)[0])
        position = position_from_signal(p, pred_ret, state.threshold)

        rows.append({
            "date": date,
            "asset": asset,
            "price": float(df.iloc[pos]["price"]),
            "p_up": p,
            "pred_fwd_ret": pred_ret,
            "threshold": state.threshold,
            "signal_position": position,
            "actual_fwd_ret": float(df.iloc[pos]["fwd_ret"]) if np.isfinite(df.iloc[pos]["fwd_ret"]) else np.nan,
            "actual_up": float(df.iloc[pos]["y_up"]) if np.isfinite(df.iloc[pos]["y_up"]) else np.nan,
            **{f"p_{k}": float(v) for k, v in probs.items()},
        })

    return pd.DataFrame(rows).set_index("date"), pd.DataFrame(weight_rows)

# -------------------------- PORTFOLIO ---------------------------------

def build_portfolio(preds: Dict[str, pd.DataFrame], raw: Dict[str, pd.Series]) -> pd.DataFrame:
    # calendario común: unión de fechas de predicción
    idx = sorted(set().union(*[set(p.index) for p in preds.values()]))
    out = pd.DataFrame(index=pd.DatetimeIndex(idx))

    asset_returns = {}
    for asset, p in preds.items():
        # retorno real del índice en su calendario
        r = raw[asset].pct_change(fill_method=None)
        r = r.reindex(out.index)
        asset_returns[asset] = r

        signal = p["signal_position"].reindex(out.index).ffill().fillna(0.0)
        # Conservador: señal generada con cierre t se considera ejecutada al cierre t+1,
        # por tanto empieza a capturar retorno desde t+1 a t+2 => shift(2).
        exec_pos = signal.shift(2).fillna(0.0)
        out[f"pos_{asset}"] = exec_pos
        out[f"ret_{asset}"] = r.fillna(0.0)

    # Cap total 90% por construcción (3 * 30%).
    pos_cols = [c for c in out.columns if c.startswith("pos_")]
    total_pos = out[pos_cols].sum(axis=1)
    scale = np.where(total_pos > 0.90, 0.90 / total_pos, 1.0)
    for c in pos_cols:
        out[c] = out[c] * scale

    gross = pd.Series(0.0, index=out.index)
    costs = pd.Series(0.0, index=out.index)

    for asset in preds:
        pos = out[f"pos_{asset}"]
        ret = out[f"ret_{asset}"]
        gross += pos * ret
        turnover = pos.diff().abs().fillna(pos.abs())
        costs += turnover * ONE_WAY_COST

    out["portfolio_ret_gross"] = gross
    out["cost"] = costs
    out["portfolio_ret_net"] = gross - costs
    out["capital"] = 10_000_000 * (1 + out["portfolio_ret_net"]).cumprod()
    out["cash_weight"] = 1 - out[pos_cols].sum(axis=1)
    return out

# --------------------------- METRICS ----------------------------------

def max_drawdown(ret: pd.Series) -> float:
    curve = (1 + ret.fillna(0)).cumprod()
    dd = curve / curve.cummax() - 1
    return float(dd.min())

def metrics_from_returns(ret: pd.Series, name: str) -> dict:
    r = ret.dropna()
    if len(r) == 0:
        return {"name": name}
    ann = (1 + r).prod() ** (252 / max(len(r), 1)) - 1
    vol = r.std() * math.sqrt(252)
    sharpe = (r.mean() * 252) / vol if vol > 0 else np.nan
    downside = r[r < 0].std() * math.sqrt(252)
    sortino = (r.mean() * 252) / downside if downside and downside > 0 else np.nan
    return {
        "name": name,
        "observations": len(r),
        "total_return": (1 + r).prod() - 1,
        "cagr": ann,
        "ann_vol": vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_drawdown(r),
    }

def prediction_metrics(pred: pd.DataFrame, asset: str) -> dict:
    d = pred.dropna(subset=["actual_up", "actual_fwd_ret"])
    if len(d) == 0:
        return {"name": f"{asset}_prediction"}
    y = d["actual_up"].astype(int)
    p = d["p_up"]
    active = d["signal_position"] > 0
    return {
        "name": f"{asset}_prediction",
        "observations": len(d),
        "directional_accuracy_50": accuracy_score(y, p >= 0.5),
        "brier": brier_score_loss(y, p),
        "active_signal_rate": active.mean(),
        "mean_actual_fwd_when_active": d.loc[active, "actual_fwd_ret"].mean() if active.any() else np.nan,
    }

# ----------------------------- MAIN -----------------------------------

def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    raw = download_all()

    predictions = {}
    all_weights = []
    metric_rows = []

    for asset in TARGETS:
        print("\n" + "=" * 78)
        print("WALK-FORWARD:", asset)
        df = build_frame(asset, raw)
        pred, weights = walk_forward(asset, df)
        predictions[asset] = pred
        pred.to_csv(OUTPUT_DIR / f"predictions_{asset}.csv")
        if len(weights):
            all_weights.append(weights)
        metric_rows.append(prediction_metrics(pred, asset))
        print(pred.tail(8)[["price", "p_up", "pred_fwd_ret", "threshold", "signal_position"]])

    portfolio = build_portfolio(predictions, raw)
    portfolio.to_csv(OUTPUT_DIR / "portfolio_daily.csv")
    metric_rows.append(metrics_from_returns(portfolio["portfolio_ret_net"], "MFP3_portfolio"))

    # Benchmarks: 30% en cada target, 10% cash, con misma ventana.
    bench = pd.Series(0.0, index=portfolio.index)
    for asset in TARGETS:
        r = raw[asset].pct_change(fill_method=None).reindex(portfolio.index).fillna(0.0)
        bench += 0.30 * r
    metric_rows.append(metrics_from_returns(bench, "Benchmark_30_30_30"))

    # Buy & Hold individual
    for asset in TARGETS:
        r = raw[asset].pct_change(fill_method=None).reindex(portfolio.index).fillna(0.0)
        metric_rows.append(metrics_from_returns(r, f"BuyHold_{asset}"))

    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(OUTPUT_DIR / "metrics.csv", index=False)

    if all_weights:
        pd.concat(all_weights, ignore_index=True).to_csv(
            OUTPUT_DIR / "model_weights.csv", index=False
        )

    print("\n" + "=" * 78)
    print("METRICAS")
    with pd.option_context("display.max_columns", None, "display.width", 160):
        print(metrics)

    print("\nCapital final MFP-3:", f"${portfolio['capital'].iloc[-1]:,.0f}")
    print("Archivos creados en:", OUTPUT_DIR.resolve())

if __name__ == "__main__":
    main()
