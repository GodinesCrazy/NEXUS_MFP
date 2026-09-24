"""Read-only aggregation of NEXUS artifacts and delayed online market data."""

from __future__ import annotations

import csv
import json
import math
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ASSETS = ("QQQ", "ECH", "CPER")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {}


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError:
        return []


def _last(rows: list[dict[str, str]]) -> dict[str, str]:
    return rows[-1] if rows else {}


def _paper_action(target: float, current: float | None) -> tuple[str, float | None]:
    if current is None:
        if target >= 0.24:
            return "AUMENTAR", None
        if target <= 0.04:
            return "REDUCIR", None
        return "MANTENER", None
    delta = target - current
    if delta > 0.02:
        return "AUMENTAR", delta
    if delta < -0.02:
        return "REDUCIR", delta
    return "MANTENER", delta


def _ensemble_components(value: str) -> list[dict[str, Any]]:
    totals: dict[str, float] = {}
    for part in (value or "").split("+"):
        name, separator, raw_weight = part.strip().rpartition(":")
        if not separator or not name:
            continue
        totals[name] = totals.get(name, 0.0) + _number(raw_weight)
    return [
        {"name": name, "weight": weight}
        for name, weight in sorted(totals.items(), key=lambda item: -item[1])
    ]


class DashboardRepository:
    """Build a stable UI snapshot from the newest local research artifacts."""

    def __init__(self, root: Path):
        self.root = root.resolve()

    def _latest_runtime_root(self) -> Path | None:
        candidates = list(
            (self.root / "runtime").glob("**/mfp3_output_v17/current_signals.csv")
        )
        if not candidates:
            return None
        newest = max(candidates, key=lambda path: path.stat().st_mtime)
        return newest.parent.parent

    def _artifact_paths(self) -> dict[str, Path]:
        runtime_root = self._latest_runtime_root()
        if runtime_root:
            return {
                "root": runtime_root,
                "signals": runtime_root / "mfp3_output_v17" / "current_signals.csv",
                "metrics": runtime_root / "mfp3_output_v17" / "metrics.csv",
                "portfolio_daily": runtime_root / "mfp3_output_v17" / "portfolio_daily.csv",
                "forward_state": runtime_root / "mfp3_forward_v17" / "state.json",
                "forward_ledger": runtime_root / "mfp3_forward_v17" / "ledger.csv",
                "causal_state": runtime_root / "mfp3_causal_driver_lab" / "causal_state.json",
                "sources": runtime_root / "mfp3_causal_driver_lab" / "causal_sources.json",
                "causal_drivers": runtime_root / "mfp3_causal_driver_lab" / "current_causal_drivers.csv",
                "vintages": self.root / "runtime" / "vintages" / "status.json",
            }
        historical = self.root / "outputs" / "extracted" / "mfp3_v17_inspect"
        return {
            "root": historical,
            "signals": historical / "current_signals.csv",
            "metrics": historical / "metrics.csv",
            "portfolio_daily": historical / "portfolio_daily.csv",
            "forward_state": Path("__missing__"),
            "forward_ledger": Path("__missing__"),
            "causal_state": Path("__missing__"),
            "sources": Path("__missing__"),
            "causal_drivers": Path("__missing__"),
            "vintages": self.root / "runtime" / "vintages" / "status.json",
        }

    def snapshot(self) -> dict:
        paths = self._artifact_paths()
        signals_raw = _read_csv(paths["signals"])
        metrics_raw = _read_csv(paths["metrics"])
        portfolio_raw = _read_csv(paths["portfolio_daily"])
        forward_state = _read_json(paths["forward_state"])
        ledger_last = _last(_read_csv(paths["forward_ledger"]))
        causal_state = _read_json(paths["causal_state"])
        source_payload = _read_json(paths["sources"])
        causal_drivers_raw = _read_csv(paths["causal_drivers"])
        vintage_status = _read_json(paths["vintages"])

        portfolio_value = _number(ledger_last.get("portfolio_value_clp"), 0.0)
        usdclp = _number(ledger_last.get("usdclp"), 0.0)
        shares = forward_state.get("shares", {})
        current_weights: dict[str, float] = {}
        if portfolio_value > 0 and usdclp > 0:
            for asset in ASSETS:
                price = _number(ledger_last.get(f"{asset.lower()}_usd"), 0.0)
                current_weights[asset] = (
                    _number(shares.get(asset), 0.0) * price * usdclp / portfolio_value
                )

        signals = []
        for row in signals_raw:
            asset = row.get("asset", "")
            if asset not in ASSETS:
                continue
            target = _number(row.get("target_portfolio_weight"))
            current = current_weights.get(asset)
            action, delta = _paper_action(target, current)
            signals.append({
                "asset": asset,
                "date": row.get("date"),
                "action": action,
                "model_action": row.get("paper_action", ""),
                "target_weight": target,
                "current_weight": current,
                "weight_delta": delta,
                "price_usd": _number(row.get("price_usd")),
                "price_clp": _number(row.get("price_clp")),
                "ensemble": row.get("ensemble", ""),
            })

        metrics = []
        for row in metrics_raw:
            metrics.append({
                "name": row.get("name", ""),
                "total_return": _number(row.get("total_return")),
                "cagr": _number(row.get("cagr")),
                "sharpe": _number(row.get("sharpe")),
                "max_drawdown": _number(row.get("max_drawdown")),
                "ann_vol": _number(row.get("ann_vol")),
            })

        equity = []
        if portfolio_raw:
            stride = max(1, len(portfolio_raw) // 180)
            sampled = portfolio_raw[::stride]
            if sampled[-1] is not portfolio_raw[-1]:
                sampled.append(portfolio_raw[-1])
            for row in sampled:
                equity.append({
                    "date": row.get("", row.get("date", "")),
                    "model": _number(row.get("capital_clp")),
                    "benchmark": _number(row.get("benchmark_capital_clp")),
                })

        source_status = {
            name: info
            for name, info in source_payload.get("sources", {}).items()
            if not name.startswith("PROMOTION_GATE_")
        }
        failed_sources = sorted(
            name for name, info in source_status.items()
            if isinstance(info, dict) and not info.get("ok", False)
        )
        updated = None
        existing = [path for path in paths.values() if isinstance(path, Path) and path.exists()]
        if existing:
            updated = datetime.fromtimestamp(
                max(path.stat().st_mtime for path in existing), timezone.utc
            ).isoformat(timespec="seconds")

        asset_details = []
        blockers = causal_state.get("promotion_blockers", ["sin_estado_causal"])
        for signal in signals:
            drivers = [
                {
                    "driver": row.get("driver", ""),
                    "status": row.get("status", "candidate"),
                    "direction": row.get("direction", row.get("sign", "")),
                    "evidence": row.get("future_ic", row.get("validation_ic", "")),
                }
                for row in causal_drivers_raw
                if row.get("asset") == signal["asset"] and row.get("driver")
            ]
            asset_details.append({
                "asset": signal["asset"],
                "action": signal["action"],
                "model_action": signal["model_action"],
                "target_weight": signal["target_weight"],
                "current_weight": signal["current_weight"],
                "weight_delta": signal["weight_delta"],
                "allocation_strength": min(1.0, signal["target_weight"] / 0.30),
                "signal_date": signal["date"],
                "ensemble_components": _ensemble_components(signal["ensemble"]),
                "causal_drivers": drivers,
                "causal_evidence": "available" if drivers else "not_available",
                "causal_weight": _number(causal_state.get("latest_causal_weight")),
                "explanation": (
                    "La acción compara la exposición paper actual con el peso objetivo "
                    "de v1.7-FROZEN. La intensidad no representa probabilidad ni confianza."
                ),
                "risk_notes": blockers[:4],
            })

        vintage_series = vintage_status.get("series", [])
        vintages = {
            "status": vintage_status.get("status", "not_run"),
            "provider": vintage_status.get("provider", "ALFRED"),
            "updated_at_utc": vintage_status.get("updated_at_utc"),
            "promotion_ready": bool(vintage_status.get("promotion_ready", False)),
            "message": vintage_status.get(
                "message", "La ingesta point-in-time todavía no se ha ejecutado."
            ),
            "series_complete": sum(bool(item.get("complete")) for item in vintage_series),
            "series_total": len(vintage_series),
            "snapshots": sum(
                int(item.get("previously_stored", 0)) + int(item.get("created", 0))
                for item in vintage_series
            ),
        }

        return {
            "generated_at_utc": _utc_now(),
            "artifact_updated_at_utc": updated,
            "artifact_root": str(paths["root"]),
            "model": {
                "name": "NEXUS-MFP",
                "champion": "v1.7-FROZEN",
                "challenger": "v1.14 Adaptive Fusion",
                "active_research": "v1.19 Causal Driver Discovery",
                "live_trading_enabled": False,
            },
            "portfolio": {
                "value_clp": portfolio_value,
                "cash_clp": _number(forward_state.get("cash_clp")),
                "return_since_start": _number(ledger_last.get("return_since_start")),
                "cumulative_cost_clp": _number(forward_state.get("cumulative_cost_clp")),
                "signal_date": forward_state.get("last_signal_date") or (
                    signals[0]["date"] if signals else None
                ),
            },
            "signals": signals,
            "asset_details": asset_details,
            "metrics": metrics,
            "equity": equity,
            "causal_gate": {
                "promotion_allowed": bool(causal_state.get("promotion_allowed", False)),
                "causal_weight": _number(causal_state.get("latest_causal_weight")),
                "v14_weight": _number(causal_state.get("latest_v14_weight"), 1.0),
                "blockers": causal_state.get("promotion_blockers", ["sin_estado_causal"]),
                "completed_at_utc": causal_state.get("last_completed_utc"),
            },
            "sources": {
                "total": len(source_status),
                "failed": failed_sources,
                "failed_count": len(failed_sources),
            },
            "vintages": vintages,
            "disclaimer": (
                "Señales de investigación y cartera paper. No constituyen una orden "
                "ni asesoría financiera; NEXUS-MFP no ejecuta operaciones reales."
            ),
        }


class MarketCache:
    """Non-blocking delayed quote cache. Yahoo failures remain explicit."""

    def __init__(self):
        self._lock = threading.RLock()
        self._state = {
            "status": "idle",
            "updated_at_utc": None,
            "provider": "Yahoo Finance (datos retrasados; sujeto a disponibilidad)",
            "error": None,
            "quotes": [],
        }
        self._thread: threading.Thread | None = None

    def snapshot(self) -> dict:
        with self._lock:
            return json.loads(json.dumps(self._state))

    def refresh_async(self) -> bool:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            self._state["status"] = "loading"
            self._state["error"] = None
            self._thread = threading.Thread(target=self._refresh, daemon=True)
            self._thread.start()
            return True

    def _refresh(self) -> None:
        try:
            import yfinance as yf

            raw = yf.download(
                list(ASSETS),
                period="5d",
                interval="5m",
                auto_adjust=True,
                progress=False,
                group_by="column",
                threads=True,
                timeout=12,
            )
            quotes = []
            for asset in ASSETS:
                if getattr(raw.columns, "nlevels", 1) > 1:
                    close = raw["Close"][asset].dropna()
                else:
                    close = raw["Close"].dropna()
                if close.empty:
                    continue
                recent = close.tail(96)
                first = float(recent.iloc[0])
                last = float(recent.iloc[-1])
                quotes.append({
                    "asset": asset,
                    "price_usd": last,
                    "change_window": (last / first - 1.0) if first else 0.0,
                    "points": [
                        {"time": str(index), "value": float(value)}
                        for index, value in recent.items()
                    ],
                })
            if not quotes:
                raise RuntimeError("Yahoo no devolvió cotizaciones utilizables")
            with self._lock:
                self._state.update({
                    "status": "ready",
                    "updated_at_utc": _utc_now(),
                    "error": None,
                    "quotes": quotes,
                })
        except Exception as exc:
            with self._lock:
                self._state.update({
                    "status": "error",
                    "updated_at_utc": _utc_now(),
                    "error": f"{type(exc).__name__}: {exc}"[:300],
                })
