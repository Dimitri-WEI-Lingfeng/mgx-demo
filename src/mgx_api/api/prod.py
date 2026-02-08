"""Production build and deployment routes."""
from fastapi import APIRouter, Depends, HTTPException, Query

from mgx_api.dependencies import get_current_user
from mgx_api.schemas import ProdBuildResponse, ProdContainerResponse
from mgx_api.services import SessionService, DockerService

router = APIRouter()


@router.post("/apps/{session_id}/prod/build", response_model=ProdBuildResponse)
async def build_prod(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Build production image for an app."""
    session_service = SessionService()
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    workspace_id = session["workspace_id"]
    app_name = session["name"]
    framework = session["framework"]
    
    try:
        docker_service = DockerService()
        result = await docker_service.build_prod_image(workspace_id, app_name, framework)
        return ProdBuildResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Build failed: {str(e)}")


@router.post("/apps/{session_id}/prod/deploy", response_model=ProdContainerResponse)
async def deploy_prod(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Deploy production container for an app."""
    session_service = SessionService()
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    workspace_id = session["workspace_id"]
    app_name = session["name"]
    image_tag = f"mgx-prod-{app_name}:{workspace_id}"
    
    try:
        docker_service = DockerService()
        container_info = await docker_service.start_prod_container(workspace_id, app_name, image_tag)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deploy failed: {str(e)}")
    # todo: port url
    return ProdContainerResponse(
        **container_info,
    )


@router.post("/apps/{session_id}/prod/stop")
async def stop_prod(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Stop production container for an app."""
    session_service = SessionService()
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    workspace_id = session["workspace_id"]

    try:
        docker_service = DockerService()
        await docker_service.stop_prod_container(workspace_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop prod container: {str(e)}")
    
    return {"status": "stopped"}


@router.get("/apps/{session_id}/prod/status", response_model=ProdContainerResponse)
async def get_prod_status(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get production container status."""
    session_service = SessionService()
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    workspace_id = session["workspace_id"]

    docker_service = DockerService()
    status = await docker_service.get_prod_container_status(workspace_id)
    if not status:
        return ProdContainerResponse(status="not_created")

    prod_url = f"/apps/{workspace_id}/prod/" if status["status"] == "running" else None
    
    return ProdContainerResponse(
        **status,
        prod_url=prod_url,
    )


@router.get("/apps/{session_id}/logs")
async def get_logs(
    session_id: str,
    target: str = Query("dev", description="dev or prod"),
    tail: int = Query(100, description="Number of log lines"),
    current_user: dict = Depends(get_current_user),
):
    """
    Get container logs (readonly terminal/logs).
    
    Returns the last N lines of container logs.
    """
    session_service = SessionService()
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    workspace_id = session["workspace_id"]
    
    try:
        docker_service = DockerService()
        logs = await docker_service.get_container_logs(workspace_id, target, tail)
        return {"logs": logs, "target": target, "tail": tail}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch logs: {str(e)}")
