#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MFP-3 ONE FILE v1.8
===================

UN SOLO ARCHIVO PARA TODO EL SISTEMA.

Uso diario:
    py mfp3_onefile_v1_8.py

Opciones:
    py mfp3_onefile_v1_8.py --full
    py mfp3_onefile_v1_8.py --status

Funciones:
1) actualiza v1.7-FROZEN si hace falta;
2) actualiza Forward Paper;
3) recolecta noticias y contexto macro/mercado;
4) etiqueta noticias con retornos futuros a 1, 5 y 20 sesiones;
5) genera reporte consolidado.

No ejecuta operaciones reales.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import traceback
import zlib
from datetime import datetime, timezone, time
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

try:
    import yfinance as yf
except ImportError:
    raise SystemExit(
        "\nFalta yfinance. Ejecuta una sola vez:\n"
        "  py -m pip install yfinance\n"
    )

V17_B64 = """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"""
EVENTS_B64 = """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"""

def embedded_source(blob: str) -> str:
    return zlib.decompress(base64.b64decode(blob)).decode("utf-8")

FROZEN_V17_SOURCE = embedded_source(V17_B64)
EVENT_COLLECTOR_SOURCE = embedded_source(EVENTS_B64)

FROZEN_V17_SHA256 = hashlib.sha256(
    FROZEN_V17_SOURCE.encode("utf-8")
).hexdigest()

EVENT_COLLECTOR_SHA256 = hashlib.sha256(
    EVENT_COLLECTOR_SOURCE.encode("utf-8")
).hexdigest()

ROOT = Path(".")
V17_OUT = ROOT / "mfp3_output_v17"
V17_SIGNALS = V17_OUT / "current_signals.csv"

FORWARD_OUT = ROOT / "mfp3_forward_v17"
FORWARD_STATE = FORWARD_OUT / "state.json"
FORWARD_LEDGER = FORWARD_OUT / "ledger.csv"
FORWARD_EVENTS = FORWARD_OUT / "rebalance_events.jsonl"

EVENT_OUT = ROOT / "mfp3_event_intelligence"
RAW_EVENTS = EVENT_OUT / "events_raw.jsonl"
EVENT_OUTCOMES = EVENT_OUT / "event_outcomes.csv"
EVENT_SUMMARY = EVENT_OUT / "event_learning_summary.csv"

MASTER_OUT = ROOT / "mfp3_master"
MANIFEST = MASTER_OUT / "manifest.json"
DAILY_REPORT = MASTER_OUT / "daily_report.csv"

INITIAL_CAPITAL_CLP = 10_000_000.0
ONE_WAY_COST = 0.0015
ASSETS = ["QQQ", "ECH", "CPER"]
FX = "CLP=X"

def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def local_today():
    return datetime.now().date()

def run_embedded(source: str, module_name: str):
    g = {
        "__name__": module_name,
        "__file__": f"<embedded:{module_name}>",
        "__builtins__": __builtins__,
    }
    exec(compile(source, g["__file__"], "exec"), g, g)
    if "main" not in g:
        raise RuntimeError(f"El módulo embebido {module_name} no contiene main().")
    g["main"]()

def latest_signal_date():
    if not V17_SIGNALS.exists():
        return None
    try:
        df = pd.read_csv(V17_SIGNALS)
        if "date" not in df or df.empty:
            return None
        return pd.to_datetime(df["date"]).max().date()
    except Exception:
        return None

def v17_needs_refresh(force=False) -> bool:
    if force:
        return True
    d = latest_signal_date()
    return d != local_today()

def write_manifest():
    MASTER_OUT.mkdir(exist_ok=True)
    manifest = {
        "created_or_checked_at_utc": now_utc(),
        "system": "MFP-3 ONE FILE v1.8",
        "frozen_v17_sha256": FROZEN_V17_SHA256,
        "event_collector_sha256": EVENT_COLLECTOR_SHA256,
        "frozen_policy": (
            "La arquitectura v1.7 embebida no cambia durante forward paper. "
            "Los nuevos aprendizajes de noticias pertenecen al Challenger."
        ),
    }
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

