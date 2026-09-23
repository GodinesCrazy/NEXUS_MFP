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


if __name__ == "__main__":
    unittest.main()
