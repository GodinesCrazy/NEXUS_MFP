#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MFP-3 Adaptive v1.3 - Postprocesador Champion/Challenger + Regime Engine

Se ejecuta DESPUES de mfp3_adaptive_v1_2.py.

Lee:
  mfp3_output/metrics.csv
  mfp3_output/portfolio_daily.csv
  mfp3_output/model_weights.csv   (si existe)

Crea:
  mfp3_output/regime_daily.csv
  mfp3_output/regime_performance.csv
  mfp3_output/experiment_registry.csv
  mfp3_output/champion.json
  mfp3_output/model_graveyard.csv

Objetivo:
- clasificar cada fecha por régimen de mercado,
- medir cómo funciona MFP-3 en cada régimen,
- registrar cada corrida como experimento reproducible,
- promover/desechar modelos con reglas objetivas.

No ejecuta operaciones reales.
"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

OUTPUT = Path("mfp3_output")

FRED = {
    "VIX": "VIXCLS",
    "NASDAQ": "NASDAQCOM",
    "US10Y": "DGS10",
    "US2Y": "DGS2",
    "WTI": "DCOILWTICO",
    "USD_BROAD": "DTWEXBGS",
}

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"

# -------------------------- utilidades ---------------------------------

def read_fred(sid: str) -> pd.Series:
    df = pd.read_csv(FRED_URL.format(sid=sid))
    dcol, vcol = df.columns[0], df.columns[1]
    df[dcol] = pd.to_datetime(df[dcol])
    df[vcol] = pd.to_numeric(df[vcol], errors="coerce")
    return df.set_index(dcol)[vcol].sort_index()

def max_drawdown(ret: pd.Series) -> float:
    curve = (1 + ret.fillna(0)).cumprod()
    dd = curve / curve.cummax() - 1
    return float(dd.min())

def safe_float(x):
    try:
        if pd.isna(x):
            return None
        return float(x)
    except Exception:
        return None

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

# --------------------------- regímenes --------------------------------

def build_regimes(index: pd.DatetimeIndex) -> pd.DataFrame:
    raw = {}
    for name, sid in FRED.items():
        print(f"Descargando régimen: {name:10s} {sid}")
        raw[name] = read_fred(sid).reindex(index).ffill(limit=5)

    r = pd.DataFrame(index=index)
    r["vix"] = raw["VIX"]
    r["nasdaq_ret20"] = raw["NASDAQ"].pct_change(20, fill_method=None)
    r["wti_ret20"] = raw["WTI"].pct_change(20, fill_method=None)
    r["usd_ret20"] = raw["USD_BROAD"].pct_change(20, fill_method=None)
    r["curve_10y_2y"] = raw["US10Y"] - raw["US2Y"]

    # Reglas simples y transparentes. Luego pueden reemplazarse por clustering/HMM.
    regime = pd.Series("NEUTRAL", index=index, dtype="object")

    risk_off = (r["vix"] >= 25) | (r["nasdaq_ret20"] <= -0.08)
    risk_on = (r["vix"] < 18) & (r["nasdaq_ret20"] > 0.03)
    inflationary = (r["wti_ret20"] > 0.08) & (r["curve_10y_2y"] > -0.25)
    usd_shock = r["usd_ret20"] > 0.03

    regime.loc[risk_on] = "RISK_ON"
    regime.loc[inflationary] = "INFLATIONARY"
    regime.loc[usd_shock & ~risk_off] = "USD_STRENGTH"
    regime.loc[risk_off] = "RISK_OFF"

    r["regime"] = regime
    return r

# ----------------------- rendimiento por régimen -----------------------

def regime_performance(port: pd.DataFrame, regimes: pd.DataFrame) -> pd.DataFrame:
    z = port.join(regimes[["regime"]], how="left")
    rows = []
    for reg, g in z.groupby("regime"):
        rr = g["portfolio_ret_net"].dropna()
        if len(rr) == 0:
            continue
        ann_vol = rr.std() * np.sqrt(252)
        sharpe = (rr.mean() * 252 / ann_vol) if ann_vol > 0 else np.nan
        rows.append({
            "regime": reg,
            "days": len(rr),
            "total_return": (1 + rr).prod() - 1,
            "avg_daily_return": rr.mean(),
            "ann_vol": ann_vol,
            "sharpe": sharpe,
            "max_drawdown": max_drawdown(rr),
            "positive_day_rate": (rr > 0).mean(),
        })
    return pd.DataFrame(rows).sort_values("regime")

# ---------------------- registro experimental --------------------------

