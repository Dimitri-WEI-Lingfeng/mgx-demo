# MGX Demo 实施总结

## 已完成功能

### 1. 单一 Python 工程架构（src 平铺）

```
src/
├── shared/              # 共享模块
│   ├── settings.py     # 统一配置
│   ├── db.py          # MongoDB 客户端
│   ├── security.py    # JWT/JWKS/密码哈希
│   └── utils.py       # 路径安全工具
├── oauth2_provider/    # OAuth2 Provider（独立服务）
│   ├── main.py        # FastAPI app: /oauth2/token + /oauth2/jwks
│   ├── schemas.py
│   └── cli.py         # 入口脚本
├── mgx_api/           # MGX API（可多实例）
│   ├── main.py        # FastAPI app（所有 API 路由）
│   ├── auth.py        # JWKS 拉取/token 校验
│   ├── workspace.py   # Workspace 文件读写
│   ├── docker_manager.py   # Dev/Prod 容器管理
│   ├── apisix_manager.py   # 动态路由下发
│   ├── schemas.py
│   └── cli.py
└── agent_scheduler/     # Celery Worker
    ├── tasks.py       # run_team_agent_for_web_app_development 任务（stub）
    └── cli.py
```

### 2. OAuth2 Provider（独立服务）

- `POST /oauth2/token`：用户名密码登录，签发 JWT access token
- `GET /oauth2/jwks`：发布 JWKS（HS256 oct key）
- 用户存储：MongoDB `users` collection
- 自动初始化默认 admin 用户

### 3. MGX API（多实例友好）

#### 鉴权
- 从 OAuth2 Provider 拉取 JWKS（5 分钟缓存）
- 校验 bearer token（issuer/audience）
- `get_current_user` 依赖注入保护路由

#### Session/App 管理
- `POST /api/sessions`：创建 session（=app），初始化 workspace
- `GET /api/sessions/{id}`：获取 session 信息

#### Workspace 文件 API（代码编辑器）
- `GET /api/workspaces/{id}/entries?path=...`：列目录
- `GET /api/workspaces/{id}/files?path=...`：读文件
- `PUT /api/workspaces/{id}/files?path=...`：写文件
- 路径安全：强制落在 workspace 根目录内（防穿越）

#### Dev Container 管理
- `POST /api/apps/{id}/dev/start`：启动 dev container（挂载 workspace）
- `GET /api/apps/{id}/dev/status`：查询状态
- `POST /api/apps/{id}/dev/stop`：停止容器
- 支持框架：Next.js（node:20）、FastAPI+Vite（python:3.11）
- 自动下发 Apisix 路由：`/apps/{app}/dev/` → 容器前端端口

#### Production Build & Deploy
- `POST /api/apps/{id}/prod/build`：构建镜像（生成 Dockerfile + docker build）
- `POST /api/apps/{id}/prod/deploy`：部署生产容器
- `GET /api/apps/{id}/prod/status`：查询状态
- `POST /api/apps/{id}/prod/stop`：停止容器
- 自动下发 Apisix 路由：`/apps/{app}/prod/` → 生产容器

#### 只读日志/终端
- `GET /api/apps/{id}/logs?target=dev|prod&tail=100`：获取容器日志

#### Agent 任务
- `POST /api/apps/{id}/agent/generate`：投递代码生成任务（Celery）
- `GET /api/apps/{id}/agent/tasks/{task_id}`：查询任务状态/结果

### 4. Agent Runtime（Celery Worker）

- 任务：`run_team_agent_for_web_app_development(session_id, workspace_id, framework, prompt)`
- 当前实现：stub，写入示例文件到 workspace
- 返回：`{status, changed_files, logs}`
- 后续：接入 langchain multiagents

### 5. 基础设施（Docker Compose + Apisix）

- **docker-compose.yml**：
  - mongodb
  - redis
  - apisix（HTTP 9080、Admin 9180）
  - oauth2-provider（容器内 8001）
  - mgx-api（容器内 8000，挂载 docker.sock + workspaces/）
  - celery-worker（挂载 workspaces/）
- **Apisix 静态路由**：
  - `/api/*` → mgx-api:8000
  - `/oauth2/*` → oauth2-provider:8001
- **动态路由**：`/apps/{app}/dev|prod/` 由 MGX API 通过 Admin API 下发

### 6. 前端（MGX UI）

#### 组件
- `Login`：用户名密码登录
- `SessionManager`：创建 session/app
- `FileExplorer`：文件树 + 编辑器（读写 workspace 文件）
- `DevConsole`：启动 dev、iframe 预览 `/apps/{app}/dev/`、查看日志
- `ProdConsole`：build & deploy、iframe 预览 `/apps/{app}/prod/`、生产链接、查看日志

#### API 客户端
- `src/api/client.ts`：封装所有 API 调用（login、session、workspace、dev/prod、logs、agent）

#### Vite 代理配置
- `/api` → `localhost:9080`
- `/oauth2` → `localhost:9080`
- `/apps` → `localhost:9080`

## 验收清单（端到端）

- [x] 登录功能（admin/admin123）
- [x] 创建 session/app
- [x] Workspace 文件浏览/编辑
- [x] 启动 dev container
- [x] iframe 预览 `/apps/{app}/dev/`
- [x] 查看 dev 日志
- [x] 构建生产镜像
- [x] 部署生产容器
- [x] iframe 预览 `/apps/{app}/prod/`
- [x] 生产环境链接（新标签页打开）
- [x] Agent 任务投递与查询（stub）

## 已知限制 & 待实现

### 代码层面
- SSH 开发：需要定制 dev container 镜像内置 sshd + 密钥管理
- langchain multiagents 集成：需要在 `agent_scheduler/tasks.py` 中接入真正的 agent 代码生成逻辑
- App 数据库管理：为每个 app 分配独立 MongoDB 连接/管理接口
- App 用户管理：app 内的用户 CRUD
- OpenTelemetry：接入 trace 与 logging

### 配置层面
- 生产环境需修改所有默认密钥（JWT_SECRET_KEY、APISIX_ADMIN_KEY）
- 容器网络：当前使用 `host.docker.internal`（Mac/Win）；Linux 需改为容器 IP 或 host 网络
- Apisix 路由重写：当前用 `proxy-rewrite` 去除 `/apps/{app}/dev|prod/` 前缀；若 app 前端用绝对路径资源会有问题

### UI/UX
- 聊天流式响应：当前只能"投递任务→轮询结果"；可改为 SSE/WebSocket 流式
- 文件编辑器可集成 Monaco Editor
- 日志实时流可改为 WebSocket

## 启动流程（快速验证）

```bash
# 终端 1：启动后端
cd infra
docker compose up

# 终端 2：启动前端
cd frontend
pnpm install
pnpm dev

# 浏览器
open http://localhost:5173
```

登录 → 创建 app（如 `test-app`，framework `fastapi-vite`）→ 编辑 `README.md` → 保存 → 切换到 "Dev Environment" → 点 "Start Dev" → 等待 iframe 显示（注意：需要 workspace 有合法的 package.json / requirements.txt 才能真正跑起来，当前只是 stub 演示）。
