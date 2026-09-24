import json
import tempfile
import unittest
import urllib.parse
from pathlib import Path

from nexus_data.alfred import AlfredClient, AlfredVintageIngestor, SeriesSpec


class AlfredContractTests(unittest.TestCase):
    def test_client_requests_exact_realtime_vintage(self):
        urls = []

        def transport(url, timeout):
            urls.append(url)
            return {
                "observations": [
                    {"date": "2020-01-01", "value": "1.25"},
                    {"date": "2020-01-02", "value": "."},
                ]
            }

        client = AlfredClient("a" * 32, transport=transport)
        series = client.observations_as_of("TEST", "2020-02-01", "2020-01-01")
        query = urllib.parse.parse_qs(urllib.parse.urlparse(urls[0]).query)
        self.assertEqual(query["realtime_start"], ["2020-02-01"])
        self.assertEqual(query["realtime_end"], ["2020-02-01"])
        self.assertEqual(float(series.iloc[0]), 1.25)

    def test_transport_error_does_not_expose_api_key(self):
        secret = "b" * 32

        def transport(url, timeout):
            raise OSError(f"failed URL {url}")

        client = AlfredClient(secret, transport=transport)
        with self.assertRaises(RuntimeError) as raised:
            client.vintage_dates("TEST", "2020-01-01", "2020-02-01")
        self.assertNotIn(secret, str(raised.exception))

    def test_ingestion_is_resumable_and_reports_partial(self):
        class FakeClient:
            def vintage_dates(self, series_id, start, end):
                return ["2020-02-01", "2020-03-01"]

            def observations_as_of(self, series_id, vintage_date, observation_start):
                import pandas as pd
                return pd.Series(
                    [1.0], index=pd.to_datetime(["2020-01-01"]), name=series_id
                )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ingestor = AlfredVintageIngestor(FakeClient(), root)
            spec = (SeriesSpec("TEST", "test", "monthly"),)
            first = ingestor.ingest(spec, start="2020-01-01", end="2020-12-31", max_new_vintages=1)
            second = ingestor.ingest(spec, start="2020-01-01", end="2020-12-31", max_new_vintages=1)
            self.assertFalse(first["promotion_ready"])
            self.assertTrue(second["promotion_ready"])
            self.assertEqual(len(list((root / "snapshots" / "ALFRED" / "test").glob("*.csv"))), 2)
            persisted = json.loads((root / "status.json").read_text(encoding="utf-8"))
            self.assertEqual(persisted["status"], "ready")


if __name__ == "__main__":
    unittest.main()
