#!/usr/bin/env bash
# MGX 镜像健康检查测试脚本
# 使用 docker run 和 docker exec 验证 mgx:latest 镜像的三种 entrypoint

set -e

IMAGE="${1:-mgx:latest}"
API_TEST_PORT="${2:-18000}"
FAILED=0

echo "=========================================="
echo "MGX Image Health Check: $IMAGE"
echo "=========================================="

# 1. 测试 Agent entrypoint（模块导入）
echo ""
echo "[1/4] Testing Agent entrypoint (docker run)..."
if docker run --rm "$IMAGE" python -c "
import sys
sys.path.insert(0, '/app/src')
import agents.run_agent
print('agent import ok')
" 2>/dev/null; then
    echo "  ✅ Agent import OK"
else
    echo "  ❌ Agent import FAILED"
    FAILED=$((FAILED + 1))
fi

# 2. 测试 MGX API（docker run 启动 + curl 健康检查 + MCP 端点）
# 使用无效 MongoDB URL 使 lifespan 快速失败，/health 不依赖 DB
# MGX_AGENT_API_KEY 为 MCP 端点鉴权所需
echo ""
echo "[2/5] Testing MGX API (docker run + health endpoint)..."
# 清理可能残留的测试容器（避免 "container name already in use"）
docker rm -f mgx-api-test 2>/dev/null || true
MCP_TEST_KEY="test-mcp-key-$(date +%s)"
CONTAINER_ID=$(docker run -d --name mgx-api-test -p "$API_TEST_PORT:8000" \
    -e MONGODB_URL="mongodb://invalid:27017/?serverSelectionTimeoutMS=2000" \
    -e MGX_AGENT_API_KEY="$MCP_TEST_KEY" \
    -e APISIX_ADMIN_URL="http://127.0.0.1:19999" \
    "$IMAGE" uvicorn mgx_api.main:app --host 0.0.0.0 --port 8000 2>/dev/null || true)

if [ -n "$CONTAINER_ID" ]; then
    echo "  Waiting for API to start..."
    sleep 6
    
    # 外部 curl 测试
    if curl -s "http://localhost:$API_TEST_PORT/health" | grep -q '"status":"ok"'; then
        echo "  ✅ MGX API health (curl) OK"
    else
        echo "  ❌ MGX API health (curl) FAILED"
        FAILED=$((FAILED + 1))
    fi
    
    # docker exec 内部测试
    if docker exec mgx-api-test python -c "
import urllib.request
r = urllib.request.urlopen('http://localhost:8000/health')
body = r.read().decode()
assert '\"status\":\"ok\"' in body or '\"status\": \"ok\"' in body
print('exec health ok')
" 2>/dev/null; then
        echo "  ✅ MGX API health (docker exec) OK"
    else
        echo "  ❌ MGX API health (docker exec) FAILED"
        FAILED=$((FAILED + 1))
    fi
    
    # MCP 端点测试（需 X-API-Key 鉴权，Accept: application/json 为 MCP 协议要求）
    echo ""
    echo "[3/5] Testing MCP server endpoint..."
    # 无 API Key 应返回 401（使用 /mcp/ 避免 307 重定向）
    MCP_STATUS_NO_KEY=$(curl -s -o /dev/null -w "%{http_code}" -X POST "http://localhost:$API_TEST_PORT/mcp/" \
        -H "Content-Type: application/json" -H "Accept: application/json" \
        -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}')
    if [ "$MCP_STATUS_NO_KEY" = "401" ]; then
        echo "  ✅ MCP endpoint rejects request without API key (401)"
    else
        echo "  ❌ MCP endpoint without key: expected 401, got $MCP_STATUS_NO_KEY"
        FAILED=$((FAILED + 1))
    fi
    # 正确 API Key 且完整 initialize 参数应返回 200 及 JSON-RPC result（含 serverInfo）
    MCP_RESP=$(curl -s -X POST "http://localhost:$API_TEST_PORT/mcp/" \
        -H "Content-Type: application/json" -H "Accept: application/json" -H "X-API-Key: $MCP_TEST_KEY" \
        -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1.0"}}}')
    if echo "$MCP_RESP" | grep -q '"result"' && echo "$MCP_RESP" | grep -q '"serverInfo"'; then
        echo "  ✅ MCP endpoint responds with initialize result (200)"
    else
        echo "  ❌ MCP endpoint with valid key: unexpected response"
        FAILED=$((FAILED + 1))
    fi
    
    docker stop mgx-api-test 2>/dev/null || true
    docker rm mgx-api-test 2>/dev/null || true
else
    echo "  ❌ Failed to start API container"
    FAILED=$((FAILED + 1))
fi

# 4. 测试 Celery（docker run 验证 celery 可启动）
echo ""
echo "[4/5] Testing Celery entrypoint (docker run)..."
if docker run --rm "$IMAGE" celery -A scheduler.tasks --help &>/dev/null; then
    echo "  ✅ Celery OK"
else
    echo "  ❌ Celery FAILED"
    FAILED=$((FAILED + 1))
fi

# 5. 测试 mgx_api 模块导入
echo ""
echo "[5/5] Testing mgx_api module import (docker run)..."
if docker run --rm "$IMAGE" python -c "
import sys
sys.path.insert(0, '/app/src')
import mgx_api.main
print('mgx_api import ok')
" 2>/dev/null; then
    echo "  ✅ mgx_api import OK"
else
    echo "  ❌ mgx_api import FAILED"
    FAILED=$((FAILED + 1))
fi

# 汇总
echo ""
echo "=========================================="
if [ $FAILED -eq 0 ]; then
    echo "✅ All tests passed"
    exit 0
else
    echo "❌ $FAILED test(s) failed"
    exit 1
fi
