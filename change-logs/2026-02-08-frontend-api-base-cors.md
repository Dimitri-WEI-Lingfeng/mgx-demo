# 前端 API base_url 编译与 APISIX CORS 配置

## 变更说明

1. **前端 base_url 编译**：`VITE_API_BASE` 在构建时注入，用于跨域请求 APISIX 网关
2. **APISIX CORS**：为 `/api/*` 和 `/oauth2/*` 路由增加 CORS 插件，支持前端跨域请求

## 修改内容

### 1. 前端 (frontend)

- **`.env.example`**：新增示例，说明 `VITE_API_BASE` 用途
- **`Dockerfile`**：增加 `ARG VITE_API_BASE` / `ENV VITE_API_BASE`，默认 `http://localhost:9080`
- **`infra/docker-compose.yml`**：frontend 构建时传入 `VITE_API_BASE`，可从 `VITE_API_BASE` 环境变量覆盖

### 2. APISIX (infra/apisix)

- **`apisix.yaml`**：在 mgx-api、oauth2-provider 路由的 plugins 中增加 `cors`：
  - `allow_credential: true`（支持 Authorization 等带凭证请求）
  - `allow_origins`: localhost/127.0.0.1 的 8080、5173 端口（前端 nginx、vite dev）
  - `allow_methods` / `allow_headers`: `"**"`

## 使用方式

### 本地开发

- 使用 Vite proxy 时：`VITE_API_BASE` 可不设（默认空，走相对路径）
- 直接请求后端时：`.env.local` 中设置 `VITE_API_BASE=http://localhost:9080`

### Docker 部署

```bash
# 默认使用 http://localhost:9080
make restart  # 或 docker compose up --build

# 自定义 base_url（如生产域名）
VITE_API_BASE=https://api.example.com docker compose -f infra/docker-compose.yml up --build
```

### 生产环境 CORS

若前端部署在其它域名，需在 `infra/apisix/apisix.yaml` 的 `cors.allow_origins` 中追加对应 origin。
