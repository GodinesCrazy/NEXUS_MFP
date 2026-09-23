import unittest

from nexus_core.provenance import SourceRecord, promotion_eligibility


class ProvenanceContractTests(unittest.TestCase):
    def test_revised_history_blocks_promotion(self):
        records = [
            SourceRecord(
                source="FRED",
                variable="NFCI",
                frequency="weekly",
                release_lag="documented calendar",
                vintage_policy="current revised history",
                point_in_time=False,
            )
        ]

        eligible, blockers = promotion_eligibility(records)

        self.assertFalse(eligible)
        self.assertEqual(blockers, ["NFCI"])

    def test_noncausal_diagnostic_does_not_block(self):
        records = [
            SourceRecord(
                source="diagnostic",
                variable="run_timestamp",
                frequency="run",
                release_lag="none",
                vintage_policy="runtime",
                used_for_causal=False,
                point_in_time=False,
            )
        ]

        eligible, blockers = promotion_eligibility(records)

        self.assertTrue(eligible)
        self.assertEqual(blockers, [])


if __name__ == "__main__":
    unittest.main()
