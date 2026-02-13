"""
Utilities for handling files created by the code interpreter.

When the Jupyter code executor runs user code that writes files to /mnt/data/,
those files are collected as base64-encoded data and returned in the execution
result.  This module:

1. Uploads those files into Open WebUI's storage so they get a proper file ID
   and are served through the existing /api/v1/files/{id}/content endpoint.
2. Replaces any ``sandbox:/mnt/data/<filename>`` references (a convention used
   by many LLMs) in output text with real download URLs.
"""

import base64
import io
import logging
import mimetypes
import re
from typing import Optional

from fastapi import Request, UploadFile

from open_webui.routers.files import upload_file_handler

log = logging.getLogger(__name__)

# ── Regex that matches sandbox:/mnt/data/<filename> links ────────────────
#   Covers both bare URLs and Markdown-style links:
#     sandbox:/mnt/data/output.csv
#     [download](sandbox:/mnt/data/output.csv)
_SANDBOX_PATH_RE = re.compile(r"sandbox:/mnt/data/([^\s\)\]\"']+)")


def process_code_interpreter_files(
    request: Request,
    raw_files: list[dict],
    metadata: dict,
    user,
) -> dict[str, str]:
    """Upload files from code execution to Open WebUI storage.

    Args:
        request:   FastAPI request (needed by upload_file_handler).
        raw_files: List of dicts with keys ``name``, ``data`` (base64), ``size``.
        metadata:  Chat metadata dict (passed through to file metadata).
        user:      The authenticated user object.

    Returns:
        A mapping of ``{filename: download_url}`` for every successfully
        uploaded file.
    """
    file_url_map: dict[str, str] = {}

    for file_info in raw_files:
        try:
            name = file_info.get("name", "")
            data_b64 = file_info.get("data", "")
            if not name or not data_b64:
                continue

            file_bytes = base64.b64decode(data_b64)
            content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"

            upload_file = UploadFile(
                file=io.BytesIO(file_bytes),
                filename=name,
                headers={"content-type": content_type},
            )

            file_item = upload_file_handler(
                request,
                file=upload_file,
                metadata={
                    "source": "code_interpreter",
                    "chat_id": metadata.get("chat_id", ""),
                },
                process=False,
                user=user,
            )

            # Build the download URL using the files router.
            download_url = f"/api/v1/files/{file_item.id}/content/{name}"
            file_url_map[name] = download_url

            log.info(
                "Code interpreter file uploaded: %s -> %s (size=%d)",
                name,
                download_url,
                len(file_bytes),
            )
        except Exception as exc:
            log.error("Failed to upload code interpreter file %s: %s", name, exc)

    return file_url_map


def replace_sandbox_links(
    text: str,
    file_url_map: Optional[dict[str, str]] = None,
) -> str:
    """Replace ``sandbox:/mnt/data/<filename>`` references in *text*.

    If *file_url_map* is provided, known filenames are replaced with their
    real download URLs.  Unknown filenames are left as-is (so the link at
    least shows the filename even if the file couldn't be uploaded).

    When called without a *file_url_map* (e.g. from serialize_content_blocks),
    the function still cleans up sandbox links by stripping the ``sandbox:``
    prefix, turning them into ``/mnt/data/<filename>`` (which won't work but
    is no worse).  The primary replacement is expected to happen earlier when
    the map is available.
    """
    if not text:
        return text

    def _replacer(match: re.Match) -> str:
        filename = match.group(1)
        if file_url_map and filename in file_url_map:
            return file_url_map[filename]
        # If we don't have a mapping for this file, leave it unchanged.
        return match.group(0)

    return _SANDBOX_PATH_RE.sub(_replacer, text)
