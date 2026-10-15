"""Manual CLI ingestion, also helpful for smoke tests."""

import argparse
import json
import logging
import sys

from .config import settings
from .pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(description="F1 dual-cloud ingestion")
    parser.add_argument("--season", type=int, default=settings.default_season)
    parser.add_argument("--demo", action="store_true", help="Generate fictional sample races without network")
    options = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    result = run_pipeline(options.season, demo=options.demo)
    print(json.dumps(result, indent=2))
    if not all(x["ok"] for x in result["clouds"].values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
