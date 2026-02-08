"""Agent/Task related schemas."""
from pydantic import BaseModel


class AgentTaskRequest(BaseModel):
    """Agent task request."""
    prompt: str


class AgentTaskResponse(BaseModel):
    """Agent task response."""
    task_id: str
    status: str


class AgentTaskResult(BaseModel):
    """Agent task result."""
    task_id: str
    status: str
    result: dict | None = None
