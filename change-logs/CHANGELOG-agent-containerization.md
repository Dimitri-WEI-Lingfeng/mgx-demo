# Agent 容器化架构改造变更日志

## 变更概述

将 agent 运行模式从 Celery worker 进程内执行改造为独立容器执行，实现更好的隔离性和可扩展性。

## 主要变更

### 1. 新增文件

#### `src/agents/run_agent.py`
- 独立的 agent 运行脚本
- 从环境变量读取配置
- 在容器中执行 agent 逻辑
- 将事件写入 MongoDB

#### `infra/Dockerfile.agent-runner`
- Agent 容器镜像的 Dockerfile
- 基于 Python 3.12-slim
- 包含所有必要的依赖和代码
- 默认执行 `run_agent.py`

#### `docs/agent-container-guide.md`
- Agent 容器化使用指南
- 详细的配置说明和故障排查
- 最佳实践和性能优化建议

#### `docs/CHANGELOG-agent-containerization.md`
- 本变更日志文件

### 2. 修改文件

#### `src/agent_scheduler/tasks.py`
**变更前**:
- Celery task 直接在进程中运行 agent
- 使用 `run_agent_with_streaming()` 同步执行

**变更后**:
- Celery task 只负责创建容器和监控
- 新增 `create_agent_container()` 函数创建 Docker 容器
- 新增 `monitor_agent_session()` 函数轮询监控 session 状态
- 移除了直接运行 agent 的逻辑
- `run_team_agent_for_web_app_development()` task 改为容器编排模式

**关键改动**:
```python
# 创建 agent 容器
container, container_id = loop.run_until_complete(
    create_agent_container(
        session_id=session_id,
        workspace_id=workspace_id,
        framework=framework,
        prompt=prompt,
    )
)

# 监控 agent session 完成状态
result = loop.run_until_complete(
    monitor_agent_session(
        session_id=session_id,
        container=container,
    )
)
```

#### `src/mgx_api/dao/event_dao.py`
**新增方法**:
- `get_finish_event(session_id)`: 查询 session 的 FINISH 事件
- 用于 Celery task 监控 agent 完成状态

**新增索引**:
- `(session_id, event_type)` 复合索引，优化 FINISH 事件查询性能

#### `src/shared/config/settings.py`
**新增配置项**:
```python
# Agent Container Configuration
agent_container_image: str = "mgx-agent:latest"
agent_container_memory_limit: str = "2g"
agent_container_cpu_quota: int = 100000
agent_task_timeout_seconds: int = 1800
```

#### `.env.example`
**新增配置**:
```bash
# Agent Container Configuration
AGENT_CONTAINER_IMAGE=mgx-agent:latest
AGENT_CONTAINER_MEMORY_LIMIT=2g
AGENT_CONTAINER_CPU_QUOTA=100000
AGENT_TASK_TIMEOUT_SECONDS=1800
```

#### `Makefile`
**新增命令**:
- `make build-agent`: 构建 agent 容器镜像

#### `docs/architecture.md`
**更新内容**:
1. 更新系统架构图，显示 Agent 容器独立运行
2. 更新请求与数据流序列图
3. 新增 "Agent 容器化架构详解" 章节
4. 更新 MGX Backend 组件说明

## 架构对比

### 旧架构

```
FastAPI → Celery Task → Agent (进程内) → MongoDB (写事件)
                ↓
        直接返回结果
```

**问题**:
- Agent 运行在 Celery worker 进程中，隔离性差
- 资源限制困难
- 长时间运行的 agent 占用 worker
- 扩展性受限

### 新架构

```
FastAPI → Celery Task → Docker → Agent Container → MongoDB (写事件)
              ↓                       ↓
         轮询监控              读写 Workspace
              ↓
        返回结果
```

**优势**:
- Agent 在独立容器中运行，完全隔离
- 可以精确控制资源（内存、CPU）
- Celery worker 不被阻塞，只负责编排
- 容器自动清理，资源管理更好
- 更容易扩展和监控

## 职责分离

