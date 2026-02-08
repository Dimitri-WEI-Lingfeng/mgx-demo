# MGX Demo

MGX 是一个 **PaaS 演示平台**，用户可以通过 AI Agent 生成、编辑、部署 Web 应用。

## 🚀 本地 Agent 开发

**无需数据库，快速运行 Agent！**

```bash
# 本地运行 Agent（内存模式）
uv run python src/agents/run_agent_local.py \
  --prompt "创建一个待办事项应用" \
  --framework nextjs

# 查看更多选项
uv run python src/agents/run_agent_local.py --help

```

**特性：**
- ✅ 无需数据库连接
- ✅ 快速启动和调试
- ✅ 完整的事件和消息追踪（SSE 流式输出）
- ✅ 支持自定义工作区路径
- ✅ Rich CLI UI（彩色输出、emoji、表格）

**详细文档：**
- [Context 重构指南](docs/context-refactoring-guide.md)
- [CLI UI 快速开始](docs/cli-ui-quick-start.md)
- [API 文档](src/agents/context/README.md)

---

## 快速开始（完整平台）

### 1. 安装依赖

```bash
make install
```

### 2. 启动后端服务

```bash
make up
```

这会启动：
- Etcd（Apisix 配置中心，端口 2379）
- Apisix（网关，端口 9080）
- MongoDB（数据库，端口 27017）
- Redis（Celery broker，端口 6379）
- OAuth2 Provider（端口 8001）
- MGX API（端口 8000）
- Frontend（端口 8080）
- Celery Worker（Agent Runtime）

### 3. 构建统一镜像（首次部署或代码变更后）

```bash
make build-mgx
```

### 4. 访问前端

**Docker 方式**（`make up` 已包含）：访问 **http://localhost:8080**。前端通过 `VITE_API_BASE` 将 `/api`、`/oauth2`、`/apps` 请求指向 Apisix（localhost:9080）。

**本地开发**（热更新）：

```bash
make frontend
# 或
cd frontend && pnpm dev
```

前端会在 **http://localhost:5173** 启动，并通过 Vite proxy 将请求代理到 Apisix。

### 5. 登录

- 默认用户名：`admin`
- 默认密码：`admin123`

## 主要功能

- **会话管理**：一个 session = 一个 app
- **代码编辑器**：浏览/编辑 workspace 文件
- **开发环境**：一键启动 dev container，iframe 预览 + 直连 URL
- **生产部署**：构建镜像、部署生产容器、iframe 预览 + 链接
- **只读日志/终端**：查看 dev/prod 容器日志
- **Agent 生成代码**：LangGraph 多智能体团队（Boss、PM、架构师、工程师、QA），隔离容器中执行
- **聊天流式响应**：SSE 实时推送 Agent 事件

## 架构

详见 [`docs/project_description.md`](docs/project_description.md)（含 Mermaid 架构图）。

- **MGX Frontend**：React SPA（Vite + TypeScript）
- **Apisix Gateway**：仅代理（`/api` → MGX API，`/oauth2` → OAuth2 Provider，`/apps` → 动态路由）
- **OAuth2 Provider**：独立服务，签发 JWT（MGX API 与 Apps 共用）
- **MGX API**：FastAPI，可多实例；负责 session、workspace 文件读写、dev/prod 容器管理、Apisix 路由下发、Celery 任务投递
- **Agent Runtime**：Celery worker，在隔离的 mgx-agent 容器中执行 LangGraph web_app_team
- **Workspace**：宿主机目录（`workspaces/`），挂载给 dev container 和 agent 容器

## 技术栈

- **Frontend**: React + TypeScript + Vite
- **Backend**: FastAPI + Python 3.12（单一工程，多模块/多入口）
- **Gateway**: Apache Apisix + Etcd
- **Database**: MongoDB
- **Task Queue**: Celery + Redis
- **Agent**: LangGraph + web_app_team（多智能体）
- **Container**: Docker（统一镜像 `mgx:latest`）
- **Tracing**: OpenTelemetry（待接入）

## 目录结构

```
mgx-demo/
├── frontend/                # MGX UI (React SPA)
├── src/                     # 单一 Python 工程
│   ├── shared/              # 共享模块（settings、db、jwt、utils）
│   ├── oauth2_provider/      # OAuth2 Provider（独立服务）
│   ├── mgx_api/              # MGX API（平台后端）
│   ├── scheduler/            # Agent Runtime（Celery worker）
│   └── agents/              # Agent 实现
│       ├── web_app_team/     # LangGraph 多智能体团队
│       └── context/          # 上下文抽象（内存/数据库）
├── infra/                    # Docker Compose + Apisix 配置
├── workspaces/               # 生成的 app 代码（不入库）
├── docs/                     # 项目文档
└── pyproject.toml            # 统一依赖与入口脚本
```

## Makefile 命令

```bash
make help          # 查看所有命令
make install       # 安装 Python 和前端依赖
make up            # 启动后端服务（docker compose）
make down          # 停止后端服务
make dev           # 启动后端 + 提示启动前端
make frontend      # 启动前端 dev server
make backend       # 重建并重启后端
make backend-local # 本地运行 MGX API（uv run）
make build-mgx     # 构建统一镜像 mgx:latest
make test-image    # 镜像健康检查
make restart       # 清理 Dev/Agent 容器 + 重建 + 启动
make clean         # 清理容器、卷、workspaces
make test          # 运行测试
```

## 限制（Demo）

- App 仅单实例部署（1 个容器或前后端各 1 个）
- 无 HTTPS
- 无多租户

## 接下来

- [ ] 实现 SSH 开发（dev container 内 sshd）
- [ ] 实现 App 数据库管理
- [ ] 实现 App 用户管理
- [ ] 接入 OpenTelemetry

## 更多文档

- [项目需求与架构](docs/project_description.md)
- [快速开始指南](docs/getting-started.md)
- [Agent 容器指南](docs/agent-container-guide.md)
