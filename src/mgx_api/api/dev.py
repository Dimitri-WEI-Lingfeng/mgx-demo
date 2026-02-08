"""Dev container management routes."""
from fastapi import APIRouter, Depends, HTTPException, Query

from mgx_api.dependencies import get_current_user
from shared.config import settings
from mgx_api.schemas import DevContainerResponse
from mgx_api.services import SessionService, DockerService
from mgx_api.services.dev_server_lock import dev_server_lock

router = APIRouter()

@router.get("/apps/{session_id}/dev/status", response_model=DevContainerResponse)
async def get_dev_status(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get dev container status."""
    session_service = SessionService()
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    workspace_id = session["workspace_id"]
    
    docker_service = DockerService()
    status = await docker_service.get_dev_container_status(workspace_id)
    dev_server_params = session.get("dev_server_params")

    # 有 dev_server_params 记录且 status 非 running 时，主动拉起 dev server（加锁防并发）
    if dev_server_params:
        async with dev_server_lock(workspace_id):
            status = await docker_service.get_dev_container_status(workspace_id)
            if not status or status.get("status") != "running":
                # 容器不存在或未运行：先确保容器存在并运行
                await docker_service._ensure_dev_container(
                    workspace_id, dev_server_params.get("framework", session.get("framework", "nextjs"))
                )
                status = await docker_service.get_dev_container_status(workspace_id)
            if status and status.get("status") == "running":
                # 容器运行中：检查 dev server 是否在跑
                dev_server_status_str = await docker_service.get_dev_server_status(workspace_id)
                if "Status: Running" not in dev_server_status_str:
                    await docker_service._start_dev_server_impl(
                        workspace_id=workspace_id,
                        command=dev_server_params.get("command", "npm run dev"),
                        working_dir=dev_server_params.get("working_dir", "/workspace"),
                        port=dev_server_params.get("port", 3000),
                        framework=dev_server_params.get("framework", session.get("framework", "nextjs")),
                    )
                    status = await docker_service.get_dev_container_status(workspace_id)

    if not status:
        return DevContainerResponse(status="not_created")

    # 直连容器 URL（不通过 APISIX 代理，避免 /.next 等路径转发问题）
    host_port = str(list(status["ports"].values())[0]) if status.get("ports") else None
    dev_url = f"{settings.dev_external_host}:{host_port}" if (status["status"] == "running" and host_port) else None

    return DevContainerResponse(
        **status,
        dev_url=dev_url,
    )


@router.get("/apps/{session_id}/dev/server/status")
async def get_dev_server_status(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Get development server status (running inside the dev container).
    
    This endpoint checks if a dev server (like npm run dev) is running
    inside the dev container and returns its status.
    """
    session_service = SessionService()
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    workspace_id = session["workspace_id"]
    
    try:
        docker_service = DockerService()
        status = await docker_service.get_dev_server_status(workspace_id)
        return {"status": "success", "data": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dev server status: {str(e)}")


@router.get("/apps/{session_id}/dev/server/logs")
async def get_dev_server_logs(
    session_id: str,
    tail: int = Query(100, description="Number of log lines to return", ge=0, le=1000),
    current_user: dict = Depends(get_current_user),
):
    """
    Get development server logs (from inside the dev container).
    
    This endpoint returns the logs from the dev server running inside
    the container (e.g., npm run dev output).
    """
    session_service = SessionService()
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    workspace_id = session["workspace_id"]
    
    try:
        docker_service = DockerService()
        logs = await docker_service.get_dev_server_logs(workspace_id, tail)
        return {"status": "success", "logs": logs, "tail": tail}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dev server logs: {str(e)}")
