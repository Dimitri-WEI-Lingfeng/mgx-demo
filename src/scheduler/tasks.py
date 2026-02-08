"""Celery tasks for agent code generation with streaming support."""
import asyncio
import threading
import time
from pathlib import Path

import docker
from celery import Celery
import loguru

from mgx_api.dao import EventDAO
from mgx_api.services import SessionRunningService
from shared.config.settings import settings
from shared.schemas import EventType


# Import agent factory
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


# Initialize Celery app
celery_app = Celery(
    "agent-runtime",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


async def create_agent_container(
    session_id: str,
    workspace_id: str,
    framework: str,
    trace_id: str | None = None,
) -> tuple[docker.models.containers.Container, str]:
    """创建并启动 agent 容器。
    
    Args:
        session_id: Session ID
        workspace_id: Workspace ID
        framework: 目标框架
        trace_id: 可选的 langfuse trace ID
    
    Returns:
        tuple: (container, container_id)
    """
    client = docker.from_env()

    container_name = f"mgx-agent-{session_id}"

    # 同名容器存在则强制删除
    try:
        existing = await asyncio.to_thread(client.containers.get, container_name)
        await asyncio.to_thread(existing.remove, force=True)
        loguru.logger.info(f"Removed existing container: {container_name}")
    except docker.errors.NotFound:
        pass

    # 准备环境变量（prompt 从历史消息获取，不再通过 env 传递）
    environment = {
        "SESSION_ID": session_id,
        "WORKSPACE_ID": workspace_id,
        "FRAMEWORK": framework,
        # 传递数据库连接信息
        "MONGODB_URL": settings.mongodb_url,
        "MONGODB_DB": settings.mongodb_db,
        # 传递 Redis 信息（如果需要）
        "REDIS_URL": settings.redis_url,
        # MCP 调用 mgx-api 所需配置（Agent 通过 MCP 执行 Docker 操作）
        # API Key 与 session 绑定，使用 session_id 作为鉴权
        "MGX_API_URL": settings.mgx_api_url,
        "MGX_AGENT_API_KEY": session_id,
        "MGX_MCP_PATH": settings.mgx_mcp_path,
    }
    
    # LLM API 配置（ChatOpenAI 需要 OPENAI_API_KEY，支持 OpenAI/DashScope/OpenRouter 等）
    if settings.openai_api_key:
        environment["OPENAI_API_KEY"] = settings.openai_api_key
    if settings.openai_base_url:
        environment["OPENAI_BASE_URL"] = settings.openai_base_url
    
    # 如果有 trace_id，传递给容器
    if trace_id:
        environment["TRACE_ID"] = trace_id
    
    # 如果启用了 langfuse，传递配置
    if settings.langfuse_enabled:
        environment.update({
            "LANGFUSE_PUBLIC_KEY": settings.langfuse_public_key,
            "LANGFUSE_SECRET_KEY": settings.langfuse_secret_key,
            "LANGFUSE_HOST": settings.langfuse_host,
            "LANGFUSE_ENABLED": "true",
        })
    
    # Workspace volume mount - Docker requires HOST path for bind mounts (scheduler 可能运行在容器内)
    workspace_path = str((Path(settings.host_workspaces_root) / workspace_id).resolve())
    volumes = {
        workspace_path: {"bind": settings.agent_workspace_root_in_container, "mode": "rw"}
    }
    loguru.logger.info(f"Workspace path: {workspace_path}")
    loguru.logger.info(f"Volumes: {volumes}")

    # 创建并启动容器
    container = await asyncio.to_thread(
        client.containers.run,
        image=settings.agent_container_image,
        command=["python", "/app/src/agents/run_agent.py"],
        name=container_name,
        environment=environment,
        volumes=volumes,
        detach=True,
        remove=True,  # 容器退出后自动删除
        network_mode=settings.mgx_network,  # 加入 mgx-network 以访问 mgx-api
        mem_limit=settings.agent_container_memory_limit,
        cpu_quota=settings.agent_container_cpu_quota,
    )

    return container, container.id


def _stream_container_logs(container: docker.models.containers.Container, session_id: str) -> None:
    """在后台线程中流式输出容器日志到 loguru。"""
    short_id = session_id[:8] if session_id else "unknown"
    try:
        for log_line in container.logs(stream=True, follow=True):
            if log_line:
                line = log_line.decode("utf-8", errors="replace").rstrip()
                if line:
                    loguru.logger.info(f"[agent:{short_id}] {line}")
    except docker.errors.NotFound:
        pass  # 容器已删除
    except Exception as e:
        loguru.logger.debug(f"Container log stream ended: {e}")


async def monitor_agent_session(
    session_id: str,
    container: docker.models.containers.Container,
    timeout_seconds: int = None,
) -> dict:
    """监控 agent session 的完成状态。
    
    通过轮询 event 表查找 FINISH 事件。
    
    Args:
        session_id: Session ID
        container: Docker container
        timeout_seconds: 超时时间（秒），None 表示使用默认值
    
    Returns:
        dict: 结果包含状态和错误信息（如果有）
    """
    if timeout_seconds is None:
        timeout_seconds = settings.agent_task_timeout_seconds
    
    event_dao = EventDAO()
    start_time = time.time()
    poll_interval = 2  # 每 2 秒轮询一次
    
    while True:
        # 检查是否超时
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            # 超时，停止容器
            try:
                await asyncio.to_thread(container.stop, timeout=10)
            except Exception as e:
                print(f"Failed to stop container: {e}")
            SessionRunningService().clear_running(session_id)
            return {
                "session_id": session_id,
                "status": "timeout",
                "error": f"Agent task timeout after {timeout_seconds} seconds",
                "elapsed_seconds": elapsed,
            }
        
        # 检查容器状态
        try:
            await asyncio.to_thread(container.reload)
            container_status = container.status
            
            # 如果容器已经退出，检查退出码
            if container_status in ["exited", "dead"]:
                exit_code = container.attrs.get("State", {}).get("ExitCode")
                
                # 即使容器退出，也要检查事件表中的 FINISH 事件
                finish_event = await event_dao.get_finish_event(session_id)
                
                if finish_event:
                    # 找到 FINISH 事件
                    event_data = finish_event.get("data", {})
                    status = event_data.get("status", "unknown")
                    SessionRunningService().clear_running(session_id)
                    return {
                        "session_id": session_id,
                        "status": status,
                        "error": event_data.get("error"),
                        "elapsed_seconds": elapsed,
                        "container_exit_code": exit_code,
                    }
                else:
                    # 容器退出但没有 FINISH 事件
                    SessionRunningService().clear_running(session_id)
                    return {
                        "session_id": session_id,
                        "status": "failed",
                        "error": f"Container exited with code {exit_code} without FINISH event",
                        "elapsed_seconds": elapsed,
                        "container_exit_code": exit_code,
                    }
        
        except docker.errors.NotFound:
            # 容器不存在了（可能被自动删除）
            # 检查事件表
            finish_event = await event_dao.get_finish_event(session_id)
            
            if finish_event:
                event_data = finish_event.get("data", {})
                status = event_data.get("status", "unknown")
                SessionRunningService().clear_running(session_id)
                return {
                    "session_id": session_id,
                    "status": status,
                    "error": event_data.get("error"),
                    "elapsed_seconds": elapsed,
                }
            else:
                SessionRunningService().clear_running(session_id)
                return {
                    "session_id": session_id,
                    "status": "failed",
                    "error": "Container not found and no FINISH event",
                    "elapsed_seconds": elapsed,
                }
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            loguru.logger.error(f"Error checking container status: {e}")
            print(f"Error checking container status: {e}")
        
        # 查询 event 表中的 FINISH 事件
        try:
            finish_event = await event_dao.get_finish_event(session_id)
            
            if finish_event:
                # 找到 FINISH 事件，返回结果
                event_data = finish_event.get("data", {})
                status = event_data.get("status", "unknown")
                SessionRunningService().clear_running(session_id)
                return {
                    "session_id": session_id,
                    "status": status,
                    "error": event_data.get("error"),
                    "elapsed_seconds": elapsed,
                }
        
        except Exception as e:
            print(f"Error querying finish event: {e}")
        
        # 等待一段时间后再次检查
        await asyncio.sleep(poll_interval)


@celery_app.task(name="agent.run_team_agent_for_web_app_development", bind=True)
def run_team_agent_for_web_app_development(self, session_id: str, workspace_id: str, framework: str):
    """Generate code using agent team with streaming.
    
    该任务创建一个独立的 agent 容器来运行 agent，然后监控其完成状态。
    Agent 容器从历史消息获取 prompt（最后一条 user 消息），并将事件写入数据库。
    
    Args:
        session_id: Session/App ID
        workspace_id: Workspace ID
        framework: Framework template (nextjs, fastapi-vite)
        
    Returns:
        dict with status, error (if any), elapsed_seconds
    """
    self.update_state(state="PROCESSING", meta={"status": "Creating agent container..."})
    
    # Run async function in sync context
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # 创建 agent 容器
        container, container_id = loop.run_until_complete(
            create_agent_container(
                session_id=session_id,
                workspace_id=workspace_id,
                framework=framework,
            )
        )
        
        self.update_state(
            state="PROCESSING", 
            meta={
                "status": "Agent container created, monitoring...",
                "container_id": container_id,
            }
        )
        
        SessionRunningService().set_running(session_id)
        
        # 后台线程实时输出容器日志
        log_thread = threading.Thread(
            target=_stream_container_logs,
            args=(container, session_id),
            daemon=True,
        )
        log_thread.start()
        
        # 监控 agent session 完成状态
        result = loop.run_until_complete(
            monitor_agent_session(
                session_id=session_id,
                container=container,
            )
        )
        
        return result
    
    except Exception as e:
        # 如果创建容器失败或其他错误
        SessionRunningService().clear_running(session_id)
        return {
            "session_id": session_id,
            "status": "failed",
            "error": f"Failed to create or monitor agent container: {str(e)}",
        }
    
    finally:
        loop.close()
