"""Authentication routes."""
from fastapi import APIRouter, Depends

from mgx_api.dependencies import get_current_user

router = APIRouter()


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Get current user info (protected endpoint).
    
    This is a test endpoint to verify authentication works.
    """
    return {
        "username": current_user.get("sub"),
        "issuer": current_user.get("iss"),
        "audience": current_user.get("aud"),
    }
