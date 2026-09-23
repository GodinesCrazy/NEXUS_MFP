import unittest

import numpy as np

from nexus_core.statistics import benjamini_hochberg, combined_pvalue


class StatisticsContractTests(unittest.TestCase):
    def test_bh_preserves_order_and_controls_family(self):
        adjusted = benjamini_hochberg([0.01, 0.04, 0.03, np.nan])

        self.assertAlmostEqual(adjusted.iloc[0], 0.03)
        self.assertAlmostEqual(adjusted.iloc[1], 0.04)
        self.assertAlmostEqual(adjusted.iloc[2], 0.04)
        self.assertTrue(np.isnan(adjusted.iloc[3]))

    def test_combined_pvalue_rejects_empty_evidence(self):
        self.assertTrue(np.isnan(combined_pvalue([np.nan])))

    def test_combined_pvalue_accumulates_repeated_evidence(self):
        self.assertLess(combined_pvalue([0.05, 0.05, 0.05]), 0.05)


if __name__ == "__main__":
    unittest.main()
