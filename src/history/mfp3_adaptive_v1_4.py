#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MFP-3 Adaptive v1.4 - Corrected Walk-Forward

Cambios frente a v1.2
---------------------
1) Etiqueta ejecutable:
   señal al cierre t -> ejecución conservadora al cierre t+1 ->
   objetivo = retorno desde cierre t+1 hasta cierre t+6 (5 sesiones completas).

2) Purge + embargo entre entrenamiento y validación.

3) Validación con muestras no solapadas para calibrar umbrales.

4) Los modelos sólo reciben peso si muestran skill fuera de muestra:
   - Brier mejor que baseline de prevalencia.
   - AUC > 0.50.

5) El modelo de retorno Ridge sólo habilita operaciones si supera en validación
   a una predicción constante basada en el retorno medio histórico.

6) CASH es una alternativa válida: si no existe edge demostrable, no opera.

7) Métricas incluyen baseline "always up", Brier Skill Score y AUC.

8) Mantiene costos de 0.15% por lado y máximo 30% por activo.

Uso:
    py mfp3_adaptive_v1_4.py

Requiere:
    pandas numpy scikit-learn
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
from sklearn.ensemble import (
    RandomForestClassifier,
    HistGradientBoostingClassifier,
    GradientBoostingClassifier,
)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (
    brier_score_loss,
    accuracy_score,
    roc_auc_score,
    mean_squared_error,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

# ----------------------------- CONFIG ---------------------------------

FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"

TARGETS = {
    "NASDAQ100_TR": "NASDAQXNDX",
    "CHILE_LARGECAP_NTR": "NASDAQNQCLLCN",
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
EXECUTION_DELAY = 1
LABEL_SPAN = EXECUTION_DELAY + HORIZON  # t+1 -> t+6

MAX_POSITION = 0.30
ONE_WAY_COST = 0.0015
ROUND_TRIP_COST = ONE_WAY_COST * 2

MIN_TRAIN = 350
VALIDATION_SIZE = 252
ROLLING_TRAIN_DAYS = 6 * 252
EMBARGO = LABEL_SPAN
RANDOM_STATE = 42

OUTPUT_DIR = Path("mfp3_output_v14")

# ----------------------------- DATA -----------------------------------

def load_fred(series_id: str) -> pd.Series:
    url = FRED_BASE.format(series=series_id)
    df = pd.read_csv(url)
    dcol, vcol = df.columns[0], df.columns[1]
    df[dcol] = pd.to_datetime(df[dcol])
    df[vcol] = pd.to_numeric(df[vcol], errors="coerce")
    s = df.set_index(dcol)[vcol].dropna().sort_index()
    s.name = series_id
    return s

def download_all() -> Dict[str, pd.Series]:
    raw = {}
    for name, sid in {**TARGETS, **EXOGENOUS}.items():
        print(f"Descargando {name:22s} {sid} ...")
        raw[name] = load_fred(sid)
    return raw

# --------------------------- FEATURES ---------------------------------

def rsi(series: pd.Series, n: int = 14) -> pd.Series:
    d = series.diff()
    up = d.clip(lower=0).rolling(n).mean()
    dn = (-d.clip(upper=0)).rolling(n).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)

def price_features(s: pd.Series, prefix: str) -> pd.DataFrame:
    x = pd.DataFrame(index=s.index)
    daily = s.pct_change(fill_method=None)

    for n in [1, 2, 5, 10, 20, 60]:
        x[f"{prefix}_ret_{n}"] = s.pct_change(n, fill_method=None)

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
    idx = target.index
    blocks = [price_features(target, "self")]

    for other in TARGETS:
        if other == asset:
            continue
        b = price_features(raw[other], other.lower()).reindex(idx).ffill(limit=5)
        blocks.append(b)

    for name in ["VIX", "FEDFUNDS", "US2Y", "US10Y", "WTI", "USD_BROAD", "NASDAQ_COMPOSITE"]:
        s = raw[name]
        if name in ["FEDFUNDS", "US2Y", "US10Y", "VIX"]:
            b = rate_features(s, name.lower())
            if name == "VIX":
                b["vix_pct_5"] = s.pct_change(5, fill_method=None)
                b["vix_pct_20"] = s.pct_change(20, fill_method=None)
        else:
            b = price_features(s, name.lower())
        blocks.append(b.reindex(idx).ffill(limit=5))

    X = pd.concat(blocks, axis=1)

    if "us10y_level" in X and "us2y_level" in X:
        X["curve_10y_2y"] = X["us10y_level"] - X["us2y_level"]

    X["dow_sin"] = np.sin(2 * np.pi * X.index.dayofweek / 5.0)
    X["dow_cos"] = np.cos(2 * np.pi * X.index.dayofweek / 5.0)
    X["month_sin"] = np.sin(2 * np.pi * X.index.month / 12.0)
    X["month_cos"] = np.cos(2 * np.pi * X.index.month / 12.0)

    X["price"] = target

    # CORRECCIÓN PRINCIPAL:
    # en t conocemos cierre_t, decidimos; ejecutamos al cierre t+1.
    # Se entrena el retorno de 5 sesiones DESPUÉS de esa ejecución.
    entry = target.shift(-EXECUTION_DELAY)             # precio t+1
    exit_ = target.shift(-LABEL_SPAN)                  # precio t+6
    X["fwd_ret_exec"] = exit_ / entry - 1
    X["y_up_exec"] = (X["fwd_ret_exec"] > 0).astype(float)
    X.loc[X["fwd_ret_exec"].isna(), "y_up_exec"] = np.nan

    return X

# ---------------------------- MODELS ----------------------------------

def classifier_templates():
    return {
        "logit": Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("sc", StandardScaler()),
            ("m", LogisticRegression(
                C=0.25, max_iter=2000, class_weight="balanced",
                random_state=RANDOM_STATE
            )),
        ]),
        "rf": Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("m", RandomForestClassifier(
                n_estimators=300,
                max_depth=5,
                min_samples_leaf=20,
                max_features="sqrt",
                class_weight="balanced_subsample",
                n_jobs=-1,
                random_state=RANDOM_STATE,
            )),
        ]),
        "hgb": Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("m", HistGradientBoostingClassifier(
                max_iter=180,
                learning_rate=0.035,
                max_leaf_nodes=10,
                min_samples_leaf=24,
                l2_regularization=3.0,
                random_state=RANDOM_STATE,
            )),
        ]),
        "gb": Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("m", GradientBoostingClassifier(
                n_estimators=140,
                learning_rate=0.03,
                max_depth=2,
                min_samples_leaf=20,
                subsample=0.80,
                random_state=RANDOM_STATE,
            )),
        ]),
    }

