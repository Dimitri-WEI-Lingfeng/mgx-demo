"""Apisix route management service."""
from pathlib import Path

import httpx
import yaml

from shared.config import settings


def _load_base_routes_from_yaml() -> list[tuple[str, dict]]:
    """从 apisix.yaml 加载 routes（仅包含 id 的项，排除 /apps/* 动态路由）。"""
    path = Path(settings.apisix_yaml_path)
    if not path.exists():
        return []
    raw = path.read_text()
    if "#END" in raw:
        raw = raw.split("#END")[0].strip()
    data = yaml.safe_load(raw) or {}
    routes = data.get("routes") or []
    result = []
    for r in routes:
        if not isinstance(r, dict):
            continue
        rid = r.get("id")
        if not rid or not isinstance(rid, str):
            continue
        # 仅同步静态路由，/apps/* 由 create_or_update_route 动态创建
        if "/apps/" in str(r.get("uri", "")):
            continue
        config = {k: v for k, v in r.items() if k != "id"}
        result.append((rid, config))
    return result


async def _put_route(route_id: str, route_config: dict, timeout: float = 2.0) -> dict:
    """Put route via Apisix Admin API."""
    admin_url = f"{settings.apisix_admin_url}/apisix/admin/routes/{route_id}"
    headers = {"X-API-KEY": settings.apisix_admin_key}
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.put(admin_url, json=route_config, headers=headers)
        resp.raise_for_status()
        return resp.json()


class ApisixService:
    """Apisix route management business logic."""
    
    async def create_or_update_route(
        self,
        workspace_id: str,
        target_type: str,
        upstream_host: str,
        upstream_port: int,
    ) -> dict:
        """
        Create or update Apisix route for an app.

        Args:
            workspace_id: Workspace ID (route path: /apps/{workspace_id}/{target_type}/*)
            target_type: "dev" or "prod"
            upstream_host: Target container host/IP
            upstream_port: Target container port

        Returns:
            Route info
        """
        route_id = f"{workspace_id}-{target_type}"
        route_uri = f"/apps/{workspace_id}/{target_type}/*"

        route_config = {
            "uri": route_uri,
            "name": route_id,
            "methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
            "upstream": {
                "type": "roundrobin",
                "nodes": {
                    f"{upstream_host}:{upstream_port}": 1
                }
            },
            "plugins": {
                "proxy-rewrite": {
                    "regex_uri": [f"^/apps/{workspace_id}/{target_type}/(.*)$", "/$1"]
                }
            }
        }
        
        return await _put_route(route_id, route_config)

    async def ensure_base_routes(self) -> None:
        """
        将 apisix.yaml 中的基础路由（/api/*, /oauth2/*）同步到 Apisix（写入 etcd）。
        traditional + etcd 模式下，etcd 启动时为空，需通过此方法载入 apisix.yaml 配置。
        """
        base_routes = _load_base_routes_from_yaml()
        if not base_routes:
            # 无 apisix.yaml 时（如 standalone 测试）使用默认配置
            base_routes = [
                ("mgx-api", {
                    "uri": "/api/*", "name": "MGX API",
                    "methods": ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
                    "upstream": {"type": "roundrobin", "nodes": {"mgx-api:8000": 1}},
                    "plugins": {"proxy-rewrite": {"regex_uri": ["^/api/(.*)$", "/$1"]}},
                }),
                ("oauth2-provider", {
                    "uri": "/oauth2/*", "name": "OAuth2 Provider",
                    "methods": ["GET", "POST", "OPTIONS", "HEAD"],
                    "upstream": {"type": "roundrobin", "nodes": {"oauth2-provider:8001": 1}},
                    "plugins": {"proxy-rewrite": {"regex_uri": ["^/oauth2/(.*)$", "/$1"]}},
                }),
            ]
        for route_id, config in base_routes:
            try:
                await _put_route(route_id, config)
                print(f"✓ Apisix route {route_id} created/updated")
            except Exception as e:
                print(f"⚠ Apisix base route {route_id}: {e}")
    
    async def delete_route(self, workspace_id: str, target_type: str) -> None:
        """
        Delete Apisix route.

        Args:
            workspace_id: Workspace ID
            target_type: "dev" or "prod"
        """
        route_id = f"{workspace_id}-{target_type}"
        admin_url = f"{settings.apisix_admin_url}/apisix/admin/routes/{route_id}"
        headers = {"X-API-KEY": settings.apisix_admin_key}
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.delete(admin_url, headers=headers)
                resp.raise_for_status()
            except httpx.HTTPStatusError:
                pass  # Ignore if route doesn't exist
