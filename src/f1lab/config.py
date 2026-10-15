"""Runtime config, overridable via Docker Compose environment variables."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    aws_endpoint: str = os.getenv("AWS_ENDPOINT_URL", "http://localhost:5000")
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")
    aws_bucket: str = os.getenv("AWS_S3_BUCKET", "f1-data-lake")
    gcp_project: str = os.getenv("GCP_PROJECT", "f1-lab-local")
    gcs_bucket: str = os.getenv("GCS_BUCKET", "f1-data-lake-gcp")
    default_season: int = int(os.getenv("F1_SEASON", "2025"))
    sync_interval_hours: float = float(os.getenv("SYNC_INTERVAL_HOURS", "6"))
    user_agent: str = os.getenv("API_USER_AGENT", "F1MultiCloudLab/1.0")


settings = Settings()