def latest_prices() -> Dict[str, float]:
    raw = yf.download(
        ASSETS + [FX],
        period="10d",
        auto_adjust=True,
        progress=False,
        threads=True,
        group_by="column",
    )

    out = {}
    for t in ASSETS + [FX]:
        if isinstance(raw.columns, pd.MultiIndex):
            l0 = raw.columns.get_level_values(0)
            l1 = raw.columns.get_level_values(1)
            if t in l0:
                d = raw[t]
            elif t in l1:
                d = raw.xs(t, axis=1, level=1)
            else:
                raise RuntimeError(f"No aparece {t} en descarga.")
        else:
            d = raw

        close = pd.to_numeric(d["Close"], errors="coerce").dropna()
        if close.empty:
            raise RuntimeError(f"Sin precio reciente para {t}.")
        out[t] = float(close.iloc[-1])

    return out

def load_current_signals() -> pd.DataFrame:
    if not V17_SIGNALS.exists():
        raise RuntimeError("No existe current_signals.csv.")

    df = pd.read_csv(V17_SIGNALS)
    required = {"date", "asset", "target_portfolio_weight"}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Faltan columnas de señal: {missing}")

    df["date"] = pd.to_datetime(df["date"])
    return df[df["asset"].isin(ASSETS)].copy()

def signal_id(df: pd.DataFrame) -> str:
    z = df[["date", "asset", "target_portfolio_weight"]].copy()
    z["date"] = z["date"].astype(str)
    txt = z.sort_values("asset").to_csv(index=False)
    return hashlib.sha256(txt.encode("utf-8")).hexdigest()

def blank_forward_state() -> dict:
    return {
        "created_at_utc": now_utc(),
        "cash_clp": INITIAL_CAPITAL_CLP,
        "shares": {a: 0.0 for a in ASSETS},
        "last_signal_id": None,
        "last_signal_date": None,
        "cumulative_cost_clp": 0.0,
        "initial_capital_clp": INITIAL_CAPITAL_CLP,
        "frozen_v17_sha256": FROZEN_V17_SHA256,
    }

def load_forward_state() -> dict:
    if not FORWARD_STATE.exists():
        return blank_forward_state()
    state = json.loads(FORWARD_STATE.read_text(encoding="utf-8"))
    state["frozen_v17_sha256"] = FROZEN_V17_SHA256
    return state

def save_forward_state(state: dict):
    FORWARD_STATE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

def forward_value(state: dict, prices: Dict[str, float]) -> float:
    fx = prices[FX]
    invested = sum(
        float(state["shares"].get(a, 0.0)) * prices[a] * fx
        for a in ASSETS
    )
    return float(state["cash_clp"]) + invested

def append_jsonl(path: Path, obj: dict):
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")

def append_csv_fixed(path: Path, row: dict):
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not exists:
            w.writeheader()
        w.writerow(row)

def rebalance_forward(state, signals, prices):
    before = forward_value(state, prices)
    fx = prices[FX]

    targets = {
        r.asset: max(0.0, float(r.target_portfolio_weight))
        for r in signals.itertuples()
    }
    targets = {a: targets.get(a, 0.0) for a in ASSETS}

    if sum(targets.values()) > 1.0 + 1e-9:
        raise RuntimeError("Pesos objetivo superan 100%.")

    current = {
        a: float(state["shares"].get(a, 0.0)) * prices[a] * fx
        for a in ASSETS
    }

    prelim_desired = {a: before * targets[a] for a in ASSETS}
    total_cost = sum(
        abs(prelim_desired[a] - current[a]) * ONE_WAY_COST
        for a in ASSETS
    )

    after_cost = max(0.0, before - total_cost)
    desired = {a: after_cost * targets[a] for a in ASSETS}

    state["shares"] = {
        a: desired[a] / (prices[a] * fx)
        for a in ASSETS
    }
    state["cash_clp"] = float(after_cost - sum(desired.values()))
    state["cumulative_cost_clp"] = (
        float(state.get("cumulative_cost_clp", 0.0)) + total_cost
    )

    return {
        "portfolio_before_clp": before,
        "portfolio_after_cost_clp": after_cost,
        "cost_clp": total_cost,
        "targets": targets,
    }

