"""Statistical screening utilities with explicit multiple-test control."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import combine_pvalues, spearmanr


def safe_corr_pvalue(a, b, min_n=40):
    z = pd.DataFrame({"a": a, "b": b}).dropna()
    if len(z) < min_n or z["a"].std() < 1e-12 or z["b"].std() < 1e-12:
        return np.nan, np.nan
    result = spearmanr(z["a"], z["b"])
    return float(result.statistic), float(result.pvalue)


def combined_pvalue(values):
    p = np.asarray([x for x in values if np.isfinite(x)], dtype=float)
    if len(p) == 0:
        return np.nan
    p = np.clip(p, 1e-12, 1.0)
    return float(combine_pvalues(p, method="fisher").pvalue)


def benjamini_hochberg(values):
    """Return Benjamini-Hochberg adjusted p-values in original order."""

    p = pd.Series(values, dtype=float)
    out = pd.Series(np.nan, index=p.index, dtype=float)
    valid = p.dropna().sort_values()
    m = len(valid)
    if m == 0:
        return out
    ranked = valid * m / np.arange(1, m + 1)
    adjusted = np.minimum.accumulate(ranked.iloc[::-1])[::-1].clip(upper=1.0)
    out.loc[adjusted.index] = adjusted
    return out
