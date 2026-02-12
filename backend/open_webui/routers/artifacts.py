import logging
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import FileResponse

from open_webui.constants import ERROR_MESSAGES
from open_webui.env import SRC_LOG_LEVELS
from open_webui.models.artifacts import (
    Artifacts,
    ArtifactResponse,
)
from open_webui.utils.artifacts import get_artifact_path, delete_artifact_file, DEFAULT_BASE_URL
from open_webui.utils.auth import get_admin_user, get_verified_user

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()


def get_base_url(request: Request) -> str:
    """Get the base URL for artifact downloads from config, with fallback."""
    base_url = (request.app.state.config.CANCHAT_PUBLIC_URL or 
                request.app.state.config.WEBUI_URL or 
                DEFAULT_BASE_URL)
    return base_url.rstrip("/") if base_url else DEFAULT_BASE_URL


############################
# Get Artifact Metadata
############################


@router.get("/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact_metadata(artifact_id: str, request: Request, user=Depends(get_verified_user)):
    """
    Get metadata for a specific artifact.
    Users can only access their own artifacts unless they are admins.
    """
    artifact = Artifacts.get_artifact_by_id(artifact_id)
    
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
    
    # Check ownership or admin access
    if artifact.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )
    
    # Build URL
    base_url = get_base_url(request)
    url = f"{base_url}/api/v1/artifacts/{artifact_id}/content"
    
    return ArtifactResponse(
        **artifact.model_dump(),
        url=url,
    )


############################
# Download Artifact Content
############################


@router.get("/{artifact_id}/content", summary="Download artifact file")
async def download_artifact_content(artifact_id: str, user=Depends(get_verified_user)):
    """
    Download the content of a specific artifact.
    Users can only download their own artifacts unless they are admins.
    """
    artifact = Artifacts.get_artifact_by_id(artifact_id)
    
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
    
    # Check ownership or admin access
    if artifact.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )
    
    try:
        # Get artifact file path with path traversal prevention
        artifact_path = get_artifact_path(artifact.relative_path)
        
        # Check if file exists
        if not artifact_path.is_file():
            log.error(f"Artifact file not found: {artifact_path}")
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Artifact file no longer exists on disk",
            )
        
        # Handle Unicode filenames
        encoded_filename = quote(artifact.filename)  # RFC5987 encoding
        
        # Set headers for file download
        headers = {
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        }
        
        # Return file response
        return FileResponse(
            artifact_path,
            media_type=artifact.mime_type,
            headers=headers,
            filename=artifact.filename,
        )
    
    except ValueError as e:
        # Path traversal or invalid path
        log.error(f"Invalid artifact path for artifact {artifact_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT("Invalid artifact path"),
        )
    except Exception as e:
        log.error(f"Error downloading artifact {artifact_id}: {type(e).__name__}")
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES.DEFAULT("Error downloading artifact"),
        )


############################
# List User Artifacts
############################


@router.get("/", response_model=list[ArtifactResponse])
async def list_user_artifacts(request: Request, user=Depends(get_verified_user)):
    """
    List all artifacts for the current user.
    Admins can see all artifacts.
    """
    if user.role == "admin":
        artifacts = Artifacts.get_artifacts()
    else:
        artifacts = Artifacts.get_artifacts_by_user_id(user.id)
    
    # Build URLs for each artifact
    base_url = get_base_url(request)
    
    return [
        ArtifactResponse(
            **artifact.model_dump(),
            url=f"{base_url}/api/v1/artifacts/{artifact.id}/content",
        )
        for artifact in artifacts
    ]


############################
# Delete Artifact
############################


@router.delete("/{artifact_id}", summary="Delete artifact")
async def delete_artifact(artifact_id: str, user=Depends(get_verified_user)):
    """
    Delete an artifact.
    Users can only delete their own artifacts unless they are admins.
    """
    artifact = Artifacts.get_artifact_by_id(artifact_id)
    
    if not artifact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )
    
    # Check ownership or admin access
    if artifact.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )
    
    try:
        # Delete from database
        if Artifacts.delete_artifact_by_id(artifact_id):
            # Delete file from disk
            delete_artifact_file(artifact.relative_path)
            
            return {"success": True, "message": "Artifact deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=ERROR_MESSAGES.DEFAULT("Error deleting artifact"),
            )
    except Exception as e:
        log.error(f"Error deleting artifact {artifact_id}: {type(e).__name__}")
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ERROR_MESSAGES.DEFAULT("Error deleting artifact"),
        )
