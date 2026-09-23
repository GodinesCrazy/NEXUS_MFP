import unittest

from nexus_ui.progress import RunProgress


class RunProgressTests(unittest.TestCase):
    def test_progress_is_monotonic_across_out_of_order_logs(self):
        progress = RunProgress()
        progress.start("causal", pid=123)
        progress.ingest("[v1.14] Probando fusión")
        self.assertEqual(progress.snapshot()["progress"], 62)
        progress.ingest("[v1.9] Enriqueciendo noticias")
        self.assertEqual(progress.snapshot()["progress"], 62)

    def test_success_closes_at_one_hundred(self):
        progress = RunProgress()
        progress.start("standard")
        progress.ingest("Causal nested walk-forward")
        progress.finish(0)
        state = progress.snapshot()
        self.assertEqual(state["status"], "completed")
        self.assertEqual(state["progress"], 100)
        self.assertEqual(state["exit_code"], 0)

    def test_failure_never_looks_completed(self):
        progress = RunProgress()
        progress.start("causal")
        progress.finish(2)
        state = progress.snapshot()
        self.assertEqual(state["status"], "failed")
        self.assertLess(state["progress"], 100)

    def test_initial_banner_does_not_fake_completion(self):
        progress = RunProgress()
        progress.start("causal")
        progress.ingest("MFP-3 ONE FILE v1.19 — CAUSAL DRIVER DISCOVERY ENGINE")
        self.assertEqual(progress.snapshot()["progress"], 2)


if __name__ == "__main__":
    unittest.main()
