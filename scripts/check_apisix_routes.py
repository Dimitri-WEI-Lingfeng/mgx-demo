#!/usr/bin/env python3
"""查询 Apisix Admin API 中的路由配置，用于诊断 dev URL 404 等问题。"""
import os
import sys

try:
    import httpx
except ImportError:
    print("请安装 httpx: pip install httpx 或 uv add httpx")
    sys.exit(1)

ADMIN_URL = os.getenv("APISIX_ADMIN_URL", "http://127.0.0.1:9180")
ADMIN_KEY = os.getenv("APISIX_ADMIN_KEY", "edd1c9f034335f136f87ad84b625c8f1")


def main():
    url = f"{ADMIN_URL.strip('/')}/apisix/admin/routes"
    headers = {"X-API-KEY": ADMIN_KEY}
    print(f"GET {url}")
    try:
        r = httpx.get(url, headers=headers, timeout=5)
        r.raise_for_status()
        data = r.json()
        total = data.get("total", 0)
        routes = data.get("list", [])
        print(f"\n共 {total} 条路由:\n")
        for item in routes:
            v = item.get("value", item)
            rid = v.get("id", v.get("name", "?"))
            uri = v.get("uri", "?")
            upstream = v.get("upstream", {})
            nodes = upstream.get("nodes", {})
            print(f"  [{rid}]")
            print(f"    uri: {uri}")
            print(f"    upstream: {list(nodes.keys()) if nodes else '(none)'}")
            print()
    except httpx.ConnectError as e:
        print(f"连接失败: {e}")
        print("提示: data_plane 模式下 Admin API 不监听，请改用 traditional + etcd 模式")
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(f"HTTP 错误: {e.response.status_code} - {e.response.text[:200]}")
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