def ridge_template():
    return Pipeline([
        ("imp", SimpleImputer(strategy="median")),
        ("sc", StandardScaler()),
        ("m", Ridge(alpha=30.0)),
    ])

@dataclass
class FitState:
    classifiers: Dict[str, object]
    ridge: object
    weights: Dict[str, float]
    threshold: float
    base_rate: float
    classifier_skill: bool
    return_skill: float
    val_brier: float
    val_brier_ref: float
    val_bss: float
    val_auc: float
    val_accuracy: float
    val_always_up_accuracy: float
    train_start: pd.Timestamp
    train_end: pd.Timestamp

def choose_threshold(
    p: np.ndarray,
    pred_ret: np.ndarray,
    actual_ret: np.ndarray,
    base_rate: float,
) -> float:
    """
    El umbral se aprende sólo sobre validación purgada/no-solapada.
    Exige una ventaja probabilística respecto a la prevalencia histórica.
    """
    minimum = max(0.52, base_rate + 0.02)
    candidates = np.arange(minimum, min(0.76, minimum + 0.18) + 1e-9, 0.02)

    best_t = 1.0
    best_score = 0.0

    for t in candidates:
        active = (p >= t) & (pred_ret > ROUND_TRIP_COST * 1.25)
        n = int(active.sum())
        if n < 6:
            continue

        rr = actual_ret[active] - ROUND_TRIP_COST
        mu = np.nanmean(rr)
        sd = np.nanstd(rr)
        hit = np.nanmean(rr > 0)
        # Sólo se acepta un umbral con esperanza positiva y >50% de éxitos netos.
        if mu <= 0 or hit <= 0.50:
            continue

        score = mu / (sd + 1e-9) * math.sqrt(n)
        if score > best_score:
            best_score = score
            best_t = float(t)

    return best_t

