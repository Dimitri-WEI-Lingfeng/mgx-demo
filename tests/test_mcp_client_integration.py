"""MCP 客户端集成测试 - 测试连接 http://localhost:8000/mcp/ 的 MCP 服务。

运行前提：
- mgx-api 已在运行（如 docker-compose up mgx-api）
- 服务暴露在 http://localhost:8000
- 鉴权：X-API-Key 为 session_id 或 MGX_AGENT_API_KEY（docker-compose 默认 dev-agent-api-key）

运行方式：
  uv run pytest tests/test_mcp_client_integration.py -v
  uv run python tests/test_mcp_client_integration.py  # 作为独立脚本
"""

import asyncio
import os
import sys
from pathlib import Path

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import MCP_DEFAULT_SSE_READ_TIMEOUT, MCP_DEFAULT_TIMEOUT

# 确保 src 在路径中
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# 测试配置
MCP_BASE_URL = os.environ.get("MGX_MCP_TEST_URL", "http://localhost:8000")
MCP_PATH = os.environ.get("MGX_MCP_PATH", "/mcp")
MCP_URL = f"{MCP_BASE_URL.rstrip('/')}{MCP_PATH if MCP_PATH.startswith('/') else '/' + MCP_PATH}{'' if MCP_PATH.endswith('/') else '/'}"
API_KEY = os.environ.get("MGX_AGENT_API_KEY", "dev-agent-api-key")


def _create_http_client(headers: dict | None = None) -> httpx.AsyncClient:
    """创建 MCP 专用的 httpx 客户端。"""
    return httpx.AsyncClient(
        headers=headers or {},
        follow_redirects=True,
        timeout=httpx.Timeout(MCP_DEFAULT_TIMEOUT, read=MCP_DEFAULT_SSE_READ_TIMEOUT),
        http2=False,
    )


async def _test_mcp_connection(api_key: str | None = None) -> dict:
    """连接 MCP 服务，执行 initialize 和 list_tools，返回结果摘要。"""
    url = MCP_URL
    headers = {"X-API-Key": api_key} if api_key else {}
    client = _create_http_client(headers=headers)

    async with client:
        async with streamable_http_client(
            url, http_client=client, terminate_on_close=True
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                init_result = await session.initialize()
                tools_result = await session.list_tools()

    return {
        "server_info": init_result.serverInfo.model_dump() if init_result.serverInfo else None,
        "tool_count": len(tools_result.tools) if tools_result.tools else 0,
        "tool_names": [t.name for t in (tools_result.tools or [])],
    }


async def _test_mcp_connection_no_key() -> int:
    """无 API Key 请求应返回 401。使用原始 HTTP 请求检测。"""
    url = MCP_URL
    async with httpx.AsyncClient(follow_redirects=True, http2=False) as client:
        resp = await client.post(
            url,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0.1.0"},
                },
            },
        )
    return resp.status_code


async def _check_api_health() -> bool:
    """检查 mgx-api 是否可达。"""
    health_url = f"{MCP_BASE_URL.rstrip('/')}/health"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(health_url)
            return resp.status_code == 200 and "ok" in resp.text.lower()
    except Exception:
        return False


@pytest.mark.asyncio
class TestMCPClientIntegration:
    """MCP 客户端集成测试。"""

    async def test_mcp_connection_with_valid_api_key(self):
        """有效 API Key 下应能 initialize 并 list_tools。"""
        if not await _check_api_health():
            pytest.skip("mgx-api 未运行")
        result = await _test_mcp_connection(api_key=API_KEY)
        assert result["server_info"] is not None
        assert result["tool_count"] > 0
        expected_tools = {
            "exec_command",
            "get_container_logs",
            "get_container_status",
            "start_dev_server",
            "get_dev_server_status",
            "get_dev_server_logs",
            "stop_dev_server",
        }
        assert expected_tools.issubset(set(result["tool_names"]))

    async def test_mcp_connection_rejects_without_api_key(self):
        """无 API Key 应返回 401。"""
        if not await _check_api_health():
            pytest.skip("mgx-api 未运行")
        status = await _test_mcp_connection_no_key()
        assert status == 401, f"Expected 401, got {status}"

    async def test_mcp_call_tool_get_container_status(self):
        """调用 get_container_status tool（不存在的 workspace 会返回错误，但连接应成功）。"""
        if not await _check_api_health():
            pytest.skip("mgx-api 未运行")
        url = MCP_URL
        headers = {"X-API-Key": API_KEY}
        client = _create_http_client(headers=headers)

        async with client:
            async with streamable_http_client(
                url, http_client=client, terminate_on_close=True
            ) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    result = await session.call_tool(
                        "get_container_status",
                        {"workspace_id": "non-existent-workspace-for-test"},
                    )
        # 连接成功即通过；tool 可能返回错误（workspace 不存在）
        assert result is not None


def main():
    """独立运行入口。"""
    print("=" * 50)
    print("MCP Client Integration Test")
    print("=" * 50)
    print(f"URL: {MCP_URL}")
    print(f"API Key: {'*' * 8}... (configured)" if API_KEY else "API Key: (not set)")
    print()

    async def run():
        # 1. 健康检查
        print("[1/4] Checking mgx-api health...")
        if not await _check_api_health():
            print("  ❌ mgx-api 未运行。请先启动: cd infra && docker-compose up -d mgx-api")
            return 1
        print("  ✅ mgx-api is reachable")

        # 2. 无 Key 应 401
        print("\n[2/4] Testing 401 without API key...")
        status = await _test_mcp_connection_no_key()
        if status != 401:
            print(f"  ❌ Expected 401, got {status}")
            return 1
        print("  ✅ Correctly rejects unauthenticated requests (401)")

        # 3. 有效 Key 连接
        print("\n[3/4] Testing MCP connection with valid API key...")
        try:
            result = await _test_mcp_connection(api_key=API_KEY)
            print(f"  ✅ Connected. Server: {result['server_info'].get('name', 'N/A')}")
            print(f"  ✅ Tools: {result['tool_count']} tools: {result['tool_names']}")
        except Exception as e:
            print(f"  ❌ Connection failed: {e}")
            return 1

        # 4. 调用 tool
        print("\n[4/4] Testing call_tool (get_container_status)...")
        try:
            url = MCP_URL
            headers = {"X-API-Key": API_KEY}
            client = _create_http_client(headers=headers)
            async with client:
                async with streamable_http_client(
                    url, http_client=client, terminate_on_close=True
                ) as (read_stream, write_stream, _):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        result = await session.call_tool(
                            "get_container_status",
                            {"workspace_id": "test-workspace"},
                        )
            print(f"  ✅ call_tool succeeded (result: {result.isError})")
        except Exception as e:
            print(f"  ❌ call_tool failed: {e}")
            return 1

        print("\n" + "=" * 50)
        print("✅ All MCP client integration tests passed")
        return 0

    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
