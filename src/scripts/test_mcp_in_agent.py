"""在 Agent 容器内测试 MCP 客户端连接。

供 celery-worker (agent container) 通过 MGX_API_URL=http://mgx-api:8000 连接 mgx-api 的 MCP 端点。
使用 mcp_docker_client 模块，与 Agent 实际调用方式一致。

运行方式（在 agent 容器内）:
  python -m scripts.test_mcp_in_agent
  # 或由 scripts/test_mcp_in_agent.sh 通过 docker exec 调用
"""

import asyncio
import os
import sys
from pathlib import Path

# 确保 src 在路径中（容器内 PYTHONPATH=/app/src 通常已设置）
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.web_app_team.tools import mcp_docker_client


async def _run_tests() -> int:
    """测试 MCP 连接，使用 mcp_docker_client 与 Agent 相同方式（async）。"""
    api_url = os.environ.get("MGX_API_URL", "http://mgx-api:8000")
    api_key = os.environ.get("MGX_AGENT_API_KEY", "")
    mcp_path = os.environ.get("MGX_MCP_PATH", "/mcp")

    print("=" * 50)
    print("MCP Client Test (Agent Container)")
    print("=" * 50)
    print(f"MGX_API_URL: {api_url}")
    print(f"MGX_MCP_PATH: {mcp_path}")
    print(f"MGX_AGENT_API_KEY: {'*' * 8}... (set)" if api_key else "MGX_AGENT_API_KEY: (not set) ❌")
    print()

    if not api_key:
        print("❌ MGX_AGENT_API_KEY 未配置")
        return 1

    # 1. get_container_status（不存在的 workspace 会返回错误，但连接应成功）
    print("[1/2] Calling get_container_status (non-existent workspace)...")
    try:
        result = await mcp_docker_client.get_container_status("test-workspace-mcp-check")
        print(f"  ✅ MCP 连接成功")
        print(f"  Response: {result[:200]}..." if len(result) > 200 else f"  Response: {result}")
    except Exception as e:
        print(f"  ❌ MCP 调用失败: {e}")
        return 1

    # 2. get_dev_server_status
    print("\n[2/2] Calling get_dev_server_status...")
    try:
        result = mcp_docker_client.get_dev_server_status("test-workspace-mcp-check")
        print(f"  ✅ call_tool 成功")
        print(f"  Response: {result[:200]}..." if len(result) > 200 else f"  Response: {result}")
    except Exception as e:
        print(f"  ❌ 调用失败: {e}")
        return 1

    print("\n" + "=" * 50)
    print("✅ Agent 容器内 MCP 连接测试通过")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_run_tests()))
