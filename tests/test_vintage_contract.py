import tempfile
import unittest
from pathlib import Path

import pandas as pd

from nexus_core.vintages import VintageSnapshotStore


class VintageContractTests(unittest.TestCase):
    def test_as_of_never_selects_future_retrieval(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = VintageSnapshotStore(Path(tmp))
            old = pd.Series([1.0], index=pd.to_datetime(["2020-01-01"]), name="x")
            new = pd.Series([2.0], index=pd.to_datetime(["2020-01-01"]), name="x")
            store.write(source="FRED", variable="X", retrieved_at="2020-02-01T00:00:00Z", data=old, frequency="daily", release_lag="1d")
            store.write(source="FRED", variable="X", retrieved_at="2020-03-01T00:00:00Z", data=new, frequency="daily", release_lag="1d")
            frame, metadata = store.as_of("FRED", "X", "2020-02-15T00:00:00Z")
            self.assertEqual(float(frame.iloc[0, 0]), 1.0)
            self.assertTrue(metadata.point_in_time)

    def test_snapshot_is_immutable(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = VintageSnapshotStore(Path(tmp))
            data = pd.Series([1.0], name="x")
            kwargs = dict(source="FRED", variable="X", retrieved_at="2020-02-01T00:00:00Z", data=data, frequency="daily", release_lag="1d")
            store.write(**kwargs)
            with self.assertRaises(FileExistsError):
                store.write(**kwargs)

    def test_alfred_knowledge_date_is_distinct_from_download_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = VintageSnapshotStore(Path(tmp))
            data = pd.Series([7.5], index=pd.to_datetime(["2020-01-01"]), name="x")
            store.write(
                source="ALFRED",
                variable="X",
                retrieved_at="2026-09-23T12:00:00Z",
                knowledge_at="2020-02-01T23:59:59Z",
                source_vintage_date="2020-02-01",
                data=data,
                frequency="daily",
                release_lag="encoded_by_alfred_realtime_period",
            )
            frame, metadata = store.as_of("ALFRED", "X", "2020-02-02T00:00:00Z")
            self.assertEqual(float(frame.iloc[0, 0]), 7.5)
            self.assertEqual(metadata.source_vintage_date, "2020-02-01")
            self.assertTrue(metadata.retrieved_at_utc.startswith("2026-09-23"))

    def test_materialized_series_uses_latest_value_known_at_each_vintage(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = VintageSnapshotStore(Path(tmp))
            for vintage, values in (
                ("2020-02-01", [1.0]),
                ("2020-03-01", [1.1, 2.0]),
            ):
                data = pd.Series(
                    values,
                    index=pd.to_datetime(["2020-01-01", "2020-02-01"][:len(values)]),
                    name="x",
                )
                store.write(
                    source="ALFRED",
                    variable="X",
                    retrieved_at="2026-09-23T12:00:00Z",
                    knowledge_at=f"{vintage}T23:59:59Z",
                    source_vintage_date=vintage,
                    data=data,
                    frequency="monthly",
                    release_lag="encoded",
                )
            timeline = store.known_latest_series("ALFRED", "X")
            self.assertEqual(timeline.tolist(), [1.0, 2.0])


if __name__ == "__main__":
    unittest.main()
