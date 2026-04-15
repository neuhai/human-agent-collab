"""
Load the Map Task guide map from disk and encode for OpenAI/Azure vision chat completions.

Uses the same file layout as /api/maps: uploads/maps first, then map_assets fallback.
"""
from __future__ import annotations

import base64
import mimetypes
import os
from typing import Any, Dict, Optional

from werkzeug.utils import secure_filename

_AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_ROOT = os.path.dirname(_AGENT_DIR)

_MAP_DIRS = (
    os.path.join(_BACKEND_ROOT, "uploads", "maps"),
    os.path.join(_BACKEND_ROOT, "map_assets"),
)

# Vision models accept raster images; PDF/TXT maps are not inlined here.
_VISION_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def resolve_maptask_map_file_path(map_obj: Any) -> Optional[str]:
    """Return absolute path to map file if it exists on disk."""
    if not isinstance(map_obj, dict):
        return None
    fn = map_obj.get("filename")
    if not fn:
        fp = map_obj.get("file_path") or ""
        if isinstance(fp, str) and fp.strip():
            fn = fp.strip().rsplit("/", 1)[-1]
    if not fn:
        return None
    safe = secure_filename(str(fn))
    if not safe:
        return None
    for d in _MAP_DIRS:
        path = os.path.join(d, safe)
        if os.path.isfile(path):
            return path
    return None


def guide_map_data_url_for_openai_vision(
    participant: Dict[str, Any], experiment_type: str
) -> Optional[str]:
    """
    Build a data: URL (base64) for the guide's assigned map image, for use in
    chat.completions image_url.url (OpenAI / Azure OpenAI vision).
    """
    if (experiment_type or "").strip().lower() != "maptask":
        return None
    role = (participant.get("role") or "").strip().lower()
    if role != "guide":
        return None
    exp = participant.get("experiment_params") or {}
    map_obj = exp.get("map")
    path = resolve_maptask_map_file_path(map_obj)
    if not path:
        return None
    ext = os.path.splitext(path)[1].lower()
    if ext not in _VISION_EXTS:
        return None
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError:
        return None
    if not raw:
        return None
    mime = mimetypes.guess_type(path)[0] or "image/png"
    b64 = base64.standard_b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"