def run_forward_paper() -> dict:
    FORWARD_OUT.mkdir(exist_ok=True)

    prices = latest_prices()
    signals = load_current_signals()
    sid = signal_id(signals)
    signal_date = signals["date"].max().date().isoformat()

    state = load_forward_state()
    rebalanced = False

    if state.get("last_signal_id") != sid:
        rebal = rebalance_forward(state, signals, prices)
        state["last_signal_id"] = sid
        state["last_signal_date"] = signal_date
        rebalanced = True

        append_jsonl(
            FORWARD_EVENTS,
            {
                "recorded_at_utc": now_utc(),
                "signal_date": signal_date,
                "signal_id": sid,
                "frozen_v17_sha256": FROZEN_V17_SHA256,
                "prices": prices,
                **rebal,
            },
        )

    value = forward_value(state, prices)
    fx = prices[FX]
    asset_values = {
        a: float(state["shares"].get(a, 0.0)) * prices[a] * fx
        for a in ASSETS
    }

    row = {
        "recorded_at_utc": now_utc(),
        "signal_date": state.get("last_signal_date"),
        "signal_id": state.get("last_signal_id"),
        "frozen_v17_sha256": FROZEN_V17_SHA256,
        "qqq_usd": prices["QQQ"],
        "ech_usd": prices["ECH"],
        "cper_usd": prices["CPER"],
        "usdclp": prices[FX],
        "qqq_value_clp": asset_values["QQQ"],
        "ech_value_clp": asset_values["ECH"],
        "cper_value_clp": asset_values["CPER"],
        "cash_clp": float(state["cash_clp"]),
        "portfolio_value_clp": value,
        "cumulative_cost_clp": float(state["cumulative_cost_clp"]),
        "return_since_start": (
            value / float(state["initial_capital_clp"]) - 1
        ),
        "rebalanced_this_run": rebalanced,
    }

    append_csv_fixed(FORWARD_LEDGER, row)
    save_forward_state(state)
    return row

def read_raw_events() -> List[dict]:
    if not RAW_EVENTS.exists():
        return []

    out = []
    with RAW_EVENTS.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out

def market_history_for_event_learning(earliest_utc: datetime):
    start = (earliest_utc.date() - pd.Timedelta(days=5)).isoformat()

    raw = yf.download(
        ASSETS + [FX],
        start=start,
        auto_adjust=True,
        progress=False,
        threads=True,
        group_by="column",
    )

    series = {}
    for t in ASSETS + [FX]:
        if isinstance(raw.columns, pd.MultiIndex):
            l0 = raw.columns.get_level_values(0)
            l1 = raw.columns.get_level_values(1)
            if t in l0:
                d = raw[t]
            elif t in l1:
                d = raw.xs(t, axis=1, level=1)
            else:
                continue
        else:
            d = raw

        close = pd.to_numeric(d["Close"], errors="coerce").dropna()
        close.index = pd.to_datetime(close.index).tz_localize(None)
        series[t] = close

    if FX not in series:
        raise RuntimeError("No hay USD/CLP para etiquetar eventos.")

    out = {}
    fx = series[FX]

    for a in ASSETS:
        if a not in series:
            continue
        idx = series[a].index
        aligned_fx = fx.reindex(idx).ffill(limit=5)
        out[a] = series[a] * aligned_fx

    return out

def event_entry_date(retrieved_at_utc, trading_index):
    dt = pd.Timestamp(retrieved_at_utc)
    if dt.tzinfo is None:
        dt = dt.tz_localize("UTC")
    else:
        dt = dt.tz_convert("UTC")

    ny = dt.tz_convert("America/New_York")
    local_date = pd.Timestamp(ny.date())

    if ny.time() < time(16, 0) and local_date in trading_index:
        candidates = trading_index[trading_index >= local_date]
    else:
        candidates = trading_index[trading_index > local_date]

    if len(candidates) == 0:
        return None
    return candidates[0]

def sentiment_bucket(x):
    try:
        v = float(x)
    except Exception:
        return "neutral"
    if v > 0.20:
        return "positive"
    if v < -0.20:
        return "negative"
    return "neutral"