### Celery Task
- ✅ 创建 agent 容器
- ✅ 传递环境变量和配置
- ✅ 轮询监控 session 状态
- ✅ 处理超时和错误
- ✅ 容器生命周期管理
- ❌ 不再执行 agent 逻辑

### Agent Container
- ✅ 运行 agent 逻辑
- ✅ 读写 workspace 文件
- ✅ 写入事件到 MongoDB
- ✅ 执行完成后退出
- ❌ 不负责容器创建和监控

### FastAPI SSE
- ✅ 读取 event 表
- ✅ 流式推送给客户端
- ❌ 不参与 agent 执行

## 容器生命周期

1. **创建**: Celery task 调用 Docker API 创建容器
2. **启动**: 容器启动并运行 `run_agent.py`
3. **执行**: Agent 运行并写入事件
4. **监控**: Celery 轮询查询 FINISH 事件
5. **完成**: Agent 写入 FINISH 事件并退出
6. **清理**: 容器自动删除（`remove=True`）

## 监控机制

### 轮询间隔
- 每 2 秒轮询一次 event 表
- 检查容器状态和 FINISH 事件

### 超时处理
- 默认超时: 30 分钟（可配置）
- 超时后强制停止容器
- 返回超时错误给调用方

### 状态检查
1. 查询 event 表中的 FINISH 事件
2. 检查容器是否还在运行
3. 检查容器退出码（如果已退出）

## 配置说明

### 资源限制

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `AGENT_CONTAINER_MEMORY_LIMIT` | 2g | 容器内存限制 |
| `AGENT_CONTAINER_CPU_QUOTA` | 100000 | CPU quota (1 CPU) |
| `AGENT_TASK_TIMEOUT_SECONDS` | 1800 | 任务超时时间（30分钟） |

### 镜像配置

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `AGENT_CONTAINER_IMAGE` | mgx-agent:latest | Agent 容器镜像 |

## 部署注意事项

### 1. 构建镜像
```bash
make build-agent
```

### 2. 更新配置
确保 `.env` 文件包含新的配置项

### 3. 重启服务
```bash
make down
make up
```

### 4. 验证
- 检查容器是否能正常创建
- 测试 agent 执行
- 监控容器资源使用

## 向后兼容性

### 破坏性变更
- Celery task 的实现逻辑完全改变
- 需要构建新的 agent 容器镜像
- 需要更新配置文件

### API 兼容性
- FastAPI 接口保持不变
- SSE 事件流格式不变
- 客户端无需修改

## 测试建议

### 单元测试
- 测试 `create_agent_container()` 函数
- 测试 `monitor_agent_session()` 函数
- 测试 `get_finish_event()` 方法

### 集成测试
- 测试完整的容器生命周期
- 测试超时处理
- 测试错误处理
- 测试事件流

### 性能测试
- 容器创建时间
- Agent 执行时间
- 事件查询性能
- 并发容器数量

## 已知问题和限制

1. **容器网络**: 容器需要能访问 MongoDB 和其他服务
2. **日志保留**: 容器删除后日志丢失，需要外部日志系统
3. **并发限制**: 需要配置最大并发容器数量
4. **资源监控**: 需要监控容器资源使用情况

## 未来改进

1. **流式输出**: 实现真正的流式 agent 执行
2. **分布式**: 支持跨主机运行 agent 容器
3. **资源池**: 预创建容器池减少启动时间
4. **日志聚合**: 集成 ELK 或其他日志系统
5. **监控告警**: 集成 Prometheus 和 Grafana
6. **容器编排**: 考虑使用 Kubernetes

## 回滚计划

如果新架构出现问题，可以通过以下步骤回滚：

1. 恢复 `tasks.py` 到之前的版本
2. 移除新增的配置项
3. 重启 Celery worker

**注意**: 需要保留版本控制中的旧代码以便快速回滚。

## 相关文档

- [Agent 容器化使用指南](./agent-container-guide.md)
- [架构文档](./architecture.md)
- [快速开始](./QUICKSTART.md)

## 贡献者

- 架构设计和实现: [您的名字]
- 文档编写: [您的名字]
- 代码审查: [审查者名字]

## 变更日期

- 初始版本: 2026-02-01
- 最后更新: 2026-02-01
