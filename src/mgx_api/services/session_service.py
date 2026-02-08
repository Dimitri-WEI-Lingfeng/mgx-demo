"""Session management service."""
import time
import uuid
from pathlib import Path

import aiofiles

from shared.config import settings
from mgx_api.dao import SessionDAO
from mgx_api.services.session_running_service import SessionRunningService


class SessionService:
    """Session business logic."""
    
    def __init__(self):
        """Initialize SessionService."""
        self.dao = SessionDAO()
    
    async def create_session(self, name: str, framework: str, username: str) -> dict:
        """
        Create a new session/app and initialize its workspace.
        
        Args:
            name: App name
            framework: Framework template (nextjs, fastapi-vite)
            username: Creator username
            
        Returns:
            Session document
        """
        session_id = str(uuid.uuid4())
        workspace_id = session_id
        
        # Create workspace directory
        workspace_path = Path(settings.workspaces_root) / workspace_id
        workspace_path.mkdir(parents=True, exist_ok=True)
        
        # Create initial README
        readme_path = workspace_path / "README.md"
        async with aiofiles.open(readme_path, "w") as f:
            await f.write(f"# {name}\n\nGenerated app using {framework} framework.\n")
        
        # Save session to database
        session_doc = {
            "session_id": session_id,
            "name": name,
            "framework": framework,
            "workspace_id": workspace_id,
            "workspace_path": str(workspace_path),
            "creator": username,
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        
        await self.dao.create(session_doc)
        # is_running comes from Redis; new session has no agent
        session_doc["is_running"] = False
        return session_doc
    
    async def get_session(self, session_id: str) -> dict | None:
        """
        Get session by ID.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session document or None (with is_running from Redis)
        """
        session = await self.dao.find_by_id(session_id)
        if session is None:
            return None
        session["is_running"] = SessionRunningService().is_running(session_id)
        return session
    
    async def list_user_sessions(self, username: str) -> list[dict]:
        """
        List all sessions for a user.
        
        Args:
            username: Username
            
        Returns:
            List of session documents (with is_running from Redis)
        """
        sessions = await self.dao.find_by_username(username)
        if not sessions:
            return sessions
        session_ids = [s["session_id"] for s in sessions]
        running_map = SessionRunningService().is_running_batch(session_ids)
        for s in sessions:
            s["is_running"] = running_map.get(s["session_id"], False)
        return sessions
