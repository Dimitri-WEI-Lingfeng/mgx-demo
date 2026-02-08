"""MCP 客户端 - 通过 MCP 协议调用 mgx-api 的 Docker 操作。

Agent 使用此客户端替代直接调用 Docker SDK。
"""

import os
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import MCP_DEFAULT_SSE_READ_TIMEOUT, MCP_DEFAULT_TIMEOUT
from mcp.types import TextContent


def _get_mcp_url() -> str:
    """获取 MCP 端点 URL。确保带尾随斜杠，避免 FastAPI 307 重定向。"""
    base = os.environ.get("MGX_API_URL", "http://mgx-api:8000")
    path = os.environ.get("MGX_MCP_PATH", "/mcp")
    path = path if path.startswith("/") else f"/{path}"
    path = path if path.endswith("/") else f"{path}/"
    return f"{base.rstrip('/')}{path}"


def _get_api_key() -> str:
    """获取 API Key。"""
    return os.environ.get("MGX_AGENT_API_KEY", "")


def _extract_text_from_result(result: Any) -> str:
    """从 CallToolResult 提取文本。"""
    if result.isError:
        return f"错误：{result.content}"
    if result.content:
        for block in result.content:
            if isinstance(block, TextContent):
                return block.text
    if result.structuredContent is not None:
        if isinstance(result.structuredContent, str):
            return result.structuredContent
        if isinstance(result.structuredContent, dict) and "result" in result.structuredContent:
            return str(result.structuredContent["result"])
        return str(result.structuredContent)
    return ""


def _create_mcp_http_client(headers: dict[str, str] | None = None) -> httpx.AsyncClient:
    """创建 MCP 专用的 httpx 客户端。

    显式禁用 HTTP/2 (http2=False)，避免 421 Misdirected Request 错误。
    该错误多发于 HTTP/2 连接复用时，uvicorn 默认使用 HTTP/1.1。
    """
    return httpx.AsyncClient(
        headers=headers or {},
        follow_redirects=True,
        timeout=httpx.Timeout(MCP_DEFAULT_TIMEOUT, read=MCP_DEFAULT_SSE_READ_TIMEOUT),
        http2=False,  # 禁用 HTTP/2，避免 421 Misdirected Request
    )


async def _call_tool(name: str, arguments: dict[str, Any]) -> str:
    """异步调用 MCP tool。"""
    url = _get_mcp_url()
    api_key = _get_api_key()
    if not api_key:
        return "错误：未配置 MGX_AGENT_API_KEY"
    headers = {"X-API-Key": api_key}
    client = _create_mcp_http_client(headers=headers)
    async with client:
        async with streamable_http_client(url, http_client=client, terminate_on_close=True) as (
            read_stream,
            write_stream,
            _,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments)
                return _extract_text_from_result(result)


async def exec_command(workspace_id: str, command: str, working_dir: str = "/workspace") -> str:
    """在 dev container 中执行 shell 命令。"""
    return await _call_tool("exec_command", {
        "workspace_id": workspace_id,
        "command": command,
        "working_dir": working_dir,
    })


async def get_container_logs(workspace_id: str, tail: int = 100) -> str:
    """获取 dev container 的日志。"""
    return await _call_tool("get_container_logs", {
        "workspace_id": workspace_id,
        "tail": tail,
    })


async def get_container_status(workspace_id: str) -> str:
    """获取 dev container 的状态。"""
    return await _call_tool("get_container_status", {"workspace_id": workspace_id})


async def start_dev_server(
    workspace_id: str,
    command: str = "npm run dev",
    working_dir: str = "/workspace",
    port: int = 3000,
) -> str:
    """启动开发服务器。"""
    return await _call_tool("start_dev_server", {
        "workspace_id": workspace_id,
        "command": command,
        "working_dir": working_dir,
        "port": port,
    })


async def get_dev_server_status(workspace_id: str) -> str:
    """获取开发服务器状态。"""
    return await _call_tool("get_dev_server_status", {"workspace_id": workspace_id})


async def get_dev_server_logs(workspace_id: str, tail: int = 50) -> str:
    """获取开发服务器日志。"""
    return await _call_tool("get_dev_server_logs", {
        "workspace_id": workspace_id,
        "tail": tail,
    })


async def stop_dev_server(workspace_id: str) -> str:
    """停止开发服务器。"""
    return await _call_tool("stop_dev_server", {"workspace_id": workspace_id})
