# Agent 容器化运行指南

## 概述

MGX 平台使用容器化的方式运行 agent，每个 session 在独立的 Docker 容器中执行。这种设计提供了更好的隔离性、可扩展性和资源管理。

## 架构设计

### 核心组件

1. **Celery Task** (`src/scheduler/tasks.py`)
   - 创建和启动 agent 容器
   - 轮询 event 表监控 session 状态
   - 处理超时和错误情况

2. **Agent Runner** (`src/agents/run_agent.py`)
   - 在容器中执行的独立脚本
   - 从环境变量读取配置
   - 运行 agent 并写入事件到数据库

3. **Agent Container Image** (`infra/Dockerfile.mgx`)
   - 统一镜像，支持 mgx-api、celery-worker、agent 三种 entrypoint
   - 使用 uv sync 安装依赖（清华源）
   - 基于 Python 3.12
   - 默认命令为运行 `run_agent.py`

### 工作流程

```
用户发起会话
    ↓
FastAPI 提交 Celery 任务
    ↓
Celery 创建 Agent 容器
    ↓
Agent 容器运行并写入事件到 MongoDB
    ↓
Celery 轮询查询 FINISH 事件
    ↓
容器完成后自动删除
    ↓
Celery 返回任务结果
    ↓
FastAPI SSE 推送事件给客户端
```

## 配置说明

### 环境变量

在 `.env` 文件中配置以下参数：

```bash
# LLM API 配置（必填，Agent 容器内 ChatOpenAI 调用 LLM 必需）
OPENAI_API_KEY=sk-xxx                         # OpenAI/DashScope/OpenRouter 等兼容 API 的 key
# OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1  # 使用 qwen3-coder-flash 时需配置 DashScope 兼容端点

# Agent Container Configuration
AGENT_CONTAINER_IMAGE=mgx:latest               # MGX 统一镜像（agent/mgx-api/celery-worker）
AGENT_CONTAINER_MEMORY_LIMIT=2g               # 内存限制
AGENT_CONTAINER_CPU_QUOTA=100000              # CPU quota (100000 = 1 CPU)
AGENT_TASK_TIMEOUT_SECONDS=1800               # 任务超时时间（秒）
```

### 容器资源限制

- **内存限制**: 默认 2GB，可根据实际需求调整
- **CPU 限制**: 默认 1 CPU，可调整 CPU quota
- **超时时间**: 默认 30 分钟，超时后容器会被强制停止

### Workspace 路径：宿主机 vs 容器内

当 mgx-api、celery-worker 运行在 Docker 容器内，并通过 Docker API 创建子容器（agent 容器、dev 容器）时，**bind mount 必须使用宿主机路径**，而非容器内路径。

| 场景 | 使用路径 | 说明 |
|------|----------|------|
| Docker API（containers.run、images.build） | `HOST_WORKSPACES_ROOT` | Docker daemon 在宿主机执行，需宿主机绝对路径 |
| 容器内文件操作（aiofiles.open 等） | `WORKSPACES_ROOT` | 进程在容器内，使用容器内挂载路径 |

**配置**：`docker-compose.yml` 中需为 mgx-api、celery-worker 设置：

```yaml
- WORKSPACES_ROOT=/workspaces
- HOST_WORKSPACES_ROOT=${PWD}/workspaces   # 宿主机路径，Docker API 使用
```

**涉及代码**：
- `src/scheduler/tasks.py`：创建 agent 容器时，volume 使用 `host_workspaces_root`
- `src/mgx_api/services/docker_service.py`：创建 dev 容器、构建 prod 镜像时，Docker API 使用 `host_workspaces_root`；容器内写文件使用 `workspaces_root`

## 使用步骤

### 1. 构建 MGX 镜像

```bash
make build-agent
# 或 make build-mgx
```

或者手动构建：

```bash
docker build -f infra/Dockerfile.mgx -t mgx:latest .
```

构建后可运行健康检查：

```bash
make test-image
```

### 2. 启动后端服务

```bash
make up
```

确保以下服务已启动：
- MongoDB
- Redis
- MGX API
- OAuth2 Provider
- Celery Worker

### 3. 测试 Agent 运行

通过 FastAPI 接口发起会话：

```bash
curl -X POST http://localhost:8000/api/agent/generate \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session",
    "workspace_id": "test-workspace",
    "framework": "nextjs",
    "prompt": "Create a simple homepage"
  }'
```

### 4. 监控容器状态

查看运行中的 agent 容器：

```bash
docker ps | grep mgx-agent
```

查看容器日志：

```bash
docker logs mgx-agent-{session_id}
```

## 容器生命周期

### 创建

- 容器名称: `mgx-agent-{session_id}`
- 网络模式: `bridge`
- 自动删除: 是（容器退出后自动删除）
- 挂载卷: Workspace 目录挂载到 `/workspace`

### 环境变量传递

Celery 会自动传递以下环境变量给容器：

- `SESSION_ID`: Session ID
- `WORKSPACE_ID`: Workspace ID
- `FRAMEWORK`: 目标框架
- `PROMPT`: 用户提示词
- `MONGODB_URL`: MongoDB 连接 URL
- `MONGODB_DB`: MongoDB 数据库名
- `REDIS_URL`: Redis 连接 URL
- `LANGFUSE_*`: Langfuse 配置（如果启用）

### 监控

Celery task 通过以下方式监控容器：

1. 轮询 event 表查找 `FINISH` 事件（每 2 秒）
2. 检查容器状态（运行中/退出）
3. 检查是否超时

