"""Session/App related schemas."""
from pydantic import BaseModel


class SessionCreate(BaseModel):
    """Request to create a new session/app."""
    name: str
    framework: str = "fastapi-vite"  # nextjs | fastapi-vite


class SessionResponse(BaseModel):
    """Session/App response."""
    session_id: str
    name: str
    framework: str
    workspace_id: str
    workspace_path: str
    created_at: float
    is_running: bool = False
