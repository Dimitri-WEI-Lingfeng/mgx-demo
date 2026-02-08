# MGX Demo

MGX 是一个 **PaaS 演示平台**，用户可以通过 AI Agent 生成、编辑、部署 Web 应用。

## 🚀 本地 Agent 开发（新功能）

**无需数据库，快速运行 Agent！**

```bash
# 本地运行 Agent（内存模式）
uv run python scripts/run_agent_local.py \
  --prompt "创建一个待办事项应用" \
  --framework nextjs

# 查看更多选项
uv run python scripts/run_agent_local.py --help

# 运行示例
uv run python examples/quick_start_memory_mode.py
```

**特性：**
- ✅ 无需数据库连接
- ✅ 快速启动和调试
- ✅ 完整的事件和消息追踪
- ✅ 支持自定义工作区路径

**详细文档：**
- [Context 重构指南](docs/context-refactoring-guide.md)
- [API 文档](src/agents/context/README.md)
- [完整变更日志](change-logs/2025-02-01-context-abstraction.md)

---

## 快速开始（完整平台）

### 1. 启动基础设施（后端）

```bash
cd infra
docker compose up -d
```

这会启动：
- Apisix（网关，端口 9080）
- MongoDB（数据库，端口 27017）
- Redis（Celery broker，端口 6379）
- OAuth2 Provider（端口 8001）
- MGX API（端口 8000）
- Celery Worker（Agent Runtime）

### 2. 启动前端（开发模式）

```bash
cd frontend
pnpm install
pnpm dev
```

前端会在 `http://localhost:5173` 启动，并通过 Vite proxy 将 `/api`、`/oauth2`、`/apps` 请求代理到 Apisix (localhost:9080)。

### 3. 登录

- 默认用户名：`admin`
- 默认密码：`admin123`

## 主要功能

- **会话管理**：一个 session = 一个 app
- **代码编辑器**：浏览/编辑 workspace 文件
- **开发环境**：一键启动 dev container，iframe 预览前端页面
- **生产部署**：构建镜像、部署生产容器、iframe 预览 + 链接
- **只读日志/终端**：查看 dev/prod 容器日志
- **Agent 生成代码**：通过 Celery 调用 agent（stub，后续接入 langchain multiagents）

## 架构

详见 [`docs/project_description.md`](docs/project_description.md)（含 Mermaid 架构图）。

- **MGX Frontend**：React SPA（Vite + TypeScript）
- **Apisix Gateway**：仅代理（`/api` → MGX API，`/oauth2` → OAuth2 Provider，`/apps` → 动态路由）
- **OAuth2 Provider**：独立服务，签发 JWT（MGX API 与 Apps 都用同一个 provider）
- **MGX API**：FastAPI，可多实例；负责 session、workspace 文件读写、dev/prod 容器管理、Apisix 路由下发、Celery 任务投递
- **Agent Runtime**：Celery worker，在隔离容器中生成代码写入 workspace
- **Workspace**：宿主机目录（`workspaces/`），挂载给 dev container

## 技术栈

- **Frontend**: React + TypeScript + Vite
- **Backend**: FastAPI + Python 3.11（单一工程，多模块/多入口）
- **Gateway**: Apache Apisix
- **Database**: MongoDB
- **Task Queue**: Celery + Redis
- **Agent**: langchain multiagents（待接入）
- **Container**: Docker
- **Tracing**: OpenTelemetry（待接入）

## 目录结构

```
mgx-demo/
├── frontend/                # MGX UI (React SPA)
├── src/                     # 单一 Python 工程
│   ├── shared/             # 共享模块（settings、db、jwt/jwks、utils）
│   ├── oauth2_provider/    # OAuth2 Provider（独立服务）
│   ├── mgx_api/            # MGX API（平台后端）
│   └── agent_scheduler/      # Agent Runtime（Celery worker）
├── infra/                   # Docker Compose + Apisix 配置
├── workspaces/              # 生成的 app 代码（不入库）
├── docs/                    # 项目文档
└── pyproject.toml          # 统一依赖与入口脚本
```

## 开发命令

```bash
# 后端（通过 docker compose）
cd infra && docker compose up

# 前端（本地开发）
cd frontend && pnpm dev

# 或使用入口脚本（需先 pip install -e .）
mgx-api                # uvicorn mgx_api.main:app --port 8000
oauth2-provider        # uvicorn oauth2_provider.main:app --port 8001
agent-worker           # celery -A agent_scheduler.tasks worker
```

## 限制（Demo）

- App 仅单实例部署（1 个容器或前后端各 1 个）
- 无 HTTPS
- 无多租户

## 接下来

- [ ] 接入 langchain multiagents 实现真正的代码生成
- [ ] 实现 SSH 开发（dev container 内 sshd）
- [ ] 实现 App 数据库管理
- [ ] 实现 App 用户管理
- [ ] 接入 OpenTelemetry
- [ ] 添加聊天流式响应

## 更多文档

- [项目需求与架构](docs/project_description.md)
- [快速开始指南](docs/getting-started.md)
