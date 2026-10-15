"""One extraction produces identical data lake objects in AWS S3 and GCP GCS."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import logging
import time
import uuid

import pandas as pd

from .sources import DemoSource, JolpicaSource
from .stores import get_stores
from .transform import normalize

LOGGER = logging.getLogger(__name__)


def _json(obj) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _parquet(df: pd.DataFrame) -> bytes:
    sink = BytesIO()
    df.to_parquet(sink, engine="pyarrow", compression="snappy", index=False)
    return sink.getvalue()


def manifest_key(season: int) -> str:
    return f"_control/season={season}/latest.json"


def run_pipeline(season: int, demo: bool = False, stores: dict | None = None, source=None) -> dict:
    """Fetch and publish to clouds independently; manifest commit happens last per cloud."""
    if season < 1950 or season > datetime.now(timezone.utc).year + 1:
        raise ValueError("Invalid Formula 1 season")
    started = time.monotonic()
    source = source or (DemoSource() if demo else JolpicaSource())
    extracted = source.extract(season)
    frames = normalize(extracted, season)
    ingested_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]

    objects = {}
    for dataset, pages in extracted.raw_pages.items():
        for i, raw in enumerate(pages):
            key = f"raw/{dataset}/season={season}/run={run_id}/page-{i:04d}.json"
            objects[key] = (_json(raw), "application/json")

    hashes = {}
    parquet_keys = {}
    for dataset, frame in frames.items():
        key = f"silver/{dataset}/season={season}/run={run_id}/{dataset}.parquet"
        blob = _parquet(frame)
        objects[key] = (blob, "application/vnd.apache.parquet")
        hashes[dataset] = sha256(blob).hexdigest()
        parquet_keys[dataset] = key

    summary = {
        "season": season, "source": "Jolpica F1 API" if not demo else "Demo local (no real)",
        "mode": extracted.mode, "ingested_at_utc": ingested_at,
        "scheduled_races": len(frames["races"]),
        "races_with_results": frames["results"]["round"].nunique(),
        "results": len(frames["results"]),
        "drivers": frames["results"]["driver_id"].nunique(),
        "constructors": frames["results"]["constructor_id"].nunique(),
    }
    gold_key = f"gold/season={season}/run={run_id}/summary.json"
    objects[gold_key] = (_json(summary), "application/json")
    manifest = {
        **summary, "run_id": run_id, "parquet_sha256": hashes,
        "parquet_keys": parquet_keys, "gold_key": gold_key,
        "raw_page_count": sum(map(len, extracted.raw_pages.values())),
        "written_object_count": len(objects) + 1,
        "extract_transform_seconds": round(time.monotonic() - started, 2),
    }

    stores = stores if stores is not None else get_stores()
    status = {}
    for cloud, store in stores.items():
        try:
            store.ensure_bucket()
            for key, (payload, content_type) in objects.items():
                store.put(key, payload, content_type)
            store.put(manifest_key(season), _json(manifest), "application/json")
            status[cloud] = {"ok": True, "bucket": store.bucket, "objects": len(objects) + 1}
            LOGGER.info("Committed %s: %s", cloud, run_id)
        except Exception as exc:
            LOGGER.exception("Upload failed for cloud %s", cloud)
            status[cloud] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return {"manifest": manifest, "clouds": status}


def load_cloud(store, season: int) -> tuple[dict | None, dict[str, pd.DataFrame]]:
    """Download real Parquet bytes from selected cloud and verify SHA-256."""
    manifest_data = store.get(manifest_key(season))
    if manifest_data is None:
        return None, {}
    manifest = json.loads(manifest_data)
    frames = {}
    for name in ("races", "results", "standings"):
        key = manifest["parquet_keys"][name]
        parquet_bytes = store.get(key)
        if parquet_bytes is None:
            raise RuntimeError(f"Missing {key}")
        expected = manifest["parquet_sha256"][name]
        if sha256(parquet_bytes).hexdigest() != expected:
            raise RuntimeError(f"SHA256 mismatch in {key}")
        frames[name] = pd.read_parquet(BytesIO(parquet_bytes))
    return manifest, frames
