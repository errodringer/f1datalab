"""Thin cloud storage adapters. Uses normal AWS and GCP SDKs."""

from __future__ import annotations

from dataclasses import dataclass

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from google.auth.credentials import AnonymousCredentials
from google.cloud import storage
from google.api_core.exceptions import NotFound

from .config import settings


@dataclass
class S3Store:
    label: str = "AWS · S3 (Moto/LocalStack)"

    def __post_init__(self):
        self.bucket = settings.aws_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.aws_endpoint,
            region_name=settings.aws_region,
            aws_access_key_id="test",
            aws_secret_access_key="test",
            config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 3}),
        )

    def ensure_bucket(self):
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code not in ("404", "NoSuchBucket", "NotFound"):
                raise
            kwargs = {"Bucket": self.bucket}
            if settings.aws_region != "us-east-1":
                kwargs["CreateBucketConfiguration"] = {"LocationConstraint": settings.aws_region}
            try:
                self.client.create_bucket(**kwargs)
            except ClientError as inner_exc:
                if inner_exc.response.get("Error", {}).get("Code") not in (
                    "BucketAlreadyExists", "BucketAlreadyOwnedByYou"
                ):
                    raise

    def put(self, key: str, payload: bytes, content_type: str):
        self.client.put_object(Bucket=self.bucket, Key=key, Body=payload, ContentType=content_type)

    def get(self, key: str) -> bytes | None:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except ClientError as exc:
            if str(exc.response.get("Error", {}).get("Code")) in ("NoSuchKey", "404", "NotFound"):
                return None
            raise

    def list_keys(self, prefix: str) -> list[str]:
        paginator = self.client.get_paginator("list_objects_v2")
        return [obj["Key"] for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix)
                for obj in page.get("Contents", [])]


@dataclass
class GCSStore:
    label: str = "GCP · Cloud Storage (emulator)"

    def __post_init__(self):
        self.bucket = settings.gcs_bucket
        # STORAGE_EMULATOR_HOST must point at the emulator (without /storage/v1).
        self.client = storage.Client(project=settings.gcp_project, credentials=AnonymousCredentials())

    def ensure_bucket(self):
        if not self.client.lookup_bucket(self.bucket):
            try:
                self.client.create_bucket(self.bucket)
            except Exception:
                # May have been created concurrently by another worker/dashboard.
                if not self.client.lookup_bucket(self.bucket):
                    raise

    def put(self, key: str, payload: bytes, content_type: str):
        self.client.bucket(self.bucket).blob(key).upload_from_string(payload, content_type=content_type)

    def get(self, key: str) -> bytes | None:
        try:
            return self.client.bucket(self.bucket).blob(key).download_as_bytes()
        except NotFound:
            return None

    def list_keys(self, prefix: str) -> list[str]:
        return [blob.name for blob in self.client.list_blobs(self.bucket, prefix=prefix)]


def get_stores():
    return {"aws": S3Store(), "gcp": GCSStore()}