def build_experiment_record(metrics: pd.DataFrame, port: pd.DataFrame) -> dict:
    row = metrics.loc[metrics["name"] == "MFP3_portfolio"]
    if len(row):
        m = row.iloc[0]
    else:
        rr = port["portfolio_ret_net"]
        ann_vol = rr.std() * np.sqrt(252)
        m = pd.Series({
            "total_return": (1 + rr).prod() - 1,
            "cagr": (1 + rr).prod() ** (252 / max(len(rr), 1)) - 1,
            "sharpe": rr.mean() * 252 / ann_vol if ann_vol > 0 else np.nan,
            "max_drawdown": max_drawdown(rr),
        })

    # Fitness conservador: favorece retorno/Sharpe y castiga drawdown.
    total_return = safe_float(m.get("total_return")) or 0.0
    sharpe = safe_float(m.get("sharpe")) or 0.0
    mdd = abs(safe_float(m.get("max_drawdown")) or 0.0)
    fitness = total_return + 0.20 * sharpe - 0.75 * mdd

    return {
        "timestamp_utc": datetime.utcnow().isoformat(timespec="seconds"),
        "version": "MFP-3_v1.2",
        "test_start": str(port.index.min().date()),
        "test_end": str(port.index.max().date()),
        "capital_initial": 10_000_000,
        "capital_final": safe_float(port["capital"].iloc[-1]),
        "total_return": total_return,
        "cagr": safe_float(m.get("cagr")),
        "sharpe": sharpe,
        "sortino": safe_float(m.get("sortino")),
        "max_drawdown": safe_float(m.get("max_drawdown")),
        "fitness": fitness,
    }

def promotion_decision(candidate: dict, champion: dict | None) -> tuple[str, str]:
    if champion is None:
        return "PROMOTE", "Primer modelo registrado"

    # Reglas mínimas. No basta con mayor rentabilidad.
    cfit = candidate.get("fitness", -999)
    ofit = champion.get("fitness", -999)

    candidate_mdd = abs(candidate.get("max_drawdown") or 999)
    champ_mdd = abs(champion.get("max_drawdown") or 999)
    candidate_sharpe = candidate.get("sharpe") or -999
    champ_sharpe = champion.get("sharpe") or -999

    if cfit <= ofit:
        return "REJECT", "Fitness no supera al Champion"
    if candidate_sharpe < champ_sharpe * 0.95:
        return "REJECT", "Mejora aparente, pero Sharpe empeora demasiado"
    if candidate_mdd > champ_mdd * 1.15:
        return "REJECT", "Drawdown empeora más de 15%"

    return "PROMOTE", "Supera fitness sin deterioro material de riesgo"

# ------------------------------- main ---------------------------------

def main():
    if not OUTPUT.exists():
        raise SystemExit("No existe mfp3_output. Ejecuta primero mfp3_adaptive_v1_2.py")

    metrics_path = OUTPUT / "metrics.csv"
    port_path = OUTPUT / "portfolio_daily.csv"

    if not metrics_path.exists() or not port_path.exists():
        raise SystemExit("Faltan metrics.csv o portfolio_daily.csv; espera a que termine v1.2")

    metrics = pd.read_csv(metrics_path)
    port = pd.read_csv(port_path, parse_dates=[0], index_col=0).sort_index()

    print("\nConstruyendo Regime Engine...")
    regimes = build_regimes(port.index)
    regimes.to_csv(OUTPUT / "regime_daily.csv")

    rp = regime_performance(port, regimes)
    rp.to_csv(OUTPUT / "regime_performance.csv", index=False)

    record = build_experiment_record(metrics, port)
    record["metrics_sha256"] = sha256_file(metrics_path)
    record["portfolio_sha256"] = sha256_file(port_path)

    registry_path = OUTPUT / "experiment_registry.csv"
    if registry_path.exists():
        registry = pd.read_csv(registry_path)
    else:
        registry = pd.DataFrame()

    champion_path = OUTPUT / "champion.json"
    champion = None
    if champion_path.exists():
        champion = json.loads(champion_path.read_text(encoding="utf-8"))

    decision, reason = promotion_decision(record, champion)
    record["decision"] = decision
    record["reason"] = reason

    registry = pd.concat([registry, pd.DataFrame([record])], ignore_index=True)
    registry.to_csv(registry_path, index=False)

    graveyard_path = OUTPUT / "model_graveyard.csv"
    if decision == "PROMOTE":
        champion_path.write_text(
            json.dumps(record, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    else:
        if graveyard_path.exists():
            gy = pd.read_csv(graveyard_path)
        else:
            gy = pd.DataFrame()
        gy = pd.concat([gy, pd.DataFrame([record])], ignore_index=True)
        gy.to_csv(graveyard_path, index=False)

    print("\n" + "=" * 72)
    print("MFP-3 v1.3 POSTPROCESS")
    print("=" * 72)
    print("Decisión :", decision)
    print("Motivo   :", reason)
    print("Capital final :", f"${record['capital_final']:,.0f}" if record["capital_final"] else "N/D")
    print("Retorno total :", f"{record['total_return']:.2%}")
    print("Sharpe        :", f"{record['sharpe']:.3f}")
    print("Max drawdown  :", f"{record['max_drawdown']:.2%}" if record["max_drawdown"] is not None else "N/D")
    print("Fitness       :", f"{record['fitness']:.4f}")

    print("\nRendimiento por régimen:")
    with pd.option_context("display.max_columns", None, "display.width", 150):
        print(rp)

    print("\nArchivos actualizados en:", OUTPUT.resolve())

if __name__ == "__main__":
    main()
