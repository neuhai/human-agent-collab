"""
AWS S3 uploads for annotation-mode screenshots and HTML snapshots.

Requires: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION, S3_BUCKET
"""

from __future__ import annotations

import os
import re
from typing import Optional, Tuple
from urllib.parse import unquote


def is_s3_configured() -> bool:
    return bool(
        (os.environ.get('AWS_ACCESS_KEY_ID') or '').strip()
        and (os.environ.get('AWS_SECRET_ACCESS_KEY') or '').strip()
        and (os.environ.get('S3_BUCKET') or '').strip()
        and (os.environ.get('AWS_REGION') or '').strip()
    )


def _client():
    import boto3

    return boto3.client(
        's3',
        region_name=os.environ['AWS_REGION'].strip(),
        aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'].strip(),
        aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'].strip(),
    )


def build_annotation_key(session_id: str, action_id: str, suffix: str) -> str:
    """Key prefix for annotation assets."""
    safe_session = re.sub(r'[^a-zA-Z0-9._-]', '_', session_id)[:200]
    return f'annotation/{safe_session}/{action_id}_{suffix}'


def build_post_annotation_asset_key(session_id: str, participant_id: str, action_id: str, filename: str) -> str:
    """S3 key for post-session annotator direct uploads (browser -> S3)."""
    safe_s = re.sub(r'[^a-zA-Z0-9._-]', '_', session_id)[:200]
    safe_p = re.sub(r'[^a-zA-Z0-9._-]', '_', participant_id)[:200]
    safe_a = re.sub(r'[^a-zA-Z0-9._-]', '_', action_id)[:80]
    safe_name = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)[:120]
    return f'post_annotation/{safe_s}/{safe_p}/{safe_a}/{safe_name}'


def upload_bytes(key: str, body: bytes, content_type: str) -> str:
    """Upload object; returns s3://bucket/key"""
    bucket = os.environ['S3_BUCKET'].strip()
    c = _client()
    c.put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type)
    return f's3://{bucket}/{key}'


def parse_s3_uri(uri: str) -> Tuple[str, str]:
    """s3://bucket/key -> (bucket, key)"""
    if not uri.startswith('s3://'):
        raise ValueError('not an s3 uri')
    rest = uri[5:]
    i = rest.find('/')
    if i < 0:
        raise ValueError('invalid s3 uri')
    bucket, key = rest[:i], rest[i + 1 :]
    return bucket, unquote(key)


def get_bucket() -> str:
    return os.environ['S3_BUCKET'].strip()


def presign_put_url(key: str, content_type: str, expires_in: int = 3600) -> Optional[str]:
    """HTTPS presigned PUT for browser direct upload. Bucket must allow CORS PUT from your frontend origin."""
    if not is_s3_configured():
        return None
    bucket = get_bucket()
    c = _client()
    return c.generate_presigned_url(
        'put_object',
        Params={'Bucket': bucket, 'Key': key, 'ContentType': content_type},
        ExpiresIn=expires_in,
    )


def s3_uri_for_key(key: str) -> str:
    return f's3://{get_bucket()}/{key}'


def presign_get_url(s3_uri: str, expires_in: int = 3600) -> Optional[str]:
    """HTTPS presigned GET URL, or None if misconfigured."""
    if not is_s3_configured():
        return None
    try:
        bucket, key = parse_s3_uri(s3_uri)
    except Exception:
        return None
    c = _client()
    return c.generate_presigned_url(
        'get_object',
        Params={'Bucket': bucket, 'Key': key},
        ExpiresIn=expires_in,
    )


def resolve_s3_fields_in_entry(entry: dict, expires_in: int = 3600) -> dict:
    """Replace s3:// screenshot/html_snapshot with presigned HTTPS URLs for API responses."""
    out = dict(entry)
    for field in ('screenshot', 'html_snapshot'):
        v = out.get(field)
        if isinstance(v, str) and v.startswith('s3://'):
            url = presign_get_url(v, expires_in=expires_in)
            if url:
                out[field] = url
    return out


def presign_saved_annotation_asset_urls(saved: dict, expires_in: int = 3600) -> dict:
    """
    For saved post-annotation payload (action_id -> dict), build presigned GET URLs
    for screenshot_s3 / html_snapshot_s3 fields (browser display).
    """
    out: dict = {}
    if not saved or not isinstance(saved, dict):
        return out
    for aid, row in saved.items():
        if not isinstance(row, dict):
            continue
        urls = {}
        for field in ('screenshot_s3', 'html_snapshot_s3'):
            v = row.get(field)
            if isinstance(v, str) and v.startswith('s3://'):
                u = presign_get_url(v, expires_in=expires_in)
                if u:
                    urls[field] = u
        if urls:
            out[str(aid)] = urls
    return out
