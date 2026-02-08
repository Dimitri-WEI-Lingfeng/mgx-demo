"""Authentication dependencies."""
import base64
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from shared.config import settings


# OAuth2 scheme pointing to the OAuth2 Provider
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.oauth2_provider_url}/token")


# JWKS cache
_jwks_cache: dict[str, Any] = {"keys": [], "expires_at": 0}


def _base64url_decode(value: str) -> bytes:
    """Base64url decode (adding padding if needed)."""
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


async def _fetch_jwks() -> dict[str, Any]:
    """Fetch JWKS from OAuth2 Provider and cache it."""
    now = int(datetime.now(timezone.utc).timestamp())
    
    # Return cached JWKS if still valid
    if _jwks_cache["keys"] and _jwks_cache["expires_at"] > now:
        return _jwks_cache
    
    # Fetch new JWKS
    jwks_url = f"{settings.oauth2_provider_url}/jwks"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(jwks_url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Failed to fetch JWKS: {str(e)}",
        )
    
    # Update cache
    _jwks_cache["keys"] = data.get("keys", [])
    _jwks_cache["expires_at"] = now + settings.jwks_cache_seconds
    
    return _jwks_cache


async def _get_hs256_secret() -> str:
    """Get HS256 secret from JWKS (oct key type)."""
    jwks = await _fetch_jwks()
    
    for key in jwks.get("keys", []):
        if key.get("kty") == "oct" and key.get("alg") == "HS256":
            k_value = key.get("k")
            if not k_value:
                continue
            return _base64url_decode(k_value).decode("utf-8")
    
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="JWKS does not contain valid HS256 oct key",
    )


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict[str, Any]:
    """
    Verify JWT token and return the payload.
    
    This dependency can be used to protect routes.
    
    Args:
        token: JWT token from Authorization header
        
    Returns:
        Decoded JWT payload
        
    Raises:
        HTTPException: If token is invalid
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        secret = await _get_hs256_secret()
        payload = jwt.decode(
            token,
            secret,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
        return payload
    except JWTError:
        raise credentials_exception
