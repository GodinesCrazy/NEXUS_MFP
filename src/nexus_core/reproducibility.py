"""Deterministic fingerprints for research inputs and configurations."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Mapping

import pandas as pd


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pandas_fingerprint(value: pd.Series | pd.DataFrame) -> str:
    normalized = value.sort_index().copy()
    if isinstance(normalized, pd.Series):
        normalized = normalized.to_frame(name=normalized.name or "value")
    normalized = normalized.reindex(sorted(normalized.columns), axis=1)
    hashed = pd.util.hash_pandas_object(normalized, index=True)
    return hashlib.sha256(hashed.to_numpy().tobytes()).hexdigest()


def mapping_fingerprint(values: Mapping[str, pd.Series | pd.DataFrame]) -> str:
    digest = hashlib.sha256()
    for name in sorted(values):
        digest.update(name.encode("utf-8"))
        digest.update(pandas_fingerprint(values[name]).encode("ascii"))
    return digest.hexdigest()
