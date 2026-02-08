#!/usr/bin/env bash
# 在 Agent 容器（mgx-celery-worker）内测试 MCP 客户端连接。
#
# 前提：docker-compose 已启动 mgx-api 和 celery-worker
# 运行：./scripts/test_mcp_in_agent.sh
# 或：  bash scripts/test_mcp_in_agent.sh

set -e

CONTAINER="${1:-mgx-celery-worker}"

echo "=========================================="
echo "MCP Client Test (inside Agent Container)"
echo "=========================================="
echo "Container: $CONTAINER"
echo ""

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "❌ Container '$CONTAINER' is not running."
    echo "   Start it with: cd infra && docker-compose up -d mgx-api celery-worker"
    exit 1
fi

echo "Running MCP test inside $CONTAINER..."
echo ""

docker exec "$CONTAINER" python -m scripts.test_mcp_in_agent
