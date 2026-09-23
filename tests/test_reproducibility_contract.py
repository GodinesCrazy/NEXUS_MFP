import unittest

import pandas as pd

from nexus_core.reproducibility import mapping_fingerprint, pandas_fingerprint


class ReproducibilityContractTests(unittest.TestCase):
    def test_frame_fingerprint_is_deterministic(self):
        frame = pd.DataFrame(
            {"b": [2.0, 3.0], "a": [0.0, 1.0]},
            index=pd.to_datetime(["2025-01-03", "2025-01-02"]),
        )

        self.assertEqual(
            pandas_fingerprint(frame),
            pandas_fingerprint(frame.copy()),
        )

    def test_mapping_fingerprint_is_key_order_independent(self):
        a = pd.Series([1.0], index=pd.to_datetime(["2025-01-02"]))
        b = pd.Series([2.0], index=pd.to_datetime(["2025-01-03"]))

        self.assertEqual(
            mapping_fingerprint({"a": a, "b": b}),
            mapping_fingerprint({"b": b, "a": a}),
        )

    def test_data_change_changes_fingerprint(self):
        first = pd.Series([1.0], index=pd.to_datetime(["2025-01-02"]))
        second = pd.Series([1.1], index=first.index)

        self.assertNotEqual(
            pandas_fingerprint(first),
            pandas_fingerprint(second),
        )


if __name__ == "__main__":
    unittest.main()
