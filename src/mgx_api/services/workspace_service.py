"""Workspace file operations service."""
from pathlib import Path

import aiofiles

from shared.config import settings
from shared.utils import safe_join


class WorkspaceService:
    """Workspace file operations business logic."""
    
    async def list_directory(self, workspace_id: str, relative_path: str = "") -> list[dict]:
        """
        List files and directories in a workspace directory.
        
        Args:
            workspace_id: Workspace ID
            relative_path: Relative path within workspace (default: root)
            
        Returns:
            List of directory entries
            
        Raises:
            ValueError: If path is invalid or outside workspace
            FileNotFoundError: If directory doesn't exist
        """
        workspace_root = Path(settings.workspaces_root) / workspace_id
        target_dir = safe_join(workspace_root, relative_path)
        
        if not target_dir.exists():
            raise FileNotFoundError(f"Directory not found: {relative_path}")
        
        if not target_dir.is_dir():
            raise ValueError(f"Not a directory: {relative_path}")
        
        entries = []
        for item in sorted(target_dir.iterdir()):
            rel_path = str(item.relative_to(workspace_root))
            entry = {
                "name": item.name,
                "path": rel_path,
                "is_dir": item.is_dir(),
                "size": item.stat().st_size if item.is_file() else None,
            }
            entries.append(entry)
        
        return entries

    async def list_tree(self, workspace_id: str) -> list[dict]:
        """
        Recursively list entire file tree of workspace.

        Args:
            workspace_id: Workspace ID

        Returns:
            List of root-level tree nodes, each with nested children

        Raises:
            ValueError: If path is invalid or outside workspace
            FileNotFoundError: If workspace root doesn't exist
        """
        def _build_tree(base_path: Path) -> list[dict]:
            if not base_path.exists() or not base_path.is_dir():
                return []
            nodes = []
            for item in sorted(base_path.iterdir()):
                rel_path = str(item.relative_to(workspace_root))
                node = {
                    "name": item.name,
                    "path": rel_path,
                    "is_dir": item.is_dir(),
                    "size": item.stat().st_size if item.is_file() else None,
                }
                if item.is_dir():
                    node["children"] = _build_tree(item)
                nodes.append(node)
            return nodes

        workspace_root = Path(settings.workspaces_root) / workspace_id
        if not workspace_root.exists():
            raise FileNotFoundError(f"Workspace not found: {workspace_id}")
        if not workspace_root.is_dir():
            raise ValueError(f"Not a directory: {workspace_id}")

        return _build_tree(workspace_root)
    
    async def read_file(self, workspace_id: str, relative_path: str) -> tuple[str, int]:
        """
        Read a file from workspace.
        
        Args:
            workspace_id: Workspace ID
            relative_path: Relative path to file
            
        Returns:
            Tuple of (content, size)
            
        Raises:
            ValueError: If path is invalid or outside workspace
            FileNotFoundError: If file doesn't exist
        """
        workspace_root = Path(settings.workspaces_root) / workspace_id
        file_path = safe_join(workspace_root, relative_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")
        
        if not file_path.is_file():
            raise ValueError(f"Not a file: {relative_path}")
        
        async with aiofiles.open(file_path, "r") as f:
            content = await f.read()
        
        size = file_path.stat().st_size
        return content, size
    
    async def write_file(self, workspace_id: str, relative_path: str, content: str) -> int:
        """
        Write content to a file in workspace.
        
        Args:
            workspace_id: Workspace ID
            relative_path: Relative path to file
            content: File content
            
        Returns:
            Written size in bytes
            
        Raises:
            ValueError: If path is invalid or outside workspace
        """
        workspace_root = Path(settings.workspaces_root) / workspace_id
        file_path = safe_join(workspace_root, relative_path)
        
        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with aiofiles.open(file_path, "w") as f:
            await f.write(content)
        
        return file_path.stat().st_size
