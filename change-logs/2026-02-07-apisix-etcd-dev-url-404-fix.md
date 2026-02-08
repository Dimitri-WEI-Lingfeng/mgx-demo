# Apisix 改用 etcd 修复 dev URL 404

**日期**: 2026-02-07

## 问题

dev status 接口返回了 `dev_url`（如 `http://localhost:9080/apps/{workspace_id}/dev/`），但访问该 URL 时返回 404。

## 根因

项目此前使用 Apisix **data_plane + yaml** 模式：

```yaml
deployment:
  role: data_plane
  role_data_plane:
    config_provider: yaml
```

在此模式下：
- Admin API **不监听** 9180 端口
- 配置仅从 `apisix.yaml` 文件读取
- mgx-api 通过 `ApisixService.create_or_update_route()` 调用的 Admin API 无法生效
- 动态路由 `/apps/{workspace_id}/dev/*` 从未被创建

## 解决方案

改用 **traditional + etcd** 模式，使 Admin API 可用：

1. **添加 etcd 服务**：作为 Apisix 配置中心
2. **修改 Apisix config**：`role: traditional`，`config_provider: etcd`
3. **mgx-api 启动时注册基础路由**：`/api/*`、`/oauth2/*` 通过 `ensure_base_routes()` 写入 etcd
4. **dev 容器创建时**：`create_or_update_route()` 可正常创建 `/apps/*` 路由

## 变更文件

- `infra/docker-compose.yml`：新增 etcd 服务，apisix 依赖 etcd，移除 apisix.yaml 挂载，mgx-api 挂载 apisix.yaml 并依赖 apisix
- `infra/apisix/config.yaml`：改为 traditional + etcd
- `src/mgx_api/services/apisix_service.py`：新增 `ensure_base_routes()`，从 `apisix.yaml` 读取路由并写入 etcd
- `src/mgx_api/main.py`：启动时调用 `ensure_base_routes()`
- `scripts/check_apisix_routes.py`：诊断脚本，用于查询 Apisix 中的路由

## 诊断

修改后可用 Admin API 查询路由：

```bash
# 从宿主机（需确保 9180 端口可访问）
uv run python scripts/check_apisix_routes.py

# 或直接 curl
curl -H "X-API-KEY: apisix-admin-key-please-change" \
  "http://localhost:9180/apisix/admin/routes"
```
