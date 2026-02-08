"""Session/App management routes."""
from fastapi import APIRouter, Depends, HTTPException

from mgx_api.dependencies import get_current_user
from mgx_api.schemas import SessionCreate, SessionResponse
from mgx_api.services import SessionService

router = APIRouter()


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    current_user: dict = Depends(get_current_user),
):
    """List all sessions for the current user."""
    username = current_user.get("sub", "unknown")
    service = SessionService()
    sessions = await service.list_user_sessions(username)
    return [SessionResponse(**session) for session in sessions]


@router.post("/sessions", response_model=SessionResponse)
async def create_new_session(
    body: SessionCreate,
    current_user: dict = Depends(get_current_user),
):
    """Create a new session/app and initialize workspace."""
    username = current_user.get("sub", "unknown")
    service = SessionService()
    session = await service.create_session(body.name, body.framework, username)
    return SessionResponse(**session)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session_info(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get session/app info."""
    service = SessionService()
    session = await service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse(**session)