def fit_state(df: pd.DataFrame, pred_pos: int, features: List[str]) -> FitState:
    # Una etiqueta de fila r requiere precio r+LABEL_SPAN.
    # En la fecha pred_pos sólo usamos etiquetas completamente realizadas.
    train_last_pos = pred_pos - LABEL_SPAN

    if train_last_pos < MIN_TRAIN:
        raise ValueError("Historia insuficiente")

    start_pos = max(0, train_last_pos - ROLLING_TRAIN_DAYS + 1)
    hist = df.iloc[start_pos:train_last_pos + 1].dropna(
        subset=["y_up_exec", "fwd_ret_exec"]
    ).copy()

    if len(hist) < MIN_TRAIN:
        raise ValueError("Historia útil insuficiente")

    val_n = min(VALIDATION_SIZE, max(96, len(hist) // 4))

    # Purge/embargo entre core y validación.
    if len(hist) <= val_n + EMBARGO + 100:
        raise ValueError("Historia insuficiente para purge/embargo")

    core = hist.iloc[:-(val_n + EMBARGO)]
    val_full = hist.iloc[-val_n:]

    # Para calibración/selección usamos observaciones no solapadas.
    val = val_full.iloc[::LABEL_SPAN].copy()

    Xc = core[features]
    yc = core["y_up_exec"].astype(int)
    Xv = val[features]
    yv = val["y_up_exec"].astype(int)

    base_rate = float(yc.mean())
    base_prob = np.full(len(yv), base_rate)
    brier_ref = brier_score_loss(yv, base_prob)

    templates = classifier_templates()
    trained = {}
    val_probs = {}
    skills = {}

    for name, tmpl in templates.items():
        m = clone(tmpl)
        m.fit(Xc, yc)
        pv = m.predict_proba(Xv)[:, 1]

        brier = brier_score_loss(yv, pv)
        try:
            auc = roc_auc_score(yv, pv)
        except Exception:
            auc = 0.5

        bss = 1.0 - brier / max(brier_ref, 1e-9)

        # El modelo debe superar el baseline de probabilidad y tener discriminación > azar.
        skill = max(0.0, bss) * max(0.0, 2.0 * (auc - 0.50))
        skills[name] = skill
        val_probs[name] = pv

    total_skill = sum(skills.values())
    classifier_skill = total_skill > 0

    if classifier_skill:
        weights = {k: v / total_skill for k, v in skills.items()}
        ensemble_v = sum(weights[k] * val_probs[k] for k in weights)
    else:
        weights = {k: 0.0 for k in skills}
        ensemble_v = np.full(len(yv), base_rate)

    vb = brier_score_loss(yv, ensemble_v)
    vbss = 1.0 - vb / max(brier_ref, 1e-9)
    try:
        vauc = roc_auc_score(yv, ensemble_v)
    except Exception:
        vauc = 0.5
    vacc = accuracy_score(yv, ensemble_v >= 0.5)
    always_up_acc = float(max(yv.mean(), 1 - yv.mean()))

    # Modelo de magnitud: debe superar retorno medio de entrenamiento.
    rr = clone(ridge_template())
    rr.fit(Xc, core["fwd_ret_exec"].values)
    pred_r_val = rr.predict(Xv)

    baseline_ret = float(core["fwd_ret_exec"].mean())
    ref_pred = np.full(len(val), baseline_ret)

    mse_model = mean_squared_error(val["fwd_ret_exec"].values, pred_r_val)
    mse_ref = mean_squared_error(val["fwd_ret_exec"].values, ref_pred)
    return_skill = 1.0 - mse_model / max(mse_ref, 1e-12)

    if classifier_skill and return_skill > 0 and vbss > 0 and vauc > 0.50:
        threshold = choose_threshold(
            ensemble_v,
            pred_r_val,
            val["fwd_ret_exec"].values,
            base_rate,
        )
    else:
        threshold = 1.0  # CASH

    # Reentrenar únicamente los modelos habilitados, ahora con toda la historia conocida.
    Xh = hist[features]
    yh = hist["y_up_exec"].astype(int)

    for name, tmpl in templates.items():
        m = clone(tmpl)
        m.fit(Xh, yh)
        trained[name] = m

    rr_final = clone(ridge_template())
    rr_final.fit(Xh, hist["fwd_ret_exec"].values)

    return FitState(
        classifiers=trained,
        ridge=rr_final,
        weights=weights,
        threshold=threshold,
        base_rate=base_rate,
        classifier_skill=classifier_skill,
        return_skill=float(return_skill),
        val_brier=float(vb),
        val_brier_ref=float(brier_ref),
        val_bss=float(vbss),
        val_auc=float(vauc),
        val_accuracy=float(vacc),
        val_always_up_accuracy=float(always_up_acc),
        train_start=hist.index.min(),
        train_end=hist.index.max(),
    )

# -------------------------- WALK FORWARD -------------------------------

def position_from_signal(
    p: float,
    pred_ret: float,
    threshold: float,
    base_rate: float,
    return_skill: float,
    annual_vol: float,
) -> float:
    if threshold >= 0.999:
        return 0.0
    if not np.isfinite(p) or not np.isfinite(pred_ret):
        return 0.0
    if return_skill <= 0:
        return 0.0

    # Margen económico mínimo: costos + fracción del riesgo de 5 sesiones.
    if np.isfinite(annual_vol):
        five_day_sigma = annual_vol / math.sqrt(252) * math.sqrt(HORIZON)
    else:
        five_day_sigma = 0.0

    required_return = max(
        ROUND_TRIP_COST * 1.25,
        ROUND_TRIP_COST + 0.10 * five_day_sigma,
    )

    required_prob = max(threshold, base_rate + 0.02)

    if p < required_prob or pred_ret <= required_return:
        return 0.0

    edge = p - required_prob

    if edge < 0.04:
        return 0.10
    if edge < 0.08:
        return 0.20
    return MAX_POSITION

def walk_forward(asset: str, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    exclude = {"price", "fwd_ret_exec", "y_up_exec"}
    features = [c for c in df.columns if c not in exclude]

    test_positions = np.flatnonzero(df.index >= pd.Timestamp(TEST_START))

    rows = []
    audit_rows = []
    state = None
    last_month = None

    for pos in test_positions:
        date = df.index[pos]
        if not np.isfinite(df.iloc[pos]["price"]):
            continue

        month = (date.year, date.month)
        if state is None or month != last_month:
            try:
                state = fit_state(df, pos, features)
                last_month = month
            except ValueError:
                continue

            ar = {
                "date": date,
                "asset": asset,
                "threshold": state.threshold,
                "base_rate": state.base_rate,
                "classifier_skill": state.classifier_skill,
                "return_skill": state.return_skill,
                "val_brier": state.val_brier,
                "val_brier_ref": state.val_brier_ref,
                "val_bss": state.val_bss,
                "val_auc": state.val_auc,
                "val_accuracy": state.val_accuracy,
                "val_always_up_accuracy": state.val_always_up_accuracy,
                "train_start": state.train_start,
                "train_end": state.train_end,
            }
            ar.update({f"w_{k}": v for k, v in state.weights.items()})
            audit_rows.append(ar)

        x = df.iloc[[pos]][features]
        model_probs = {
            k: float(state.classifiers[k].predict_proba(x)[:, 1][0])
            for k in state.classifiers
        }

        if state.classifier_skill and sum(state.weights.values()) > 0:
            p = float(sum(state.weights[k] * model_probs[k] for k in model_probs))
        else:
            p = state.base_rate

        pred_ret = float(state.ridge.predict(x)[0])

        vol = df.iloc[pos].get("self_vol_20", np.nan)
        position = position_from_signal(
            p=p,
            pred_ret=pred_ret,
            threshold=state.threshold,
            base_rate=state.base_rate,
            return_skill=state.return_skill,
            annual_vol=float(vol) if np.isfinite(vol) else np.nan,
        )

        rows.append({
            "date": date,
            "asset": asset,
            "price": float(df.iloc[pos]["price"]),
            "p_up": p,
            "base_rate": state.base_rate,
            "pred_fwd_ret_exec": pred_ret,
            "threshold": state.threshold,
            "return_skill": state.return_skill,
            "signal_position": position,
            "actual_fwd_ret_exec": (
                float(df.iloc[pos]["fwd_ret_exec"])
                if np.isfinite(df.iloc[pos]["fwd_ret_exec"]) else np.nan
            ),
            "actual_up_exec": (
                float(df.iloc[pos]["y_up_exec"])
                if np.isfinite(df.iloc[pos]["y_up_exec"]) else np.nan
            ),
            **{f"p_{k}": v for k, v in model_probs.items()},
        })

    pred = pd.DataFrame(rows)
    if len(pred):
        pred = pred.set_index("date")
    return pred, pd.DataFrame(audit_rows)

# --------------------------- PORTFOLIO --------------------------------

def build_portfolio(
    predictions: Dict[str, pd.DataFrame],
    raw: Dict[str, pd.Series],
) -> pd.DataFrame:

    idx = sorted(set().union(*[
        set(p.index) for p in predictions.values() if len(p)
    ]))
    out = pd.DataFrame(index=pd.DatetimeIndex(idx))

    for asset, p in predictions.items():
        ret = raw[asset].pct_change(fill_method=None).reindex(out.index).fillna(0.0)

        signal = p["signal_position"].reindex(out.index).ffill().fillna(0.0)

        # ret[d] mide cierre(d-1)->cierre(d).
        # señal en t, ejecución al cierre t+1:
        # primer retorno capturable es t+1 -> t+2, por eso shift(2).
        pos = signal.shift(2).fillna(0.0)

        out[f"pos_{asset}"] = pos
        out[f"ret_{asset}"] = ret

    pos_cols = [c for c in out.columns if c.startswith("pos_")]
    total = out[pos_cols].sum(axis=1)
    scale = np.where(total > 0.90, 0.90 / total, 1.0)
    for c in pos_cols:
        out[c] *= scale

    gross = pd.Series(0.0, index=out.index)
    costs = pd.Series(0.0, index=out.index)

    for asset in predictions:
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

# ---------------------------- METRICS ---------------------------------

def max_drawdown(ret: pd.Series) -> float:
    curve = (1 + ret.fillna(0)).cumprod()
    dd = curve / curve.cummax() - 1
    return float(dd.min())

def portfolio_metrics(ret: pd.Series, name: str) -> dict:
    r = ret.dropna()
    if len(r) == 0:
        return {"name": name}

    total_return = (1 + r).prod() - 1
    cagr = (1 + total_return) ** (252 / max(len(r), 1)) - 1
    ann_vol = r.std() * math.sqrt(252)
    sharpe = r.mean() * 252 / ann_vol if ann_vol > 0 else np.nan
    downside = r[r < 0].std() * math.sqrt(252)
    sortino = r.mean() * 252 / downside if downside and downside > 0 else np.nan

    return {
        "name": name,
        "observations": len(r),
        "total_return": total_return,
        "cagr": cagr,
        "ann_vol": ann_vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_drawdown(r),
    }

def prediction_metrics(pred: pd.DataFrame, asset: str) -> dict:
    d = pred.dropna(subset=["actual_up_exec", "actual_fwd_ret_exec"]).copy()
    if len(d) == 0:
        return {"name": f"{asset}_prediction"}

    y = d["actual_up_exec"].astype(int)
    p = d["p_up"]

    base_rate = float(y.mean())
    always_up_acc = max(base_rate, 1 - base_rate)
    brier = brier_score_loss(y, p)
    brier_ref = brier_score_loss(y, np.full(len(y), base_rate))
    bss = 1 - brier / max(brier_ref, 1e-9)

    try:
        auc = roc_auc_score(y, p)
    except Exception:
        auc = np.nan

    active = d["signal_position"] > 0

    return {
        "name": f"{asset}_prediction",
        "observations": len(d),
        "actual_up_rate": base_rate,
        "always_up_accuracy": always_up_acc,
        "directional_accuracy_50": accuracy_score(y, p >= 0.5),
        "brier": brier,
        "brier_ref": brier_ref,
        "brier_skill": bss,
        "auc": auc,
        "active_signal_rate": active.mean(),
        "mean_actual_exec_ret_when_active": (
            d.loc[active, "actual_fwd_ret_exec"].mean()
            if active.any() else np.nan
        ),
    }

# ------------------------------ MAIN ----------------------------------

def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    raw = download_all()

    predictions = {}
    audits = []
    metrics = []

    for asset in TARGETS:
        print("\n" + "=" * 80)
        print("WALK-FORWARD CORREGIDO:", asset)

        df = build_frame(asset, raw)
        pred, audit = walk_forward(asset, df)

        predictions[asset] = pred
        pred.to_csv(OUTPUT_DIR / f"predictions_{asset}.csv")

        if len(audit):
            audits.append(audit)

        metrics.append(prediction_metrics(pred, asset))

        if len(pred):
            cols = [
                "price", "p_up", "base_rate",
                "pred_fwd_ret_exec", "threshold",
                "return_skill", "signal_position"
            ]
            print(pred.tail(8)[cols])

    portfolio = build_portfolio(predictions, raw)
    portfolio.to_csv(OUTPUT_DIR / "portfolio_daily.csv")

    metrics.append(
        portfolio_metrics(portfolio["portfolio_ret_net"], "MFP3_v14_portfolio")
    )

    # Benchmark 30/30/30
    bench = pd.Series(0.0, index=portfolio.index)
    for asset in TARGETS:
        r = raw[asset].pct_change(fill_method=None).reindex(portfolio.index).fillna(0.0)
        bench += 0.30 * r
    metrics.append(portfolio_metrics(bench, "Benchmark_30_30_30"))

    # CASH
    metrics.append(portfolio_metrics(
        pd.Series(0.0, index=portfolio.index),
        "Cash_0pct"
    ))

    for asset in TARGETS:
        r = raw[asset].pct_change(fill_method=None).reindex(portfolio.index).fillna(0.0)
        metrics.append(portfolio_metrics(r, f"BuyHold_{asset}"))

    mdf = pd.DataFrame(metrics)
    mdf.to_csv(OUTPUT_DIR / "metrics.csv", index=False)

    if audits:
        pd.concat(audits, ignore_index=True).to_csv(
            OUTPUT_DIR / "validation_audit.csv",
            index=False
        )

    print("\n" + "=" * 80)
    print("MÉTRICAS v1.4")
    with pd.option_context("display.max_columns", None, "display.width", 180):
        print(mdf)

    final_capital = portfolio["capital"].iloc[-1]
    print("\nCapital inicial: $10,000,000")
    print("Capital final v1.4:", f"${final_capital:,.0f}")
    print("Salida:", OUTPUT_DIR.resolve())

    # Clasificación provisional; Champion sólo después del Time Machine Tournament.
    row = mdf.loc[mdf["name"] == "MFP3_v14_portfolio"]
    if len(row):
        tr = float(row.iloc[0].get("total_return", np.nan))
        sh = float(row.iloc[0].get("sharpe", np.nan))
        dd = float(row.iloc[0].get("max_drawdown", np.nan))

        if np.isfinite(tr) and np.isfinite(sh) and tr > 0 and sh > 0 and dd > -0.20:
            status = "CANDIDATE - debe pasar Time Machine Tournament"
        else:
            status = "REJECT - no cumple mínimos absolutos"

        print("Estado provisional:", status)

if __name__ == "__main__":
    main()
