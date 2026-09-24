"""Resumable ALFRED vintage ingestion with explicit provenance."""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pandas as pd

from nexus_core.vintages import VintageSnapshotStore


API_ROOT = "https://api.stlouisfed.org/fred"


@dataclass(frozen=True)
class SeriesSpec:
    series_id: str
    variable: str
    frequency: str
    release_lag: str = "encoded_by_alfred_realtime_period"


DEFAULT_SERIES = (
    SeriesSpec("DFII10", "real10y", "daily"),
    SeriesSpec("T10Y2Y", "curve10y2y", "daily"),
    SeriesSpec("NFCI", "nfci", "weekly"),
    SeriesSpec("T10YIE", "breakeven10y", "daily"),
    SeriesSpec("DGS2", "dgs2", "daily"),
    SeriesSpec("DGS10", "dgs10", "daily"),
    SeriesSpec("DTWEXBGS", "usd_broad", "daily"),
)


class AlfredClient:
    """Small official FRED API client; the API key is never persisted."""

    def __init__(
        self,
        api_key: str,
        *,
        timeout: int = 20,
        transport: Callable[[str, int], dict] | None = None,
    ):
        if not re.fullmatch(r"[a-z0-9]{32}", api_key or ""):
            raise ValueError("FRED_API_KEY debe contener 32 caracteres alfanuméricos")
        self._api_key = api_key
        self.timeout = timeout
        self._transport = transport or self._download_json

    @staticmethod
    def _download_json(url: str, timeout: int) -> dict:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "NEXUS-MFP/point-in-time-research"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def _get(self, endpoint: str, **parameters) -> dict:
        query = urllib.parse.urlencode({
            **parameters,
            "api_key": self._api_key,
            "file_type": "json",
        })
        try:
            return self._transport(f"{API_ROOT}/{endpoint}?{query}", self.timeout)
        except Exception as exc:
            reason = getattr(exc, "reason", None) or type(exc).__name__
            raise RuntimeError(
                f"solicitud ALFRED falló: {type(exc).__name__}: {reason}"
            ) from None

    def vintage_dates(self, series_id: str, start: str, end: str) -> list[str]:
        dates: list[str] = []
        offset = 0
        while True:
            payload = self._get(
                "series/vintagedates",
                series_id=series_id,
                realtime_start=start,
                realtime_end=end,
                limit=10_000,
                offset=offset,
                sort_order="asc",
            )
            page = payload.get("vintage_dates", [])
            dates.extend(str(item) for item in page)
            count = int(payload.get("count", len(dates)))
            offset += len(page)
            if not page or offset >= count:
                return dates

    def observations_as_of(
        self,
        series_id: str,
        vintage_date: str,
        observation_start: str,
    ) -> pd.Series:
        payload = self._get(
            "series/observations",
            series_id=series_id,
            realtime_start=vintage_date,
            realtime_end=vintage_date,
            observation_start=observation_start,
            observation_end=vintage_date,
            output_type=1,
            sort_order="asc",
        )
        values = {}
        for row in payload.get("observations", []):
            if row.get("value") in (None, "."):
                continue
            values[pd.Timestamp(row["date"])] = float(row["value"])
        return pd.Series(values, name=series_id, dtype=float).sort_index()


class AlfredVintageIngestor:
    """Backfill a bounded number of vintages per run and report completeness."""

    def __init__(self, client: AlfredClient, root: Path):
        self.client = client
        self.root = Path(root)
        self.store = VintageSnapshotStore(self.root / "snapshots")

    def _existing(self, variable: str) -> set[str]:
        directory = self.root / "snapshots" / "ALFRED" / variable
        existing: set[str] = set()
        for path in directory.glob("*.json") if directory.exists() else []:
            payload = json.loads(path.read_text(encoding="utf-8"))
            vintage = payload.get("source_vintage_date")
            if vintage:
                existing.add(vintage)
        return existing

    def ingest(
        self,
        specs: tuple[SeriesSpec, ...] = DEFAULT_SERIES,
        *,
        start: str = "2008-01-01",
        end: str | None = None,
        max_new_vintages: int = 25,
    ) -> dict:
        if max_new_vintages < 1:
            raise ValueError("max_new_vintages debe ser positivo")
        end = end or datetime.now(timezone.utc).date().isoformat()
        retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        series_status = []
        for spec in specs:
            all_dates = self.client.vintage_dates(spec.series_id, start, end)
            existing = self._existing(spec.variable)
            pending = [date for date in all_dates if date not in existing]
            created = 0
            errors = []
            for vintage_date in pending[:max_new_vintages]:
                try:
                    data = self.client.observations_as_of(
                        spec.series_id, vintage_date, start
                    )
                    if data.empty:
                        raise ValueError("vintage sin observaciones utilizables")
                    self.store.write(
                        source="ALFRED",
                        variable=spec.variable,
                        retrieved_at=retrieved_at,
                        knowledge_at=f"{vintage_date}T23:59:59Z",
                        source_vintage_date=vintage_date,
                        data=data,
                        frequency=spec.frequency,
                        release_lag=spec.release_lag,
                    )
                    created += 1
                except Exception as exc:
                    errors.append(f"{vintage_date}: {type(exc).__name__}: {exc}"[:300])
                    break
            remaining = max(0, len(pending) - created)
            series_status.append({
                **asdict(spec),
                "available_vintages": len(all_dates),
                "previously_stored": len(existing),
                "created": created,
                "remaining": remaining,
                "complete": remaining == 0 and not errors and bool(all_dates),
                "errors": errors,
            })
        ready = bool(series_status) and all(item["complete"] for item in series_status)
        status = {
            "status": "ready" if ready else "partial",
            "provider": "ALFRED / Federal Reserve Bank of St. Louis",
            "official_api": "https://fred.stlouisfed.org/docs/api/fred/",
            "updated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "observation_start": start,
            "observation_end": end,
            "promotion_ready": ready,
            "series": series_status,
        }
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "status.json").write_text(
            json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return status


def _credential_status(root: Path) -> dict:
    status = {
        "status": "credential_missing",
        "provider": "ALFRED / Federal Reserve Bank of St. Louis",
        "official_api": "https://fred.stlouisfed.org/docs/api/fred/",
        "updated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "promotion_ready": False,
        "message": "Configura FRED_API_KEY; no se descargaron ni simularon vintages.",
        "series": [],
    }
    root.mkdir(parents=True, exist_ok=True)
    (root / "status.json").write_text(
        json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingesta resumible de vintages ALFRED")
    parser.add_argument("--root", type=Path, default=Path("runtime/vintages"))
    parser.add_argument("--start", default="2008-01-01")
    parser.add_argument("--end")
    parser.add_argument("--max-new-vintages", type=int, default=25)
    args = parser.parse_args()
    api_key = os.environ.get("FRED_API_KEY", "")
    if not api_key:
        status = _credential_status(args.root)
        print(status["message"])
        return 2
    status = AlfredVintageIngestor(AlfredClient(api_key), args.root).ingest(
        start=args.start,
        end=args.end,
        max_new_vintages=args.max_new_vintages,
    )
    print(json.dumps(status, indent=2, ensure_ascii=False))
    return 0 if status["promotion_ready"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
