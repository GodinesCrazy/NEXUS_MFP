"""Transparent, non-predictive scenario calculations for the terminal."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def _metrics(returns: pd.Series) -> dict[str, float]:
    clean = pd.to_numeric(returns, errors="coerce").dropna()
    if clean.empty:
        return {"total_return": 0.0, "cagr": 0.0, "sharpe": 0.0, "max_drawdown": 0.0}
    capital = (1.0 + clean).cumprod()
    total = float(capital.iloc[-1] - 1.0)
    years = len(clean) / 252.0
    cagr = float(capital.iloc[-1] ** (1.0 / years) - 1.0) if years > 0 and capital.iloc[-1] > 0 else 0.0
    volatility = float(clean.std(ddof=0))
    sharpe = float(clean.mean() / volatility * math.sqrt(252)) if volatility > 0 else 0.0
    drawdown = capital / capital.cummax() - 1.0
    return {
        "total_return": total,
        "cagr": cagr,
        "sharpe": sharpe,
        "max_drawdown": float(drawdown.min()),
    }


def transaction_cost_sensitivity(
    gross_returns: pd.Series,
    turnover: pd.Series,
    *,
    costs_bps: tuple[int, ...] = (5, 15, 30, 50),
) -> dict:
    """Reprice one-way transaction costs on one identical historical window."""

    aligned = pd.concat(
        [
            pd.Series(gross_returns, name="gross"),
            pd.Series(turnover, name="turnover"),
        ],
        axis=1,
    ).replace([np.inf, -np.inf], np.nan).dropna()
    if aligned.empty:
        return {"observations": 0, "start": None, "end": None, "scenarios": []}
    if (aligned["turnover"] < 0).any():
        raise ValueError("turnover no puede ser negativo")
    gross_metrics = _metrics(aligned["gross"])
    scenarios = []
    for bps in costs_bps:
        if bps < 0:
            raise ValueError("el costo no puede ser negativo")
        cost_rate = bps / 10_000.0
        net = aligned["gross"] - aligned["turnover"] * cost_rate
        if (net <= -1.0).any():
            raise ValueError("escenario produce retorno diario menor o igual a -100%")
        metrics = _metrics(net)
        scenarios.append({
            "cost_bps": int(bps),
            **metrics,
            "return_drag": gross_metrics["total_return"] - metrics["total_return"],
            "cumulative_turnover": float(aligned["turnover"].sum()),
        })
    return {
        "observations": int(len(aligned)),
        "start": str(aligned.index[0]),
        "end": str(aligned.index[-1]),
        "gross": gross_metrics,
        "scenarios": scenarios,
    }


def linear_portfolio_shock(
    weights: dict[str, float],
    shocks: dict[str, float],
) -> dict:
    """Apply one-period asset shocks to fixed weights; cash has zero return."""

    contributions = {}
    for asset, raw_weight in weights.items():
        weight = float(raw_weight)
        shock = float(shocks.get(asset, 0.0))
        if not math.isfinite(weight) or not math.isfinite(shock):
            raise ValueError("pesos y shocks deben ser finitos")
        contributions[asset] = weight * shock
    return {
        "impact": float(sum(contributions.values())),
        "contributions": contributions,
        "invested_weight": float(sum(float(value) for value in weights.values())),
        "method": "fixed_weight_linear_one_period",
    }
