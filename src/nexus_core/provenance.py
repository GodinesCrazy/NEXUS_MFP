"""Source provenance and promotion gating contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class SourceRecord:
    source: str
    variable: str
    frequency: str
    release_lag: str
    vintage_policy: str
    fallback: str = ""
    used_for_causal: bool = True
    point_in_time: bool = False

    def as_row(self) -> dict:
        return asdict(self)


def promotion_eligibility(
    records: Iterable[SourceRecord],
) -> tuple[bool, list[str]]:
    """Fail closed when a causal input is not point-in-time reproducible."""

    rows = list(records)
    blockers = sorted(
        {
            r.variable
            for r in rows
            if r.used_for_causal and not r.point_in_time
        }
    )
    return not blockers, blockers


def ledger_frame(records: Iterable[SourceRecord]) -> pd.DataFrame:
    return pd.DataFrame([r.as_row() for r in records])
