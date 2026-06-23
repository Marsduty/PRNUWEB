from io import BytesIO
from pathlib import PurePath

from minio import Minio

from app.core.config import settings


def get_minio_client() -> Minio:
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


def build_object_key(prefix: str, owner_id: int | str, filename: str) -> str:
    normalized = str(filename).replace("\\", "/")
    safe_name = PurePath(normalized).name
    return f"{prefix.strip('/')}/{owner_id}/{safe_name}"


def ensure_buckets(client: Minio | None = None) -> None:
    client = client or get_minio_client()
    for bucket in [settings.prnu_image_bucket, settings.prnu_artifact_bucket]:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)


def put_bytes(bucket: str, object_key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    client = get_minio_client()
    client.put_object(bucket, object_key, BytesIO(data), length=len(data), content_type=content_type)


def get_bytes(bucket: str, object_key: str) -> bytes:
    client = get_minio_client()
    response = client.get_object(bucket, object_key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()
