"""API routes module."""
from fastapi import APIRouter

from . import health, auth, sessions, workspaces, dev, prod, agent, database


def create_api_router() -> APIRouter:
    """
    Create and configure the main API router.
    
    Returns:
        Configured APIRouter instance
    """
    router = APIRouter()
    
    # Register all route modules
    # Note: No /api prefix here because APISIX rewrites /api/* to /*
    router.include_router(health.router, tags=["Health"])
    router.include_router(auth.router, tags=["Auth"])
    router.include_router(sessions.router, tags=["Sessions"])
    router.include_router(workspaces.router, tags=["Workspaces"])
    router.include_router(dev.router, tags=["Dev Containers"])
    router.include_router(prod.router, tags=["Production"])
    router.include_router(agent.router, tags=["Agent"])
    router.include_router(database.router, tags=["Database"])
    
    return router


__all__ = ["create_api_router"]
