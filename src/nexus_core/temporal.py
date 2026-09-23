"""Point-in-time split helpers shared by active NEXUS-MFP research."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


def _validate_index(index: pd.Index) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(index)
    if not idx.is_monotonic_increasing:
        raise ValueError("Temporal index must be sorted ascending")
    if idx.has_duplicates:
        raise ValueError("Temporal index must not contain duplicates")
    return idx


def mature_label_mask(
    index: pd.Index,
    horizon: int,
    allowed: Sequence[bool] | pd.Series | np.ndarray | None = None,
    entry_delay: int = 1,
) -> pd.Series:
    """Return rows whose entire forward target stays inside a partition.

    NEXUS targets enter at ``t + entry_delay`` and exit ``horizon`` sessions
    later. A label is usable only when both its source row and its exit row
    belong to the allowed temporal partition. The calculation is positional,
    so holidays and irregular trading calendars cannot invalidate the purge.
    """

    idx = _validate_index(index)
    if horizon < 1:
        raise ValueError("horizon must be at least one session")
    if entry_delay < 0:
        raise ValueError("entry_delay cannot be negative")

    steps = entry_delay + horizon
    if allowed is None:
        allowed_values = np.ones(len(idx), dtype=bool)
    else:
        allowed_values = np.asarray(allowed, dtype=bool)
        if len(allowed_values) != len(idx):
            raise ValueError("allowed must have the same length as index")

    result = np.zeros(len(idx), dtype=bool)
    if len(idx) > steps:
        source = np.arange(0, len(idx) - steps)
        exits = source + steps
        result[source] = allowed_values[source] & allowed_values[exits]

    return pd.Series(result, index=idx, name="mature_label")


def purge_labeled_frame(
    frame: pd.DataFrame,
    horizon: int,
    entry_delay: int = 1,
) -> pd.DataFrame:
    """Remove observations whose target would leave ``frame``."""

    mask = mature_label_mask(
        frame.index,
        horizon=horizon,
        entry_delay=entry_delay,
    )
    return frame.loc[mask].copy()
