from collections import defaultdict
import json

from f1lab.sources import DemoSource
from f1lab.pipeline import load_cloud, run_pipeline, manifest_key


class MemoryStore:
    bucket = "test-f1"

    def __init__(self):
        self.blobs = {}

    def ensure_bucket(self):
        pass

    def put(self, key, payload, content_type):
        self.blobs[key] = payload

    def get(self, key):
        return self.blobs.get(key)


def test_dual_cloud_equal_hashes_and_readable_parquet():
    stores = {"aws": MemoryStore(), "gcp": MemoryStore()}
    output = run_pipeline(2025, demo=True, stores=stores, source=DemoSource())
    assert all(info["ok"] for info in output["clouds"].values())
    for store in stores.values():
        manifest, dfs = load_cloud(store, 2025)
        assert manifest["results"] == 15
        assert len(dfs["results"]) == 15
        assert manifest_key(2025) in store.blobs
        assert any(k.startswith("raw/results/") for k in store.blobs)
    key = output["manifest"]["parquet_keys"]["results"]
    assert stores["aws"].blobs[key] == stores["gcp"].blobs[key]
