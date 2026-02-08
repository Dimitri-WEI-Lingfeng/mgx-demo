# MCP API Key 与 Session 绑定

## 变更概述

MCP 端点的 API Key 鉴权改为与 session 绑定，使用 session_id 作为 API Key。

## 变更内容

### 1. api_key_mcp 中间件 (`src/mgx_api/middleware/api_key_mcp.py`)

- **主逻辑**：X-API-Key 作为 session_id，通过 SessionDAO 查询数据库校验 session 是否存在
- **兼容逻辑**：若配置了 `MGX_AGENT_API_KEY`，与其匹配时也放行（用于测试/本地开发）
- 移除对全局 `MGX_AGENT_API_KEY` 的强依赖（原 500 错误改为可选）

### 2. Scheduler 创建 Agent 容器 (`src/scheduler/tasks.py`)

- `MGX_AGENT_API_KEY` 从 `settings.mgx_agent_api_key` 改为 `session_id`
- Agent 容器启动时注入的 API Key 即为当前 session 的 ID

### 3. 配置与文档

- **settings.py**：`mgx_agent_api_key` 改为可选，注释说明生产环境主用 session_id
- **.env.example**：补充 MCP 鉴权说明
- **docker-compose.yml**：mgx-api 保留 `MGX_AGENT_API_KEY` 用于兼容/测试（默认 dev-agent-api-key）

### 4. mcp_docker_client & run_agent

- 无需改动：仍从环境变量 `MGX_AGENT_API_KEY` 读取，scheduler 注入的即为 session_id

## 鉴权流程

```
Agent 容器启动
  → Scheduler 注入 MGX_AGENT_API_KEY=session_id
  → mcp_docker_client 读取 env，请求 MCP 时携带 X-API-Key: session_id
  → api_key_mcp 中间件：
     1. 若配置了 MGX_AGENT_API_KEY 且匹配 → 放行
     2. 否则查 SessionDAO.find_by_id(api_key) → 存在则放行
```

## 测试兼容

- `test_mcp_client_integration.py`：使用 `MGX_AGENT_API_KEY=dev-agent-api-key`（与 docker-compose 默认一致）
- `scripts/test_mgx_image.sh`：启动 mgx-api 时传入 `MGX_AGENT_API_KEY=$MCP_TEST_KEY`，请求时使用相同 key
