import json
import tempfile
import unittest
from pathlib import Path

from nexus_ui.data import DashboardRepository


class DashboardRepositoryTests(unittest.TestCase):
    def test_snapshot_uses_latest_runtime_and_derives_paper_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "runtime" / "run_a" / "mfp3_output_v17"
            forward = root / "runtime" / "run_a" / "mfp3_forward_v17"
            causal = root / "runtime" / "run_a" / "mfp3_causal_driver_lab"
            for directory in (output, forward, causal):
                directory.mkdir(parents=True)

            (output / "current_signals.csv").write_text(
                "date,asset,ensemble,paper_action,target_portfolio_weight,price_usd,usdclp,price_clp\n"
                "2026-01-02,QQQ,test,EXPOSICIÓN PARCIAL (paper),0.30,100,900,90000\n",
                encoding="utf-8",
            )
            (output / "metrics.csv").write_text(
                "name,total_return,cagr,sharpe,max_drawdown,ann_vol\n"
                "MFP3_v17_META_ENSEMBLE,0.1,0.05,0.7,-0.1,0.12\n",
                encoding="utf-8",
            )
            (output / "portfolio_daily.csv").write_text(
                ",capital_clp,benchmark_capital_clp\n2026-01-02,10000000,11000000\n",
                encoding="utf-8",
            )
            (forward / "state.json").write_text(
                json.dumps({"shares": {"QQQ": 10}, "cash_clp": 9_100_000, "last_signal_date": "2026-01-02"}),
                encoding="utf-8",
            )
            (forward / "ledger.csv").write_text(
                "portfolio_value_clp,usdclp,qqq_usd,return_since_start\n10000000,900,100,0.01\n",
                encoding="utf-8",
            )
            (causal / "causal_state.json").write_text(
                json.dumps({"promotion_allowed": False, "latest_causal_weight": 0, "promotion_blockers": ["not_pit"]}),
                encoding="utf-8",
            )
            (causal / "causal_sources.json").write_text(
                json.dumps({"sources": {"FRED_X": {"ok": False}}}),
                encoding="utf-8",
            )

            snapshot = DashboardRepository(root).snapshot()
            self.assertEqual(snapshot["signals"][0]["action"], "AUMENTAR")
            self.assertAlmostEqual(snapshot["signals"][0]["current_weight"], 0.09)
            self.assertFalse(snapshot["causal_gate"]["promotion_allowed"])
            self.assertEqual(snapshot["sources"]["failed_count"], 1)
            self.assertFalse(snapshot["model"]["live_trading_enabled"])


if __name__ == "__main__":
    unittest.main()
