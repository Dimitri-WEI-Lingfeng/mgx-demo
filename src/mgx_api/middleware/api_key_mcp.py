"""API Key 鉴权中间件 - 用于保护 MCP 端点。

对发往 MCP 的请求校验 X-API-Key header。API Key 与 session 绑定，当前使用 session_id 作为 API Key：
- Agent 容器启动时由 scheduler 注入 MGX_AGENT_API_KEY=session_id
- 中间件校验 X-API-Key 对应的 session 是否存在于数据库
- 若配置了 MGX_AGENT_API_KEY（兼容/测试），与其匹配也放行
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from mgx_api.dao import SessionDAO
from shared.config import settings


class ApiKeyMCPMiddleware(BaseHTTPMiddleware):
    """校验 X-API-Key（session_id 或兼容的 MGX_AGENT_API_KEY）的 ASGI 中间件。"""

    async def dispatch(self, request: Request, call_next) -> Response:
        api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization", "").replace("Bearer ", "")
        if not api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing X-API-Key or Authorization header"},
            )
        # 兼容：配置了 MGX_AGENT_API_KEY 时，与其匹配也放行（测试/本地开发）
        if settings.mgx_agent_api_key and api_key == settings.mgx_agent_api_key:
            return await call_next(request)
        # 主逻辑：api_key 作为 session_id 校验，可以使用 redis 缓存优化查询速度
        session_dao = SessionDAO()
        session = await session_dao.find_by_id(api_key)
        if session is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or unknown session ID"},
            )
        return await call_next(request)


def create_api_key_mcp_middleware(app):
    """将 MCP app 包装在 API Key 鉴权中间件中。"""
    return ApiKeyMCPMiddleware(app)
