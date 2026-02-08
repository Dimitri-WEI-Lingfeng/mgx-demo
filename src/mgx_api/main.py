"""MGX API main application."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from mgx_api.api import create_api_router
from mgx_api.dao import EventDAO, MessageDAO
from mgx_api.mcp_server import get_mcp_app, mcp
from mgx_api.middleware import create_api_key_mcp_middleware
from mgx_api.services import ApisixService
from shared.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager.

    Handles startup and shutdown events.
    MCP session_manager 需在 lifespan 中运行，否则 MCP 请求会失败。
    """
    # Startup: Initialize database indexes
    print("Initializing database indexes...")
    try:
        event_dao = EventDAO()
        await event_dao.create_indexes()
        print("✓ Event indexes created")

        message_dao = MessageDAO()
        await message_dao.create_indexes()
        print("✓ Message indexes created")
    except Exception as e:
        print(f"Warning: Failed to create indexes: {e}")

    # Startup: Ensure Apisix base routes (/api/*, /oauth2/*) when using traditional + etcd
    try:
        apisix = ApisixService()
        await apisix.ensure_base_routes()
    except Exception as e:
        print(f"Warning: Failed to ensure Apisix base routes: {e}")

    # MCP session_manager 必须运行（get_mcp_app 在下方 mount 时已调用，触发 lazy 初始化）
    async with mcp.session_manager.run():
        yield

    # Shutdown: Cleanup
    print("Shutting down...")


app = FastAPI(
    title="MGX API",
    description="MGX Platform API - workspace, apps, deployment management",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all API routes
app.include_router(create_api_router())

# Mount MCP server with API Key auth (for Agent Docker operations)
_mcp_app = get_mcp_app()
_mcp_app_with_auth = create_api_key_mcp_middleware(_mcp_app)
app.mount(settings.mgx_mcp_path, _mcp_app_with_auth)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        'mgx_api.main:app',
        host='0.0.0.0',
        port=8866,
        reload=True,
    )