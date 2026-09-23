#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MFP-3 v1.7-FROZEN — FORWARD PAPER RECORDER
===========================================

Objetivo:
- NO modifica el modelo v1.7.
- Lee sus señales actuales desde:
      mfp3_output_v17/current_signals.csv
- Mantiene una cartera paper persistente en CLP.
- Cada ejecución:
    1) descarga precios actuales/cierres más recientes;
    2) valora la cartera existente;
    3) si hay una nueva señal de v1.7, rebalancea;
    4) descuenta costos simulados;
    5) guarda un snapshot inmutable en CSV/JSONL.

Importante:
- No ejecuta órdenes reales.
- Permite fracciones de ETF para medir el modelo sin ruido de redondeo.
- Coste base: 0,15% por lado.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    raise SystemExit(
        "\nFalta yfinance.\nEjecuta:\n"
        "  py -m pip install yfinance\n"
    )

# ------------------------------ CONFIG --------------------------------

INITIAL_CAPITAL_CLP = 10_000_000.0
ONE_WAY_COST = 0.0015

ROOT = Path(".")
SIGNALS_FILE = ROOT / "mfp3_output_v17" / "current_signals.csv"
FROZEN_MODEL_FILE = ROOT / "mfp3_meta_learning_v1_7.py"

OUT = ROOT / "mfp3_forward_v17"
STATE_FILE = OUT / "state.json"
LEDGER_FILE = OUT / "ledger.csv"
EVENT_LOG = OUT / "rebalance_events.jsonl"
MODEL_FINGERPRINT = OUT / "frozen_model_fingerprint.json"

ASSETS = ["QQQ", "ECH", "CPER"]
FX = "CLP=X"

# ----------------------------- HELPERS --------------------------------

def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def load_latest_prices() -> Dict[str, float]:
    tickers = ASSETS + [FX]
    raw = yf.download(
        tickers,
        period="10d",
        auto_adjust=True,
        progress=False,
        threads=True,
        group_by="column",
    )

    prices = {}

    for t in tickers:
        if isinstance(raw.columns, pd.MultiIndex):
            l0 = raw.columns.get_level_values(0)
            l1 = raw.columns.get_level_values(1)

            if t in l0:
                d = raw[t]
            elif t in l1:
                d = raw.xs(t, axis=1, level=1)
            else:
                raise RuntimeError(f"No se encontró {t} en Yahoo.")
        else:
            d = raw

        close = pd.to_numeric(d["Close"], errors="coerce").dropna()
        if close.empty:
            raise RuntimeError(f"Sin precio reciente para {t}.")
        prices[t] = float(close.iloc[-1])

    return prices

def read_signals() -> pd.DataFrame:
    if not SIGNALS_FILE.exists():
        raise SystemExit(
            f"\nNo existe {SIGNALS_FILE}.\n"
            "Ejecuta primero la v1.7-FROZEN para generar current_signals.csv.\n"
        )

    df = pd.read_csv(SIGNALS_FILE)
    required = {"date", "asset", "target_portfolio_weight"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(
            f"current_signals.csv no tiene columnas esperadas: {missing}"
        )

    df["date"] = pd.to_datetime(df["date"])
    df = df[df["asset"].isin(ASSETS)].copy()
    return df

def signal_id(df: pd.DataFrame) -> str:
    z = df[["date", "asset", "target_portfolio_weight"]].copy()
    z["date"] = z["date"].astype(str)
    txt = z.sort_values("asset").to_csv(index=False)
    return hashlib.sha256(txt.encode("utf-8")).hexdigest()

def blank_state() -> dict:
    return {
        "created_at_utc": now_utc(),
        "cash_clp": INITIAL_CAPITAL_CLP,
        "shares": {a: 0.0 for a in ASSETS},
        "last_signal_id": None,
        "last_signal_date": None,
        "cumulative_cost_clp": 0.0,
        "initial_capital_clp": INITIAL_CAPITAL_CLP,
    }

def load_state() -> dict:
    if not STATE_FILE.exists():
        return blank_state()
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))

def save_state(state: dict):
    STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

def portfolio_value(state: dict, prices: Dict[str, float]) -> float:
    fx = prices[FX]
    invested = sum(
        float(state["shares"].get(a, 0.0)) * prices[a] * fx
        for a in ASSETS
    )
    return float(state["cash_clp"]) + invested

def append_jsonl(path: Path, obj: dict):
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")

def append_ledger(row: dict):
    exists = LEDGER_FILE.exists()
    with LEDGER_FILE.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not exists:
            w.writeheader()
        w.writerow(row)

# --------------------------- REBALANCE --------------------------------

