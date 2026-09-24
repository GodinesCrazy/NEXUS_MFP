import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from nexus_core.forecasting import AnalogForecaster, PredictionLedger, business_session_age, evaluate_forecasts, forward_registration_allowed, prepare_price_frame


def synthetic_frame(size=500):
    rng = np.random.default_rng(23)
    returns = rng.normal(0.0004, 0.012, size)
    prices = 100 * np.cumprod(1 + returns)
    return prepare_price_frame(pd.DataFrame({
        "Date": pd.bdate_range("2020-01-01", periods=size),
        "price_usd": prices,
        "ensemble_p_up": np.clip(0.5 + returns * 4, 0.05, 0.95),
    }))


class ForecastingContractTests(unittest.TestCase):
    def test_prediction_uses_only_matured_labels(self):
        frame = synthetic_frame()
        model = AnalogForecaster(minimum_history=180, neighbors=60)
        before = model.predict(frame, 300, 20)
        changed = frame.copy()
        changed.loc[301:, "price_usd"] *= 10
        after = model.predict(changed, 300, 20)
        self.assertEqual(before, after)

    def test_walk_forward_outcomes_are_strictly_later(self):
        predictions = AnalogForecaster(minimum_history=180, neighbors=60).walk_forward(synthetic_frame(), 5)
        self.assertTrue((predictions["outcome_date"] > predictions["date"]).all())

    def test_uncertified_source_never_promotes(self):
        predictions = AnalogForecaster(minimum_history=180, neighbors=60).walk_forward(synthetic_frame(), 5)
        result = evaluate_forecasts(predictions, source_point_in_time_verified=False, minimum_oos=100)
        self.assertFalse(result.promotion_allowed)
        self.assertIn("source_history_not_point_in_time_certified", result.blockers)
        self.assertIn("paper_forward_evidence_pending", result.blockers)

    def test_ledger_is_append_only_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.jsonl"
            ledger = PredictionLedger(path)
            payload = {"asset":"QQQ", "as_of_utc":"2026-01-01T00:00:00+00:00", "horizon_sessions":5, "model_version":"x", "data_sha256":"abc"}
            self.assertEqual(ledger.append([payload]), 1)
            self.assertEqual(ledger.append([payload]), 0)
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertIsNone(rows[0]["outcome"])

    def test_revised_data_does_not_duplicate_same_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = PredictionLedger(Path(tmp) / "ledger.jsonl")
            base = {"asset":"QQQ", "as_of_utc":"2026-01-01T00:00:00+00:00", "horizon_sessions":5, "model_version":"x", "data_sha256":"old"}
            self.assertEqual(ledger.append([base]), 1)
            self.assertEqual(ledger.append([{**base, "data_sha256":"revised"}]), 0)

    def test_business_session_age_excludes_weekend(self):
        self.assertEqual(business_session_age(pd.Timestamp("2026-09-18", tz="UTC"), pd.Timestamp("2026-09-21", tz="UTC")), 1)

    def test_future_dated_source_cannot_register_forward(self):
        self.assertFalse(forward_registration_allowed(
            pd.Timestamp("2026-09-25", tz="UTC"), pd.Timestamp("2026-09-24", tz="UTC")
        ))


if __name__ == "__main__":
    unittest.main()
