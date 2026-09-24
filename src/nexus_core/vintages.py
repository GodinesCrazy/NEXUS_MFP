"""Immutable local snapshots and as-of selection for point-in-time research."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def _utc(value) -> datetime:
    parsed = pd.Timestamp(value)
    if parsed.tzinfo is None:
        parsed = parsed.tz_localize("UTC")
    else:
        parsed = parsed.tz_convert("UTC")
    return parsed.to_pydatetime()


def _slug(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")
    if not clean:
        raise ValueError("nombre de snapshot vacío")
    return clean


@dataclass(frozen=True)
class SnapshotMetadata:
    source: str
    variable: str
    retrieved_at_utc: str
    frequency: str
    release_lag: str
    content_sha256: str
    rows: int
    point_in_time: bool = True
    knowledge_at_utc: str | None = None
    source_vintage_date: str | None = None


class VintageSnapshotStore:
    """Append-only snapshots; an as-of query never sees future retrievals."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def write(
        self,
        *,
        source: str,
        variable: str,
        retrieved_at,
        knowledge_at=None,
        data: pd.Series | pd.DataFrame,
        frequency: str,
        release_lag: str,
        source_vintage_date: str | None = None,
    ) -> SnapshotMetadata:
        retrieved = _utc(retrieved_at)
        knowledge = _utc(knowledge_at if knowledge_at is not None else retrieved_at)
        stamp = knowledge.strftime("%Y%m%dT%H%M%SZ")
        directory = self.root / _slug(source) / _slug(variable)
        directory.mkdir(parents=True, exist_ok=True)
        stem = directory / stamp
        csv_path = stem.with_suffix(".csv")
        json_path = stem.with_suffix(".json")
        if csv_path.exists() or json_path.exists():
            raise FileExistsError(f"snapshot inmutable ya existe: {stem}")
        frame = data.to_frame(name=data.name or "value") if isinstance(data, pd.Series) else data.copy()
        payload = frame.to_csv(index=True, lineterminator="\n").encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()
        metadata = SnapshotMetadata(
            source=source,
            variable=variable,
            retrieved_at_utc=retrieved.isoformat(timespec="seconds"),
            frequency=frequency,
            release_lag=release_lag,
            content_sha256=digest,
            rows=int(len(frame)),
            knowledge_at_utc=knowledge.isoformat(timespec="seconds"),
            source_vintage_date=source_vintage_date,
        )
        csv_path.write_bytes(payload)
        json_path.write_text(
            json.dumps(asdict(metadata), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return metadata

    def as_of(self, source: str, variable: str, decision_time) -> tuple[pd.DataFrame, SnapshotMetadata]:
        cutoff = _utc(decision_time)
        directory = self.root / _slug(source) / _slug(variable)
        eligible: list[tuple[datetime, Path]] = []
        for metadata_path in directory.glob("*.json") if directory.exists() else []:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            known = _utc(
                payload.get("knowledge_at_utc")
                or payload["retrieved_at_utc"]
            )
            if known <= cutoff:
                eligible.append((known, metadata_path))
        if not eligible:
            raise LookupError(
                f"sin snapshot {source}/{variable} disponible en {cutoff.isoformat()}"
            )
        _, metadata_path = max(eligible, key=lambda item: item[0])
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        payload.setdefault("knowledge_at_utc", payload["retrieved_at_utc"])
        payload.setdefault("source_vintage_date", None)
        metadata = SnapshotMetadata(**payload)
        csv_path = metadata_path.with_suffix(".csv")
        raw = csv_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != metadata.content_sha256:
            raise ValueError(f"hash inválido para snapshot: {csv_path}")
        return pd.read_csv(csv_path, index_col=0, parse_dates=True), metadata

    def known_latest_series(self, source: str, variable: str) -> pd.Series:
        """Materialize the latest observation actually known at each vintage."""

        directory = self.root / _slug(source) / _slug(variable)
        points: dict[pd.Timestamp, float] = {}
        for metadata_path in sorted(directory.glob("*.json")) if directory.exists() else []:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            known = pd.Timestamp(
                payload.get("knowledge_at_utc") or payload["retrieved_at_utc"]
            )
            csv_path = metadata_path.with_suffix(".csv")
            raw = csv_path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != payload["content_sha256"]:
                raise ValueError(f"hash inválido para snapshot: {csv_path}")
            frame = pd.read_csv(csv_path, index_col=0, parse_dates=True)
            if frame.empty:
                continue
            index = pd.to_datetime(frame.index, utc=True, errors="coerce")
            values = pd.to_numeric(frame.iloc[:, 0], errors="coerce")
            eligible = values[(index <= known) & values.notna()]
            if not eligible.empty:
                points[known] = float(eligible.iloc[-1])
        if not points:
            return pd.Series(dtype=float, name=variable)
        series = pd.Series(points, name=variable, dtype=float).sort_index()
        series.index = series.index.tz_convert(None)
        return series[~series.index.duplicated(keep="last")]
