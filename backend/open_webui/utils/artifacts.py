import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import Union

from open_webui.env import DATA_DIR, SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

# Define artifacts storage directory
ARTIFACTS_DIR = Path(DATA_DIR) / "artifacts"


def ensure_artifacts_dir():
    """Ensure the artifacts directory exists."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def store_artifact(
    user_id: str, filename: str, mime_type: str, src_path_or_bytes: Union[str, Path, bytes]
) -> dict:
    """
    Store an artifact file and return metadata.
    
    Args:
        user_id: ID of the user who owns the artifact
        filename: Original filename
        mime_type: MIME type of the file
        src_path_or_bytes: Either a path to the source file or bytes content
        
    Returns:
        dict with keys: id, path, url, size
    """
    # Ensure artifacts directory exists
    ensure_artifacts_dir()
    
    # Generate unique artifact ID
    artifact_id = str(uuid.uuid4())
    
    # Create safe filename with UUID prefix
    safe_filename = f"{artifact_id}_{filename}"
    
    # Sanitize filename to prevent path traversal
    safe_filename = os.path.basename(safe_filename)
    
    # Full path for the artifact
    artifact_path = ARTIFACTS_DIR / safe_filename
    
    # Resolve path to prevent path traversal
    artifact_path = artifact_path.resolve()
    
    # Verify the resolved path is still under ARTIFACTS_DIR
    try:
        if not artifact_path.is_relative_to(ARTIFACTS_DIR.resolve()):
            raise ValueError("Invalid artifact path: path traversal detected")
    except ValueError:
        # is_relative_to raises ValueError if paths are on different drives on Windows
        raise ValueError("Invalid artifact path: path traversal detected")
    
    # Write the file
    if isinstance(src_path_or_bytes, bytes):
        # Write bytes content
        with open(artifact_path, "wb") as f:
            f.write(src_path_or_bytes)
        file_size = len(src_path_or_bytes)
    else:
        # Copy from source path
        src_path = Path(src_path_or_bytes)
        if not src_path.exists():
            raise FileNotFoundError(f"Source file not found: {src_path}")
        shutil.copy2(src_path, artifact_path)
        file_size = artifact_path.stat().st_size
    
    # Get relative path for storage
    relative_path = safe_filename
    
    # Build URL - import here to avoid circular imports
    from open_webui.config import CANCHAT_PUBLIC_URL, WEBUI_URL
    
    base_url = (CANCHAT_PUBLIC_URL.value or WEBUI_URL.value)
    # Remove trailing slash from base_url if present
    base_url = base_url.rstrip("/") if base_url else "http://localhost:3000"
    url = f"{base_url}/api/v1/artifacts/{artifact_id}/content"
    
    log.info(f"Stored artifact {artifact_id} for user {user_id}: {filename} ({file_size} bytes)")
    
    return {
        "id": artifact_id,
        "path": str(artifact_path),
        "relative_path": relative_path,
        "url": url,
        "size": file_size,
    }


def get_artifact_path(relative_path: str) -> Path:
    """
    Get the full path to an artifact file, with path traversal prevention.
    
    Args:
        relative_path: Relative path to the artifact file
        
    Returns:
        Path object to the artifact file
        
    Raises:
        ValueError: If path traversal is detected
    """
    # Construct full path
    artifact_path = ARTIFACTS_DIR / relative_path
    
    # Resolve path to prevent path traversal
    artifact_path = artifact_path.resolve()
    
    # Verify the resolved path is still under ARTIFACTS_DIR
    try:
        if not artifact_path.is_relative_to(ARTIFACTS_DIR.resolve()):
            raise ValueError("Invalid artifact path: path traversal detected")
    except ValueError:
        # is_relative_to raises ValueError if paths are on different drives on Windows
        raise ValueError("Invalid artifact path: path traversal detected")
    
    return artifact_path


def delete_artifact_file(relative_path: str) -> bool:
    """
    Delete an artifact file from disk.
    
    Args:
        relative_path: Relative path to the artifact file
        
    Returns:
        True if file was deleted, False otherwise
    """
    try:
        artifact_path = get_artifact_path(relative_path)
        if artifact_path.exists():
            artifact_path.unlink()
            log.info(f"Deleted artifact file: {relative_path}")
            return True
        return False
    except Exception as e:
        log.error(f"Error deleting artifact file {relative_path}: {e}")
        return False