def update_event_outcomes() -> dict:
    events = read_raw_events()

    if not events:
        return {
            "events_total": 0,
            "outcome_rows": 0,
            "matured_1d": 0,
            "matured_5d": 0,
            "matured_20d": 0,
        }

    parsed_times = []
    for e in events:
        try:
            parsed_times.append(
                pd.Timestamp(e["retrieved_at_utc"]).to_pydatetime()
            )
        except Exception:
            pass

    if not parsed_times:
        return {"events_total": len(events), "outcome_rows": 0}

    history = market_history_for_event_learning(min(parsed_times))
    rows = []

    for e in events:
        if not e.get("retrieved_at_utc"):
            continue

        for asset in ASSETS:
            if asset not in history:
                continue

            px = history[asset].dropna()
            entry = event_entry_date(
                e["retrieved_at_utc"], px.index
            )
            if entry is None:
                continue

            loc = px.index.get_loc(entry)
            entry_px = float(px.iloc[loc])

            row = {
                "event_id": e.get("event_id"),
                "retrieved_at_utc": e.get("retrieved_at_utc"),
                "published_at_utc": e.get("published_at_utc"),
                "asset_tag": e.get("asset_tag"),
                "evaluated_asset": asset,
                "direct_match": int(
                    e.get("asset_tag") in {asset, "GLOBAL"}
                ),
                "query": e.get("query"),
                "source": e.get("source"),
                "title": e.get("title"),
                "lexical_sentiment": e.get("lexical_sentiment", 0.0),
                "sentiment_bucket": sentiment_bucket(
                    e.get("lexical_sentiment", 0.0)
                ),
                "impact_keyword_hits": e.get("impact_keyword_hits", 0),
                "entry_session": entry.date().isoformat(),
                "entry_price_clp": entry_px,
            }

            for h in [1, 5, 20]:
                if loc + h < len(px):
                    exit_px = float(px.iloc[loc + h])
                    row[f"ret_{h}s"] = exit_px / entry_px - 1
                    row[f"matured_{h}s"] = 1
                else:
                    row[f"ret_{h}s"] = np.nan
                    row[f"matured_{h}s"] = 0

            rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(
        EVENT_OUTCOMES,
        index=False,
        encoding="utf-8-sig",
    )

    summaries = []
    if not df.empty:
        group_cols = [
            "asset_tag",
            "evaluated_asset",
            "direct_match",
            "sentiment_bucket",
        ]

        for keys, g in df.groupby(group_cols, dropna=False):
            record = dict(zip(group_cols, keys))
            record["n_events"] = len(g)

            for h in [1, 5, 20]:
                matured = g[g[f"matured_{h}s"] == 1]
                record[f"n_{h}s"] = len(matured)

                if len(matured):
                    r = matured[f"ret_{h}s"].dropna()
                    record[f"mean_ret_{h}s"] = (
                        float(r.mean()) if len(r) else np.nan
                    )
                    record[f"median_ret_{h}s"] = (
                        float(r.median()) if len(r) else np.nan
                    )
                    record[f"positive_rate_{h}s"] = (
                        float((r > 0).mean()) if len(r) else np.nan
                    )
                else:
                    record[f"mean_ret_{h}s"] = np.nan
                    record[f"median_ret_{h}s"] = np.nan
                    record[f"positive_rate_{h}s"] = np.nan

            summaries.append(record)

    pd.DataFrame(summaries).to_csv(
        EVENT_SUMMARY,
        index=False,
        encoding="utf-8-sig",
    )

    return {
        "events_total": len(events),
        "outcome_rows": len(df),
        "matured_1d": (
            int(df["matured_1s"].sum()) if len(df) else 0
        ),
        "matured_5d": (
            int(df["matured_5s"].sum()) if len(df) else 0
        ),
        "matured_20d": (
            int(df["matured_20s"].sum()) if len(df) else 0
        ),
    }

def append_dynamic_report(row):
    MASTER_OUT.mkdir(exist_ok=True)

    if DAILY_REPORT.exists():
        old = pd.read_csv(DAILY_REPORT)
        new = pd.concat(
            [old, pd.DataFrame([row])],
            ignore_index=True,
            sort=False,
        )
    else:
        new = pd.DataFrame([row])

    new.to_csv(
        DAILY_REPORT,
        index=False,
        encoding="utf-8-sig",
    )

