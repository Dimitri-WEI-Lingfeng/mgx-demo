"""JWT encoding/decoding and JWKS utilities."""
import base64
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt

from shared.config import settings


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> tuple[str, int]:
    """
    Create a JWT access token.
    
    Returns:
        tuple of (token_string, expires_timestamp)
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    
    payload = {
        "sub": subject,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, int(expire.timestamp())


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and verify a JWT token.
    
    Raises:
        jose.JWTError: If token is invalid
    """
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
    )


def _base64url_encode(data: bytes) -> str:
    """Base64url encode (no padding)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def build_jwks() -> dict[str, Any]:
    """
    Build JWKS (JSON Web Key Set) for HS256 symmetric key.
    
    Returns JWKS with a single oct (octet sequence) key.
    """
    return {
        "keys": [
            {
                "kty": "oct",
                "k": _base64url_encode(settings.jwt_secret_key.encode("utf-8")),
                "alg": settings.jwt_algorithm,
                "use": "sig",
                "kid": "mgx-hs256-key",
            }
        ]
    }
