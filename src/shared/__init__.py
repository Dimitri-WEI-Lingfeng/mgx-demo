"""Shared utilities and configurations.

This module provides backward compatibility with the old flat structure.
New code should import from the submodules directly.
"""
# Config
from .config import settings

# Database
from .database import get_client, get_db, close_db

# Security
from .security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
    build_jwks,
)

# Utils
from .utils import safe_join


__all__ = [
    # Config
    "settings",
    # Database
    "get_client",
    "get_db",
    "close_db",
    # Security
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_token",
    "build_jwks",
    # Utils
    "safe_join",
]