def rebalance(
    state: dict,
    signals: pd.DataFrame,
    prices: Dict[str, float],
) -> dict:

    before_value = portfolio_value(state, prices)
    fx = prices[FX]

    targets = {
        r.asset: float(r.target_portfolio_weight)
        for r in signals.itertuples()
    }

    # Seguridad: pesos negativos no, total <= 100%.
    targets = {a: max(0.0, targets.get(a, 0.0)) for a in ASSETS}
    total_target = sum(targets.values())
    if total_target > 1.0 + 1e-9:
        raise RuntimeError(
            f"Pesos objetivo suman {total_target:.3f}; supera 100%."
        )

    current_values = {
        a: float(state["shares"].get(a, 0.0)) * prices[a] * fx
        for a in ASSETS
    }
    desired_values = {
        a: before_value * targets[a]
        for a in ASSETS
    }

    trades = {}
    total_cost = 0.0

    # Primero estimamos costos de todos los cambios.
    for a in ASSETS:
        delta_clp = desired_values[a] - current_values[a]
        cost = abs(delta_clp) * ONE_WAY_COST
        trades[a] = {
            "current_value_clp": current_values[a],
            "desired_value_clp": desired_values[a],
            "delta_value_clp": delta_clp,
            "cost_clp": cost,
        }
        total_cost += cost

    # Ajustar el valor invertible por el costo para no crear dinero.
    net_value = max(0.0, before_value - total_cost)
    desired_values = {
        a: net_value * targets[a]
        for a in ASSETS
    }

    new_shares = {
        a: desired_values[a] / (prices[a] * fx)
        for a in ASSETS
    }
    invested = sum(desired_values.values())
    new_cash = net_value - invested

    state["shares"] = new_shares
    state["cash_clp"] = float(new_cash)
    state["cumulative_cost_clp"] = (
        float(state.get("cumulative_cost_clp", 0.0)) + total_cost
    )

    return {
        "portfolio_before_clp": before_value,
        "portfolio_after_clp": net_value,
        "cost_clp": total_cost,
        "targets": targets,
        "trades": trades,
    }

# ------------------------------- MAIN ---------------------------------

def main():
    OUT.mkdir(exist_ok=True)

    prices = load_latest_prices()
    signals = read_signals()
    sid = signal_id(signals)
    latest_signal_date = signals["date"].max().date().isoformat()

    # Congelar huella de código la primera vez.
    if not MODEL_FINGERPRINT.exists():
        fp = {
            "created_at_utc": now_utc(),
            "model_file": str(FROZEN_MODEL_FILE),
            "sha256": sha256(FROZEN_MODEL_FILE),
            "signals_file": str(SIGNALS_FILE),
            "note": "Huella de v1.7-FROZEN. No modificar durante forward paper.",
        }
        MODEL_FINGERPRINT.write_text(
            json.dumps(fp, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    state = load_state()

    pre_value = portfolio_value(state, prices)
    rebalance_info = None

    if state.get("last_signal_id") != sid:
        rebalance_info = rebalance(state, signals, prices)
        state["last_signal_id"] = sid
        state["last_signal_date"] = latest_signal_date

        append_jsonl(
            EVENT_LOG,
            {
                "recorded_at_utc": now_utc(),
                "signal_date": latest_signal_date,
                "signal_id": sid,
                "prices": prices,
                **rebalance_info,
            },
        )

    post_value = portfolio_value(state, prices)

    fx = prices[FX]
    values = {
        a: float(state["shares"].get(a, 0.0)) * prices[a] * fx
        for a in ASSETS
    }

    row = {
        "recorded_at_utc": now_utc(),
        "signal_date": state.get("last_signal_date"),
        "signal_id": state.get("last_signal_id"),
        "qqq_usd": prices["QQQ"],
        "ech_usd": prices["ECH"],
        "cper_usd": prices["CPER"],
        "usdclp": prices[FX],
        "qqq_value_clp": values["QQQ"],
        "ech_value_clp": values["ECH"],
        "cper_value_clp": values["CPER"],
        "cash_clp": float(state["cash_clp"]),
        "portfolio_value_clp": post_value,
        "cumulative_cost_clp": float(state["cumulative_cost_clp"]),
        "return_since_start": (
            post_value / float(state["initial_capital_clp"]) - 1.0
        ),
        "rebalanced_this_run": bool(rebalance_info is not None),
        "frozen_model_sha256": sha256(FROZEN_MODEL_FILE),
    }

    append_ledger(row)
    save_state(state)

    print("\n" + "=" * 82)
    print("MFP-3 v1.7-FROZEN — FORWARD PAPER")
    print("=" * 82)
    print("Señal vigente :", latest_signal_date)
    print("Rebalanceo    :", "SÍ" if rebalance_info else "NO")
    print(f"USD/CLP       : {prices[FX]:,.4f}")
    print(f"QQQ           : USD {prices['QQQ']:,.4f}")
    print(f"ECH           : USD {prices['ECH']:,.4f}")
    print(f"CPER          : USD {prices['CPER']:,.4f}")
    print()
    print(f"QQQ valor     : ${values['QQQ']:,.0f} CLP")
    print(f"ECH valor     : ${values['ECH']:,.0f} CLP")
    print(f"CPER valor    : ${values['CPER']:,.0f} CLP")
    print(f"CASH          : ${float(state['cash_clp']):,.0f} CLP")
    print("-" * 42)
    print(f"CARTERA       : ${post_value:,.0f} CLP")
    print(f"Retorno       : {row['return_since_start']:+.3%}")
    print(f"Costos acum.  : ${float(state['cumulative_cost_clp']):,.0f} CLP")
    print("\nLedger:", LEDGER_FILE.resolve())
    print("No ejecuta operaciones reales.")

if __name__ == "__main__":
    main()
