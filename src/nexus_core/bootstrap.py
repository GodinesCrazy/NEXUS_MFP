"""Serial-dependence-aware evidence for incremental strategy returns."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BootstrapEvidence:
    observations: int
    block_size: int
    samples: int
    observed_annualized_delta: float
    lower_95_annualized_delta: float
    upper_95_annualized_delta: float
    probability_positive: float
    passes: bool

    def as_dict(self) -> dict:
        return asdict(self)


def paired_block_bootstrap(
    candidate: pd.Series,
    baseline: pd.Series,
    *,
    block_size: int = 20,
    samples: int = 1_000,
    seed: int = 19,
    min_observations: int = 120,
    annualization: int = 252,
    minimum_probability: float = 0.95,
) -> BootstrapEvidence:
    """Bootstrap paired net-return deltas using circular moving blocks.

    Pairing preserves the common market path and moving blocks preserve local
    serial dependence. Promotion is deliberately strict: the lower 95% bound
    of the annualized mean delta must be positive.
    """

    aligned = pd.concat(
        [pd.Series(candidate, name="candidate"), pd.Series(baseline, name="baseline")],
        axis=1,
    ).replace([np.inf, -np.inf], np.nan).dropna()
    n = len(aligned)
    if block_size < 2:
        raise ValueError("block_size debe ser al menos 2")
    if samples < 100:
        raise ValueError("samples debe ser al menos 100")
    if n < min_observations:
        return BootstrapEvidence(n, block_size, samples, 0.0, 0.0, 0.0, 0.0, False)

    delta = (aligned["candidate"] - aligned["baseline"]).to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    blocks = int(np.ceil(n / block_size))
    starts = rng.integers(0, n, size=(samples, blocks, 1))
    offsets = np.arange(block_size).reshape(1, 1, block_size)
    indices = ((starts + offsets) % n).reshape(samples, -1)[:, :n]
    boot = delta[indices].mean(axis=1) * annualization
    observed = float(delta.mean() * annualization)
    lower, upper = np.quantile(boot, [0.025, 0.975])
    probability = float(np.mean(boot > 0.0))
    passes = bool(lower > 0.0 and probability >= minimum_probability)
    return BootstrapEvidence(
        observations=n,
        block_size=block_size,
        samples=samples,
        observed_annualized_delta=observed,
        lower_95_annualized_delta=float(lower),
        upper_95_annualized_delta=float(upper),
        probability_positive=probability,
        passes=passes,
    )