### 完成

容器完成后：
1. 写入 `FINISH` 事件到 MongoDB
2. 容器退出
3. Docker 自动删除容器
4. Celery task 返回结果

## 事件流

Agent 容器在执行过程中会写入以下事件到 MongoDB：

1. `AGENT_START` - Agent 开始执行
2. `MESSAGE_DELTA` - 流式消息增量（可选）
3. `TOOL_START` - 工具调用开始
4. `TOOL_END` - 工具调用结束
5. `MESSAGE_COMPLETE` - 消息完成
6. `AGENT_END` - Agent 执行结束
7. `FINISH` - Session 完成（包含状态）

FastAPI SSE 端点会读取这些事件并实时推送给客户端。

## 错误处理

### 容器创建失败

如果容器创建失败，Celery task 会返回错误结果：

```json
{
  "session_id": "...",
  "status": "failed",
  "error": "Failed to create or monitor agent container: ..."
}
```

### 容器超时

如果容器运行时间超过配置的超时时间：

1. Celery 会尝试停止容器
2. 返回超时错误结果
3. 容器被强制停止和删除

```json
{
  "session_id": "...",
  "status": "timeout",
  "error": "Agent task timeout after 1800 seconds",
  "elapsed_seconds": 1800.5
}
```

### 容器异常退出

如果容器异常退出（非零退出码）：

1. Celery 检查 event 表中是否有 `FINISH` 事件
2. 如果有，使用事件中的状态
3. 如果没有，返回容器退出错误

## 调试

### 查看容器日志

```bash
# 查看运行中的容器
docker ps | grep mgx-agent

# 查看容器日志
docker logs mgx-agent-{session_id}

# 实时跟踪日志
docker logs -f mgx-agent-{session_id}
```

### 查看数据库事件

```bash
# 进入 MongoDB
make mongo

# 查询 session 的所有事件
db.events.find({session_id: "your-session-id"}).sort({timestamp: 1})

# 查询 FINISH 事件
db.events.find({session_id: "your-session-id", event_type: "finish"})
```

### 手动运行容器（测试）

```bash
docker run --rm \
  -e SESSION_ID=test-session \
  -e WORKSPACE_ID=test-workspace \
  -e FRAMEWORK=nextjs \
  -e PROMPT="Create a homepage" \
  -e MONGODB_URL=mongodb://localhost:27017 \
  -e MONGODB_DB=mgx \
  -v $(pwd)/workspaces/test-workspace:/workspace \
  mgx:latest
```

## 最佳实践

1. **资源限制**
   - 根据 agent 的实际需求设置合理的内存和 CPU 限制
   - 避免过度分配导致资源浪费

2. **超时设置**
   - 根据任务复杂度设置合理的超时时间
   - 过短会导致任务被意外中断
   - 过长会占用资源

3. **镜像更新**
   - 代码更新后需要重新构建 agent 镜像
   - 使用版本标签管理不同版本的镜像

4. **日志管理**
   - 容器日志会在容器删除后丢失
   - 重要日志应该写入数据库或外部日志系统

5. **网络配置**
   - 确保容器能够访问 MongoDB 和其他必要服务
   - 使用 Docker 网络或 host 网络模式

## 故障排查

### 问题：容器无法启动

**可能原因**:
- 镜像不存在
- 环境变量缺失
- 挂载卷路径不存在

**解决方案**:
1. 检查镜像是否存在: `docker images | grep mgx`
2. 重新构建镜像: `make build-agent`
3. 检查环境变量配置
4. 检查 workspace 目录是否存在

### 问题：Mounts denied - path is not shared from the host

**错误信息**:
```
Mounts denied: The path /workspaces/xxx is not shared from the host and is not known to Docker.
```

**原因**：celery-worker 或 mgx-api 在容器内运行时，创建子容器时误用了容器内路径 `WORKSPACES_ROOT`（`/workspaces`）。Docker bind mount 需要**宿主机路径**，宿主机上不存在 `/workspaces/xxx`。

**解决方案**:
1. 确保 `docker-compose.yml` 中 celery-worker、mgx-api 配置了 `HOST_WORKSPACES_ROOT=${PWD}/workspaces`
2. 从项目根目录执行 `docker compose`，以便 `${PWD}` 正确解析为宿主机项目路径

### 问题：容器运行但没有事件

**可能原因**:
- MongoDB 连接失败
- 数据库配置错误

**解决方案**:
1. 检查 MongoDB 是否运行: `docker ps | grep mongodb`
2. 检查容器日志中的连接错误
3. 验证 MongoDB URL 配置

### 问题：任务一直超时

**可能原因**:
- Agent 执行时间过长
- 超时设置过短
- Agent 陷入死循环

**解决方案**:
1. 增加 `AGENT_TASK_TIMEOUT_SECONDS`
2. 优化 agent 逻辑
3. 检查容器日志确认是否有错误

## 性能优化

1. **镜像优化**
   - 使用多阶段构建减小镜像体积
   - 缓存依赖层加速构建

2. **资源调优**
   - 根据实际负载调整资源限制
   - 监控容器资源使用情况

3. **并发控制**
   - 限制同时运行的 agent 容器数量
   - 使用 Celery 的 worker 并发设置

4. **事件优化**
   - 批量写入事件减少数据库压力
   - 使用索引加速事件查询

## 参考资料

- [Docker Python SDK](https://docker-py.readthedocs.io/)
- [Celery Documentation](https://docs.celeryproject.org/)
- [MongoDB Python Driver](https://pymongo.readthedocs.io/)
