# b2_client.py
import io
import uuid
from datetime import date

import boto3
import streamlit as st
from botocore.config import Config


@st.cache_resource
def get_s3():
    """One boto3 client per Streamlit session/process."""
    return boto3.client(
        "s3",
        endpoint_url=st.secrets["b2"]["endpoint"],
        aws_access_key_id=st.secrets["b2"]["key_id"],
        aws_secret_access_key=st.secrets["b2"]["application_key"],
        region_name=st.secrets["b2"]["region"],
        config=Config(signature_version="s3v4"),
    )


def _bucket() -> str:
    return st.secrets["b2"]["bucket_name"]


def make_key(user_id: str, original_name: str) -> str:
    """Build a collision-proof key: receipts/<user>/<yyyy>/<mm>/<uuid>.<ext>"""
    ext = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else "bin"
    return f"receipts/{user_id}/{date.today():%Y/%m}/{uuid.uuid4()}.{ext}"


def upload_to_b2(file_bytes: bytes, original_name: str, user_id: str,
                 content_type: str | None = None) -> str:
    """Upload bytes to B2, return the object key."""
    key = make_key(user_id, original_name)
    extra = {"ContentType": content_type} if content_type else {}
    get_s3().put_object(
        Bucket=_bucket(),
        Key=key,
        Body=file_bytes,
        **extra,
    )
    return key


def presigned_url(b2_key: str, expires: int = 3600) -> str:
    """Time-limited URL for viewing/downloading a private object."""
    return get_s3().generate_presigned_url(
        "get_object",
        Params={"Bucket": _bucket(), "Key": b2_key},
        ExpiresIn=expires,
    )


def download_bytes(b2_key: str) -> bytes:
    """Fetch the object into memory (use for small files only)."""
    obj = get_s3().get_object(Bucket=_bucket(), Key=b2_key)
    return obj["Body"].read()


def delete_from_b2(b2_key: str) -> None:
    """Remove an object. Call this when its receipt row is deleted."""
    get_s3().delete_object(Bucket=_bucket(), Key=b2_key)