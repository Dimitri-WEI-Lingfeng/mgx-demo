"""Health check routes."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    """Health check endpoint (no auth required)."""
    return {"status": "ok", "service": "mgx-api"}
