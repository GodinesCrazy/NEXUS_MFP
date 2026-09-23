import unittest

import numpy as np
import pandas as pd

from nexus_core.bootstrap import paired_block_bootstrap


class BootstrapContractTests(unittest.TestCase):
    def test_deterministic_positive_increment_passes(self):
        rng = np.random.default_rng(7)
        baseline = pd.Series(rng.normal(0.0002, 0.004, 500))
        candidate = baseline + 0.0008 + pd.Series(rng.normal(0, 0.0002, 500))
        first = paired_block_bootstrap(candidate, baseline, samples=400, seed=11)
        second = paired_block_bootstrap(candidate, baseline, samples=400, seed=11)
        self.assertEqual(first, second)
        self.assertTrue(first.passes)
        self.assertGreater(first.lower_95_annualized_delta, 0)

    def test_insufficient_history_fails_closed(self):
        evidence = paired_block_bootstrap(
            pd.Series([0.01] * 20),
            pd.Series([0.0] * 20),
            samples=100,
        )
        self.assertFalse(evidence.passes)
        self.assertEqual(evidence.observations, 20)


if __name__ == "__main__":
    unittest.main()
