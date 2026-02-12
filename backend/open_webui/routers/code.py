import logging
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from open_webui.constants import ERROR_MESSAGES
from open_webui.env import SRC_LOG_LEVELS, DATA_DIR
from open_webui.models.code_sessions import (
    CodeSessions,
    CodeSessionResponse,
)
from open_webui.utils.auth import get_verified_user
from open_webui.utils.code_executor import DockerCodeExecutor

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()

# Initialize code sessions manager
code_sessions = CodeSessions()

# Workspace base directory
WORKSPACE_BASE_DIR = Path(DATA_DIR) / "workspaces"
WORKSPACE_BASE_DIR.mkdir(parents=True, exist_ok=True)


def get_workspace_path(user_id: str, session_id: str) -> Path:
    """
    Get workspace path for a user session.
    
    Args:
        user_id: User ID
        session_id: Session ID
        
    Returns:
        Path to workspace directory
    """
    return WORKSPACE_BASE_DIR / user_id / session_id


############################
# Create Code Session
############################


@router.post("/sessions", response_model=CodeSessionResponse)
async def create_code_session(
    request: Request,
    user=Depends(get_verified_user)
):
    """
    Create a new code execution session.
    Creates a per-user workspace directory under /app/backend/data/workspaces/
    
    Returns:
        CodeSessionResponse with session details
    """
    try:
        user_id = user.id
        
        # Try to create session in database first (with empty workspace path)
        session = code_sessions.insert_new_session(
            user_id=user_id,
            workspace_path=""  # Temporary, will update after creating directory
        )
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create code session"
            )
        
        session_id = session.id
        workspace_path = get_workspace_path(user_id, session_id)
        
        # Create workspace directory
        workspace_path.mkdir(parents=True, exist_ok=True)
        
        # Update session with actual workspace path
        session = code_sessions.update_session_workspace_path(session_id, str(workspace_path))
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update workspace path"
            )
        
        log.info(f"Created code session {session_id} for user {user_id}")
        
        return CodeSessionResponse(
            id=session.id,
            user_id=session.user_id,
            workspace_path=session.workspace_path,
            created_at=session.created_at,
            updated_at=session.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error creating code session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create code session: {str(e)}"
        )


############################
# Get Code Session
############################


@router.get("/sessions/{session_id}", response_model=CodeSessionResponse)
async def get_code_session(
    session_id: str,
    user=Depends(get_verified_user)
):
    """
    Get details of a code execution session.
    
    Args:
        session_id: Session ID
        
    Returns:
        CodeSessionResponse with session details
    """
    session = code_sessions.get_session_by_id(session_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND
        )
    
    # Check ownership
    if session.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED
        )
    
    return CodeSessionResponse(
        id=session.id,
        user_id=session.user_id,
        workspace_path=session.workspace_path,
        created_at=session.created_at,
        updated_at=session.updated_at
    )


############################
# List Code Sessions
############################


@router.get("/sessions", response_model=list[CodeSessionResponse])
async def list_code_sessions(
    user=Depends(get_verified_user)
):
    """
    List all code execution sessions for the current user.
    
    Returns:
        List of CodeSessionResponse
    """
    sessions = code_sessions.get_sessions_by_user_id(user.id)
    
    return [
        CodeSessionResponse(
            id=session.id,
            user_id=session.user_id,
            workspace_path=session.workspace_path,
            created_at=session.created_at,
            updated_at=session.updated_at
        )
        for session in sessions
    ]


############################
# Delete Code Session
############################


@router.delete("/sessions/{session_id}")
async def delete_code_session(
    session_id: str,
    user=Depends(get_verified_user)
):
    """
    Delete a code execution session and its workspace.
    
    Args:
        session_id: Session ID
        
    Returns:
        Success message
    """
    session = code_sessions.get_session_by_id(session_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND
        )
    
    # Check ownership
    if session.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED
        )
    
    # Delete workspace directory if it exists
    workspace_path = Path(session.workspace_path)
    if workspace_path.exists():
        try:
            shutil.rmtree(workspace_path)
            log.info(f"Deleted workspace directory: {workspace_path}")
        except Exception as e:
            log.error(f"Error deleting workspace directory: {e}")
    
    # Delete session from database
    success = code_sessions.delete_session_by_id(session_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete code session"
        )
    
    log.info(f"Deleted code session {session_id}")
    
    return {"success": True, "message": "Code session deleted successfully"}


############################
# Execute Code
############################


class CodeExecutionRequest(BaseModel):
    code: str
    timeout: Optional[int] = 30


class CodeExecutionResponse(BaseModel):
    success: bool
    output: str
    error: str
    exit_code: int


@router.post("/sessions/{session_id}/execute", response_model=CodeExecutionResponse)
async def execute_code(
    session_id: str,
    request: CodeExecutionRequest,
    user=Depends(get_verified_user)
):
    """
    Execute Python code in a Docker container for the given session.
    
    Args:
        session_id: Session ID
        request: Code execution request with code and optional timeout
        
    Returns:
        CodeExecutionResponse with execution results
    """
    session = code_sessions.get_session_by_id(session_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND
        )
    
    # Check ownership
    if session.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED
        )
    
    try:
        # Initialize Docker executor
        executor = DockerCodeExecutor()
        
        # Ensure Python image is available
        if not executor.check_image_exists():
            log.info("Python Docker image not found, pulling...")
            if not executor.pull_image():
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to pull Python Docker image"
                )
        
        # Execute code
        workspace_path = Path(session.workspace_path)
        result = executor.execute_python_code(
            code=request.code,
            workspace_path=workspace_path,
            timeout=request.timeout
        )
        
        executor.close()
        
        log.info(f"Code execution completed for session {session_id}")
        
        return CodeExecutionResponse(
            success=result["success"],
            output=result["output"],
            error=result["error"],
            exit_code=result["exit_code"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Error executing code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Code execution failed: {str(e)}"
        )
