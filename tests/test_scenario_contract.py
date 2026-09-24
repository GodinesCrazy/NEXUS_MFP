import unittest

import pandas as pd

from nexus_core.scenarios import linear_portfolio_shock, transaction_cost_sensitivity


class ScenarioContractTests(unittest.TestCase):
    def test_cost_scenarios_share_window_and_decline_monotonically(self):
        index = pd.date_range("2020-01-01", periods=300, freq="B")
        gross = pd.Series(0.0008, index=index)
        turnover = pd.Series(0.20, index=index)
        result = transaction_cost_sensitivity(gross, turnover)
        returns = [item["total_return"] for item in result["scenarios"]]
        self.assertEqual(result["observations"], 300)
        self.assertEqual(len(set(item["cumulative_turnover"] for item in result["scenarios"])), 1)
        self.assertEqual(returns, sorted(returns, reverse=True))

    def test_zero_turnover_has_no_cost_drag(self):
        gross = pd.Series([0.01, -0.005, 0.002])
        result = transaction_cost_sensitivity(gross, pd.Series([0.0, 0.0, 0.0]))
        self.assertTrue(all(abs(item["return_drag"]) < 1e-12 for item in result["scenarios"]))

    def test_negative_turnover_is_rejected(self):
        with self.assertRaises(ValueError):
            transaction_cost_sensitivity(pd.Series([0.01]), pd.Series([-0.1]))

    def test_linear_shock_is_weighted_and_leaves_cash_unchanged(self):
        result = linear_portfolio_shock(
            {"QQQ": 0.20, "ECH": 0.15, "CPER": 0.30},
            {"QQQ": -0.10, "ECH": 0.05, "CPER": -0.20},
        )
        self.assertAlmostEqual(result["impact"], -0.0725)
        self.assertAlmostEqual(result["invested_weight"], 0.65)


if __name__ == "__main__":
    unittest.main()
