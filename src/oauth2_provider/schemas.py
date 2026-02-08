"""OAuth2 Provider schemas."""
from pydantic import BaseModel


class TokenResponse(BaseModel):
    """OAuth2 token response."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
