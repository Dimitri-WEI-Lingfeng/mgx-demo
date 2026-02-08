"""OAuth2 Provider main application."""
import time

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm

from shared.database.mongodb import get_db
from shared.security.jwt import create_access_token, build_jwks
from shared.security.password import hash_password, verify_password
from shared.config.settings import settings

from .schemas import TokenResponse


app = FastAPI(
    title="MGX OAuth2 Provider",
    description="JWT token issuer for MGX platform",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _get_user(username: str):
    """Get user from database."""
    db = get_db()
    return await db["users"].find_one({"username": username})


async def _ensure_default_admin():
    """Ensure default admin user exists."""
    if not settings.default_admin_username:
        return
    
    existing = await _get_user(settings.default_admin_username)
    if existing:
        return
    
    db = get_db()
    await db["users"].insert_one({
        "username": settings.default_admin_username,
        "password_hash": hash_password(settings.default_admin_password),
        "is_admin": True,
        "created_at": time.time(),
    })


@app.on_event("startup")
async def startup():
    """Startup tasks."""
    await _ensure_default_admin()


@app.post("/token", response_model=TokenResponse)
async def issue_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    OAuth2 password grant: issue JWT access token.
    
    - **username**: User's username
    - **password**: User's password
    """
    user = await _get_user(form_data.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token, exp_ts = create_access_token(form_data.username)
    expires_in = max(0, exp_ts - int(time.time()))
    
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
    )


@app.get("/jwks")
async def jwks():
    """
    Get JSON Web Key Set (JWKS) for token verification.
    
    Returns the public key information (HS256 symmetric key as oct type).
    """
    return build_jwks()


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "oauth2-provider"}
