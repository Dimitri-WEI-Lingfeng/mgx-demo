# MGX Demo - 快速开始指南

## 前置条件

- Docker & Docker Compose
- Node.js 20+ & pnpm
- Python 3.11+

## 启动步骤

### 1. 安装 Python 依赖（可选，docker compose 会自动安装）

```bash
pip install -e .
```

### 2. 启动后端服务

```bash
cd infra
docker compose up -d
```

等待服务启动（约 30 秒）。检查状态：

```bash
docker compose ps
```

### 3. 启动前端

```bash
cd frontend
pnpm install
pnpm dev
```

### 4. 访问 MGX UI

打开浏览器：`http://localhost:5173`

登录：
- 用户名：`admin`
- 密码：`admin123`

## 使用流程

### 创建 App

1. 登录后，输入 app 名称（如 `my-app`）
2. 选择框架（FastAPI+Vite 或 Next.js）
3. 点击 "Create"

### 编辑代码

1. 切换到 "Code Editor" 标签
2. 浏览文件树
3. 点击文件查看/编辑内容
4. 修改后点击 "Save"

### 启动开发环境

1. 切换到 "Dev Environment" 标签
2. 点击 "Start Dev"
3. 等待容器启动（会自动下发 Apisix 路由）
4. iframe 会显示 `/apps/{app-name}/dev/` 的预览
5. 可点击 "Refresh Logs" 查看只读日志/终端

### 构建与部署生产环境

1. 切换到 "Production" 标签
2. 点击 "Build Image"（会在 workspace 生成 Dockerfile 并构建）
3. 构建成功后，点击 "Deploy"
4. iframe 会显示 `/apps/{app-name}/prod/` 的预览
5. 可点击链接在新标签页打开生产环境

### 调用 Agent 生成代码（TODO）

后端已预留 `/api/apps/{id}/agent/generate` 接口，前端可集成聊天窗口调用。

## 端口映射

| 服务 | 容器端口 | 宿主机端口 | 说明 |
|------|---------|-----------|------|
| Apisix Gateway | 9080 | 9080 | HTTP 入口（前端 dev 代理到这里） |
| Apisix Admin | 9180 | 9180 | Admin API（MGX API 用于动态路由） |
| MGX API | 8000 | 8000 | 平台 API |
| OAuth2 Provider | 8001 | 8001 | 认证服务 |
| MongoDB | 27017 | 27017 | 数据库 |
| Redis | 6379 | 6379 | Celery broker |

## 数据目录

- `workspaces/`：所有 app 的代码（按 workspace_id 组织，已加入 .gitignore）

## 故障排查

### Apisix 路由不通

检查 Apisix Admin API：

```bash
curl -H "X-API-KEY: edd1c9f034335f136f87ad84b625c8f1" http://localhost:9180/apisix/admin/routes
```

### MongoDB 连接失败

确保 MongoDB 容器已启动：

```bash
docker compose ps mongodb
```

### Celery worker 无响应

查看 worker 日志：

```bash
docker compose logs celery-worker
```

### 前端 API 调用失败

- 检查 Vite proxy 配置（`frontend/vite.config.ts`）
- 确认 Apisix 在 `localhost:9080` 可访问
- 打开浏览器 DevTools 查看网络请求
