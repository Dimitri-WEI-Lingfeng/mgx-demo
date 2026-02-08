"""Container related schemas."""
from pydantic import BaseModel


class DevContainerResponse(BaseModel):
    """Dev container status response."""
    container_id: str | None = None
    container_name: str | None = None
    status: str
    ports: dict[str, str] = {}
    dev_url: str | None = None


class ProdBuildResponse(BaseModel):
    """Production build response."""
    image_id: str | None = None
    image_tag: str | None = None
    status: str
    logs: str | None = None
    error: str | None = None


class ProdContainerResponse(BaseModel):
    """Production container status response."""
    container_id: str | None = None
    container_name: str | None = None
    status: str
    ports: dict[str, str] = {}
    prod_url: str | None = None
