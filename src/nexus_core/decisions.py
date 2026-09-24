"""Conservative, auditable decision contract for the paper terminal.

Allocation signals and directional recommendations are deliberately separate.
A BUY/SELL label is impossible until a forecast has enough promoted OOS evidence.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass(frozen=True)
class ForecastDistribution:
    asset: str
    as_of_utc: str
    horizon_sessions: int
    current_price: float
    p10: float
    p50: float
    p90: float
    probability_positive: float
    oos_observations: int
    calibrated: bool
    promoted: bool

    def __post_init__(self) -> None:
        numeric = (self.current_price, self.p10, self.p50, self.p90)
        if not all(math.isfinite(value) and value > 0 for value in numeric):
            raise ValueError("forecast prices must be finite and positive")
        if not self.p10 <= self.p50 <= self.p90:
            raise ValueError("forecast quantiles must satisfy p10 <= p50 <= p90")
        if not 0 <= self.probability_positive <= 1:
            raise ValueError("probability_positive must be between 0 and 1")
        if self.horizon_sessions <= 0 or self.oos_observations < 0:
            raise ValueError("forecast horizons and observation counts are invalid")
        try:
            as_of = datetime.fromisoformat(self.as_of_utc.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("as_of_utc must be a valid ISO timestamp") from exc
        if as_of.tzinfo is None:
            raise ValueError("as_of_utc must include a timezone")


@dataclass(frozen=True)
class DecisionResult:
    asset: str
    recommendation: str
    market_outlook: str
    portfolio_action: str
    status: str
    reason: str
    forecast: dict | None
    expected_net_return: float | None

    def to_dict(self) -> dict:
        return asdict(self)


class DecisionPolicy:
    """Translate promoted forecast evidence into paper-only recommendations."""

    def __init__(
        self,
        minimum_oos_observations: int = 252,
        minimum_probability: float = 0.60,
        minimum_net_return: float = 0.01,
        maximum_p10_loss: float = 0.08,
        one_way_cost: float = 0.0015,
    ):
        self.minimum_oos_observations = minimum_oos_observations
        self.minimum_probability = minimum_probability
        self.minimum_net_return = minimum_net_return
        self.maximum_p10_loss = maximum_p10_loss
        self.one_way_cost = one_way_cost

    def evaluate(
        self,
        asset: str,
        portfolio_action: str,
        forecast: ForecastDistribution | None,
        has_position: bool = True,
    ) -> DecisionResult:
        if forecast is None:
            return self._abstain(
                asset,
                portfolio_action,
                "No existe un pronóstico probabilístico promovido para este activo.",
            )
        if forecast.asset != asset:
            raise ValueError("forecast asset does not match the requested decision")
        if not forecast.calibrated or not forecast.promoted:
            return self._abstain(
                asset,
                portfolio_action,
                "El pronóstico existe, pero aún no está calibrado y promovido con evidencia OOS.",
                forecast,
            )
        if forecast.oos_observations < self.minimum_oos_observations:
            return self._abstain(
                asset,
                portfolio_action,
                f"Sólo hay {forecast.oos_observations} observaciones OOS; se exigen "
                f"{self.minimum_oos_observations}.",
                forecast,
            )

        expected_net = forecast.p50 / forecast.current_price - 1 - self.one_way_cost
        downside = forecast.p10 / forecast.current_price - 1
        if (
            forecast.probability_positive >= self.minimum_probability
            and expected_net >= self.minimum_net_return
            and downside >= -self.maximum_p10_loss
        ):
            recommendation, outlook = "COMPRAR", "ALCISTA"
            reason = "Retorno neto, probabilidad y downside superan los umbrales OOS."
        elif (
            forecast.probability_positive <= 1 - self.minimum_probability
            and expected_net <= -self.minimum_net_return
        ):
            recommendation = "VENDER" if has_position else "EVITAR"
            outlook = "BAJISTA"
            reason = "El escenario central neto es negativo y la probabilidad alcista es baja."
        else:
            recommendation, outlook = "MANTENER", "NEUTRAL"
            reason = "La evidencia promovida no supera los umbrales de compra o venta."

        return DecisionResult(
            asset=asset,
            recommendation=recommendation,
            market_outlook=outlook,
            portfolio_action=portfolio_action,
            status="paper_only",
            reason=reason,
            forecast=asdict(forecast),
            expected_net_return=expected_net,
        )

    @staticmethod
    def _abstain(
        asset: str,
        portfolio_action: str,
        reason: str,
        forecast: ForecastDistribution | None = None,
    ) -> DecisionResult:
        return DecisionResult(
            asset=asset,
            recommendation="SIN RECOMENDACIÓN",
            market_outlook="NO CALIBRADO",
            portfolio_action=portfolio_action,
            status="blocked",
            reason=reason,
            forecast=asdict(forecast) if forecast else None,
            expected_net_return=None,
        )
