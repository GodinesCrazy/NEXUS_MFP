import unittest

import numpy as np
import pandas as pd

from nexus_core.temporal import mature_label_mask, purge_labeled_frame


class TemporalContractTests(unittest.TestCase):
    def test_purges_entry_delay_plus_horizon_sessions(self):
        idx = pd.bdate_range("2025-01-02", periods=10)
        frame = pd.DataFrame({"x": range(10)}, index=idx)

        purged = purge_labeled_frame(frame, horizon=5)

        self.assertEqual(len(purged), 4)
        self.assertEqual(purged.index[-1], idx[3])

    def test_year_partition_cannot_use_next_year_label(self):
        idx = pd.DatetimeIndex(
            [
                "2024-12-26",
                "2024-12-27",
                "2024-12-30",
                "2024-12-31",
                "2025-01-02",
                "2025-01-03",
            ]
        )
        allowed = idx.year == 2024

        mask = mature_label_mask(idx, horizon=1, allowed=allowed)

        self.assertTrue(mask.iloc[0])
        self.assertTrue(mask.iloc[1])
        self.assertFalse(mask.iloc[2])
        self.assertFalse(mask.iloc[3])
        self.assertFalse(mask.iloc[4:].any())

    def test_irregular_calendar_uses_positions_not_business_day_math(self):
        idx = pd.DatetimeIndex(
            ["2024-12-27", "2024-12-30", "2025-01-02", "2025-01-03"]
        )
        mask = mature_label_mask(idx, horizon=1)

        np.testing.assert_array_equal(
            mask.to_numpy(),
            np.array([True, True, False, False]),
        )

    def test_rejects_unsorted_index(self):
        idx = pd.DatetimeIndex(["2025-01-03", "2025-01-02"])
        with self.assertRaisesRegex(ValueError, "sorted"):
            mature_label_mask(idx, horizon=1)


if __name__ == "__main__":
    unittest.main()
