"""Background ingestion on startup and every SYNC_INTERVAL_HOURS."""

from __future__ import annotations

import logging
import time

from .config import settings
from .pipeline import run_pipeline
from .stores import get_stores

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("f1lab.worker")


def wait_for_emulators():
    """Wait briefly while Docker starts the two storage APIs."""
    for attempt in range(1, 31):
        try:
            for store in get_stores().values():
                store.ensure_bucket()
            return
        except Exception as exc:
            log.warning("Emulators starting (%d/30): %s", attempt, exc)
            time.sleep(3)
    log.warning("Storage readiness timeout; worker will keep retrying")


def main():
    wait_for_emulators()
    while True:
        try:
            log.info("Refreshing F1 season %d", settings.default_season)
            response = run_pipeline(settings.default_season)
            log.info("Sync result: %s", response["clouds"])
            # If at least one cloud is offline, retry sooner.
            if all(info["ok"] for info in response["clouds"].values()):
                time.sleep(max(settings.sync_interval_hours, 0.1) * 3600)
            else:
                time.sleep(90)
        except Exception:
            log.exception("Ingestion failed. Retrying in 90s.")
            time.sleep(90)


if __name__ == "__main__":
    main()
