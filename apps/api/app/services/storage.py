"""MinIO-backed object storage for uploaded documents (docs/KNOWLEDGE_SYSTEM.md).

A thin wrapper, not a generic storage abstraction — if a second storage
backend is ever needed, promote this to an interface then (docs/DATABASE_DESIGN.md's
"don't over-engineer" principle applies here too).
"""

import io
from functools import lru_cache

from minio import Minio

from app.core.config import get_settings


@lru_cache
def get_storage_client() -> Minio:
    settings = get_settings()
    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)
    return client


def upload_bytes(object_name: str, content: bytes, content_type: str) -> str:
    """Returns `object_name` unchanged — the bucket is deployment config
    (`settings.minio_bucket`), not per-document data, so `Document.storage_path`
    stores only the object key.
    """
    settings = get_settings()
    client = get_storage_client()
    client.put_object(
        settings.minio_bucket,
        object_name,
        data=io.BytesIO(content),
        length=len(content),
        content_type=content_type,
    )
    return object_name


def download_bytes(object_name: str) -> bytes:
    settings = get_settings()
    client = get_storage_client()
    response = client.get_object(settings.minio_bucket, object_name)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()