def status_only():
    print("\nMFP-3 ONE FILE v1.8 — ESTADO")
    print("v1.7 señales :", V17_SIGNALS.resolve(), V17_SIGNALS.exists())
    print("Forward      :", FORWARD_LEDGER.resolve(), FORWARD_LEDGER.exists())
    print("Eventos raw  :", RAW_EVENTS.resolve(), RAW_EVENTS.exists())
    print("Outcomes     :", EVENT_OUTCOMES.resolve(), EVENT_OUTCOMES.exists())
    print("Reporte      :", DAILY_REPORT.resolve(), DAILY_REPORT.exists())
    print("v1.7 SHA256  :", FROZEN_V17_SHA256)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full",
        action="store_true",
        help="Fuerza recálculo completo de v1.7-FROZEN.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Sólo muestra estado.",
    )
    args = parser.parse_args()

    if args.status:
        status_only()
        return

    write_manifest()

    print("\n" + "=" * 88)
    print("MFP-3 ONE FILE v1.8")
    print("=" * 88)
    print("Frozen v1.7 SHA256:", FROZEN_V17_SHA256)

    results = {
        "recorded_at_utc": now_utc(),
        "frozen_v17_sha256": FROZEN_V17_SHA256,
    }

    try:
        if v17_needs_refresh(args.full):
            print("\n[1/4] Actualizando v1.7-FROZEN...")
            run_embedded(
                FROZEN_V17_SOURCE,
                "mfp3_frozen_v17_embedded",
            )
            results["v17_refreshed"] = True
        else:
            print("\n[1/4] v1.7-FROZEN ya está actualizada hoy. Se reutiliza.")
            results["v17_refreshed"] = False

        d = latest_signal_date()
        results["signal_date"] = d.isoformat() if d else None

    except Exception as e:
        print("\nERROR en v1.7-FROZEN:", e)
        traceback.print_exc()
        results["v17_error"] = str(e)

    try:
        print("\n[2/4] Actualizando Forward Paper...")
        fwd = run_forward_paper()
        results.update({
            "portfolio_value_clp": fwd["portfolio_value_clp"],
            "forward_return": fwd["return_since_start"],
            "cumulative_cost_clp": fwd["cumulative_cost_clp"],
            "rebalanced": fwd["rebalanced_this_run"],
        })
    except Exception as e:
        print("\nERROR en Forward Paper:", e)
        traceback.print_exc()
        results["forward_error"] = str(e)

    try:
        print("\n[3/4] Recolectando noticias + mercado + macro...")
        before = RAW_EVENTS.stat().st_size if RAW_EVENTS.exists() else 0

        run_embedded(
            EVENT_COLLECTOR_SOURCE,
            "mfp3_events_embedded",
        )

        after = RAW_EVENTS.stat().st_size if RAW_EVENTS.exists() else 0
        results["event_raw_bytes_added"] = max(0, after - before)

    except Exception as e:
        print("\nERROR en Event Collector:", e)
        traceback.print_exc()
        results["events_error"] = str(e)

    try:
        print("\n[4/4] Etiquetando eventos con resultados futuros disponibles...")
        ev = update_event_outcomes()
        results.update({
            "events_total": ev.get("events_total"),
            "event_outcome_rows": ev.get("outcome_rows"),
            "event_matured_1d": ev.get("matured_1d"),
            "event_matured_5d": ev.get("matured_5d"),
            "event_matured_20d": ev.get("matured_20d"),
        })
    except Exception as e:
        print("\nERROR en Event Learning:", e)
        traceback.print_exc()
        results["event_learning_error"] = str(e)

    append_dynamic_report(results)

    print("\n" + "=" * 88)
    print("RESUMEN DIARIO")
    print("=" * 88)

    if "portfolio_value_clp" in results:
        print(
            "Cartera Forward :",
            f"${results['portfolio_value_clp']:,.0f} CLP"
        )
        print(
            "Retorno Forward :",
            f"{results['forward_return']:+.3%}"
        )
        print(
            "Costos acum.    :",
            f"${results['cumulative_cost_clp']:,.0f} CLP"
        )

    print("Señal v1.7     :", results.get("signal_date"))
    print("Eventos total  :", results.get("events_total", "N/D"))
    print("Etiquetas 1s   :", results.get("event_matured_1d", "N/D"))
    print("Etiquetas 5s   :", results.get("event_matured_5d", "N/D"))
    print("Etiquetas 20s  :", results.get("event_matured_20d", "N/D"))

    print("\nTODO se activa ahora con un solo archivo:")
    print("  py mfp3_onefile_v1_8.py")
    print("\nCarpeta master:", MASTER_OUT.resolve())
    print("No ejecuta operaciones reales.")

if __name__ == "__main__":
    main()
