import unittest

from nexus_core.decisions import DecisionPolicy, ForecastDistribution


def forecast(**overrides):
    values = {
        "asset": "QQQ", "as_of_utc": "2026-09-23T20:00:00+00:00",
        "horizon_sessions": 20, "current_price": 100.0,
        "p10": 96.0, "p50": 104.0, "p90": 110.0,
        "probability_positive": 0.67, "oos_observations": 300,
        "calibrated": True, "promoted": True,
    }
    values.update(overrides)
    return ForecastDistribution(**values)


class DecisionContractTests(unittest.TestCase):
    def test_missing_forecast_forces_abstention(self):
        result = DecisionPolicy().evaluate("QQQ", "AUMENTAR", None)
        self.assertEqual(result.recommendation, "SIN RECOMENDACIÓN")
        self.assertEqual(result.portfolio_action, "AUMENTAR")

    def test_unpromoted_forecast_forces_abstention(self):
        result = DecisionPolicy().evaluate("QQQ", "MANTENER", forecast(promoted=False))
        self.assertEqual(result.status, "blocked")

    def test_invalid_quantile_order_is_rejected(self):
        with self.assertRaises(ValueError):
            forecast(p10=105.0, p50=100.0)

    def test_promoted_positive_forecast_can_buy(self):
        result = DecisionPolicy().evaluate("QQQ", "AUMENTAR", forecast())
        self.assertEqual(result.recommendation, "COMPRAR")
        self.assertEqual(result.market_outlook, "ALCISTA")

    def test_promoted_negative_forecast_sells_existing_position(self):
        result = DecisionPolicy().evaluate(
            "QQQ", "REDUCIR",
            forecast(p10=82.0, p50=96.0, p90=103.0, probability_positive=0.30),
            has_position=True,
        )
        self.assertEqual(result.recommendation, "VENDER")


if __name__ == "__main__":
    unittest.main()
