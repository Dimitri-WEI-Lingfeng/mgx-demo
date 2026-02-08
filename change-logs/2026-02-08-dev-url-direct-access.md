# Dev URL 直连改造

**日期**: 2026-02-08

## 变更

将 dev status 接口返回的 `dev_url` 从 APISIX 代理路径改为直接返回容器暴露的 host:port。

- **原**: `http://localhost:9080/apps/{workspace_id}/dev/`（经 APISIX 代理）
- **新**: `http://localhost:{host_port}`（直接访问容器端口）

## 原因

Dev server（如 Next.js）会访问 `/.next`、`/_next` 等路径，通过 APISIX 代理时存在路径匹配和转发不便的问题。

## 变更文件

- `src/shared/config/settings.py`: 新增 `dev_external_host` 配置（默认 `http://localhost`）
- `.env.example`: 新增 `DEV_EXTERNAL_HOST` 示例
- `src/mgx_api/api/dev.py`: 移除 APISIX 路由创建，dev_url 改为直连 URL
- `src/mgx_api/services/docker_service.py`: 移除 `_ensure_dev_container` 和 `_start_dev_server_impl` 中的 dev 路由创建逻辑

## 配置

远程部署时需设置 `DEV_EXTERNAL_HOST=http://<宿主机IP>`，使浏览器能访问到宿主机端口。
