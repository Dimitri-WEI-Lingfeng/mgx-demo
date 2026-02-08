"""Workspace file operation routes."""
from fastapi import APIRouter, Depends, HTTPException, Query

from mgx_api.dependencies import get_current_user
from mgx_api.schemas import FileContent, FileResponse, FileTreeResponse, FileTreeNode
from mgx_api.services import WorkspaceService

router = APIRouter()


def _dict_to_tree_node(d: dict) -> FileTreeNode:
    """Convert dict to FileTreeNode recursively."""
    children = d.get("children")
    return FileTreeNode(
        name=d["name"],
        path=d["path"],
        is_dir=d["is_dir"],
        size=d.get("size"),
        children=[_dict_to_tree_node(c) for c in children] if children else None,
    )


def _entry_to_tree_node(e: dict) -> FileTreeNode:
    """Convert flat entry to FileTreeNode (no children)."""
    return FileTreeNode(
        name=e["name"],
        path=e["path"],
        is_dir=e["is_dir"],
        size=e.get("size"),
        children=None,
    )


@router.get("/workspaces/{workspace_id}/entries", response_model=FileTreeResponse)
async def list_workspace_tree(
    workspace_id: str,
    dir: str | None = Query(None, description="List only one level under this path; omit for full tree"),
    current_user: dict = Depends(get_current_user),
):
    """List file tree of workspace. With dir: one level only; without: full tree."""
    try:
        service = WorkspaceService()
        if dir is not None:
            entries = await service.list_directory(workspace_id, dir)
            return FileTreeResponse(
                entries=[_entry_to_tree_node(e) for e in entries],
            )
        entries = await service.list_tree(workspace_id)
        return FileTreeResponse(
            entries=[_dict_to_tree_node(e) for e in entries],
        )
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/workspaces/{workspace_id}/files", response_model=FileResponse)
async def read_workspace_file(
    workspace_id: str,
    path: str = Query(..., description="Relative path to file"),
    current_user: dict = Depends(get_current_user),
):
    """Read a file from workspace."""
    try:
        service = WorkspaceService()
        content, size = await service.read_file(workspace_id, path)
        return FileResponse(path=path, content=content, size=size)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/workspaces/{workspace_id}/files", response_model=FileResponse)
async def write_workspace_file(
    workspace_id: str,
    body: FileContent,
    path: str = Query(..., description="Relative path to file"),
    current_user: dict = Depends(get_current_user),
):
    """Write content to a file in workspace."""
    try:
        service = WorkspaceService()
        size = await service.write_file(workspace_id, path, body.content)
        return FileResponse(path=path, content=body.content, size=size)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
