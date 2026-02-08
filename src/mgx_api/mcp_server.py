"""MCP Server - 将 Docker 操作暴露为 MCP Tools。

供 Agent 通过 MCP 协议调用 mgx-api 的 Docker 操作。
"""

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from mgx_api.services.docker_service import DockerService


def _get_docker_service() -> DockerService:
    return DockerService()


# 允许 localhost 与 Docker 内网 mgx-api 的 Host，供 Agent 容器连接
_transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=True,
    allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*", "mgx-api:*", "mgx-api:8000"],
    allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*", "http://mgx-api:*"],
)

# streamable_http_path="/" 用于挂载场景：main.py 将 MCP app mount 到 /mcp，
# 子应用收到的路径是 /，故需在根路径注册 MCP 端点
mcp = FastMCP(
    name="MGX Docker Tools",
    instructions="Tools for executing commands in dev containers, managing dev server, and fetching container logs/status.",
    json_response=True,
    stateless_http=True,
    streamable_http_path="/",
    transport_security=_transport_security,
)


@mcp.tool()
async def exec_command(
    workspace_id: str,
    command: str,
    working_dir: str = "/workspace",
) -> str:
    """在 dev container 中执行 shell 命令。

    Args:
        workspace_id: Workspace ID
        command: 要执行的 shell 命令
        working_dir: 工作目录，默认为 /workspace

    Returns:
        命令输出（stdout + stderr）
    """
    svc = _get_docker_service()
    return await svc.exec_command(workspace_id, command, working_dir)


@mcp.tool()
async def get_container_logs(workspace_id: str, tail: int = 100) -> str:
    """获取 dev container 的日志。

    Args:
        workspace_id: Workspace ID
        tail: 返回最后 N 行，默认 100

    Returns:
        容器日志
    """
    svc = _get_docker_service()
    return await svc.get_container_logs(workspace_id, target="dev", tail=tail)


@mcp.tool()
async def get_container_status(workspace_id: str) -> str:
    """获取 dev container 的状态信息。

    Args:
        workspace_id: Workspace ID

    Returns:
        容器状态（名称、状态、端口映射等）
    """
    svc = _get_docker_service()
    return await svc.get_container_status_str(workspace_id)


@mcp.tool()
async def start_dev_server(
    workspace_id: str,
    command: str = "npm run dev",
    working_dir: str = "/workspace",
    port: int = 3000,
    framework: str = "nextjs",
) -> str:
    """在 dev container 中启动开发服务器（后台运行）。
    若 dev container 不存在则自动创建并配置 Apisix 路由。

    Args:
        workspace_id: Workspace ID
        command: 启动命令，如 'npm run dev'
        working_dir: 工作目录
        port: 开发服务器端口
        framework: 框架 (nextjs, fastapi-vite)，创建容器时使用

    Returns:
        启动结果
    """
    svc = _get_docker_service()
    return await svc.start_dev_server(
        workspace_id, command, working_dir, port, framework
    )


@mcp.tool()
async def get_dev_server_status(workspace_id: str) -> str:
    """获取开发服务器的运行状态。

    Args:
        workspace_id: Workspace ID

    Returns:
        开发服务器状态信息
    """
    svc = _get_docker_service()
    return await svc.get_dev_server_status(workspace_id)


@mcp.tool()
async def get_dev_server_logs(workspace_id: str, tail: int = 50) -> str:
    """获取开发服务器的日志输出。

    Args:
        workspace_id: Workspace ID
        tail: 返回最后 N 行，默认 50

    Returns:
        开发服务器日志
    """
    svc = _get_docker_service()
    return await svc.get_dev_server_logs(workspace_id, tail)


@mcp.tool()
async def stop_dev_server(workspace_id: str) -> str:
    """停止开发服务器。

    Args:
        workspace_id: Workspace ID

    Returns:
        停止结果
    """
    svc = _get_docker_service()
    return await svc.stop_dev_server(workspace_id)


def get_mcp_app():
    """获取 MCP Streamable HTTP ASGI app。"""
    return mcp.streamable_http_app()
