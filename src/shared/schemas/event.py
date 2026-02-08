"""Event schema for agent streaming."""
from enum import Enum
from typing import Any, Union

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class EventType(str, Enum):
    """Event types for agent streaming."""
    
    # Agent lifecycle events
    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    AGENT_ERROR = "agent_error"
    
    # LLM events (delta)
    LLM_START = "llm_start"
    LLM_STREAM = "llm_stream"  # delta event
    LLM_END = "llm_end"
    
    # Tool events
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    
    # Message events
    MESSAGE_DELTA = "message_delta"  # incremental message
    MESSAGE_COMPLETE = "message_complete"  # complete message
    
    # Team workflow events
    NODE_START = "node_start"  # 节点开始执行
    NODE_END = "node_end"  # 节点执行完成
    STAGE_CHANGE = "stage_change"  # 工作流阶段变更
    
    # Custom events
    CUSTOM = "custom"
    
    # Termination event
    FINISH = "finish"


# ==================== Event Data Types ====================

class AgentStartData(BaseModel):
    """AGENT_START 事件数据。"""
    prompt: str = Field(..., description="用户提示词")
    framework: str = Field(..., description="目标框架")
    mode: str | None = Field(None, description="运行模式 (single/team)")


class AgentEndData(BaseModel):
    """AGENT_END 事件数据。"""
    status: str = Field(..., description="执行状态 (success/failed)")
    output: str = Field(default="", description="输出内容")
    stage: str | None = Field(None, description="当前工作阶段")
    prd_document: str | None = Field(None, description="PRD 文档路径")
    design_document: str | None = Field(None, description="设计文档路径")


class AgentErrorData(BaseModel):
    """AGENT_ERROR 事件数据。"""
    error: str = Field(..., description="错误信息")
    error_type: str = Field(..., description="错误类型")
    details: str | None = Field(None, description="详细错误堆栈")


class LLMStartData(BaseModel):
    """LLM_START 事件数据。"""
    model: str | None = Field(None, description="模型名称")
    prompt: str | None = Field(None, description="提示词")
    temperature: float | None = Field(None, description="温度参数")


class LLMStreamData(BaseModel):
    """LLM_STREAM 事件数据（增量）。"""
    model_config = ConfigDict(extra="allow")

    delta: str = Field(..., description="增量文本内容")
    content_type: str = Field(default="text", description="内容类型")


class LLMEndData(BaseModel):
    """LLM_END 事件数据。"""
    content: str = Field(..., description="完整输出内容")
    usage: dict[str, Any] | None = Field(None, description="Token 使用统计")
    finish_reason: str | None = Field(None, description="结束原因")


class ToolStartData(BaseModel):
    """TOOL_START 事件数据。"""
    tool_name: str = Field(..., description="工具名称")
    tool_args: dict[str, Any] = Field(default_factory=dict, description="工具参数")


class ToolEndData(BaseModel):
    """TOOL_END 事件数据。"""
    tool_name: str = Field(..., description="工具名称")
    tool_result: Any = Field(..., description="工具执行结果")
    success: bool = Field(default=True, description="是否执行成功")
    error: str | None = Field(None, description="错误信息（如果失败）")


class MessageDeltaData(BaseModel):
    """MESSAGE_DELTA 事件数据（增量）。"""
    delta: str = Field(..., description="增量消息内容")
    role: str | None = Field(None, description="消息角色")


class MessageCompleteData(BaseModel):
    """MESSAGE_COMPLETE 事件数据。"""
    content: str = Field(..., description="完整消息内容")
    role: str | None = Field(None, description="消息角色")
    stage: str | None = Field(None, description="当前工作阶段")


class NodeStartData(BaseModel):
    """NODE_START 事件数据（团队工作流节点开始）。"""
    node_name: str = Field(..., description="节点名称")
    agent_name: str | None = Field(None, description="Agent 名称")


class NodeEndData(BaseModel):
    """NODE_END 事件数据（团队工作流节点完成）。"""
    node_name: str = Field(..., description="节点名称")
    agent_name: str | None = Field(None, description="Agent 名称")
    output: str | None = Field(None, description="节点输出")


class StageChangeData(BaseModel):
    """STAGE_CHANGE 事件数据（工作流阶段变更）。"""
    model_config = ConfigDict(populate_by_name=True)

    from_stage: str | None = Field(
        None,
        description="原阶段",
        validation_alias=AliasChoices("from_stage", "old_stage"),
    )
    to_stage: str = Field(
        ...,
        description="目标阶段",
        validation_alias=AliasChoices("to_stage", "new_stage"),
    )


class FinishData(BaseModel):
    """FINISH 事件数据。"""
    status: str = Field(..., description="最终状态 (success/error)")
    error: str | None = Field(None, description="错误信息（如果失败）")


class CustomData(BaseModel):
    """CUSTOM 事件数据（任意键值）。"""
    model_config = ConfigDict(extra="allow")


# EventData 联合类型：所有已知 event_type 对应的 data 类型
EventData = Union[
    AgentStartData,
    AgentEndData,
    AgentErrorData,
    LLMStartData,
    LLMStreamData,
    LLMEndData,
    ToolStartData,
    ToolEndData,
    MessageDeltaData,
    MessageCompleteData,
    NodeStartData,
    NodeEndData,
    StageChangeData,
    FinishData,
    CustomData,
]


class Event(BaseModel):
    """Event model for agent streaming.
    
    This schema is compatible with langchain streaming protocol and
    integrates with langfuse for tracing.
    """
    
    event_id: str = Field(..., description="Unique event ID (UUID)")
    session_id: str = Field(..., description="Session ID this event belongs to")
    timestamp: float = Field(..., description="Unix timestamp when event was created")
    event_type: EventType = Field(..., description="Type of event")
    agent_name: str | None = Field(None, description="Name of the agent that created this event")
    
    # Langchain streaming compatible fields
    run_id: str | None = Field(None, description="Langchain run ID")
    parent_ids: list[str] = Field(default_factory=list, description="Parent run IDs")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    # Langfuse trace association fields
    trace_id: str | None = Field(None, description="Langfuse trace ID")
    observation_id: str | None = Field(None, description="Langfuse observation ID")
    
    # Event data payload
    data: dict[str, Any] = Field(..., description="Event data containing delta/chunk and other incremental data")
    
    # Associated message (if any)
    message_id: str | None = Field(None, description="Associated message ID")

    @model_validator(mode="after")
    def validate_data_for_event_type(self) -> "Event":
        """根据 event_type 校验 data 字段类型。"""
        type_map = {
            EventType.AGENT_START: AgentStartData,
            EventType.AGENT_END: AgentEndData,
            EventType.AGENT_ERROR: AgentErrorData,
            EventType.LLM_START: LLMStartData,
            EventType.LLM_STREAM: LLMStreamData,
            EventType.LLM_END: LLMEndData,
            EventType.TOOL_START: ToolStartData,
            EventType.TOOL_END: ToolEndData,
            EventType.MESSAGE_DELTA: MessageDeltaData,
            EventType.MESSAGE_COMPLETE: MessageCompleteData,
            EventType.NODE_START: NodeStartData,
            EventType.NODE_END: NodeEndData,
            EventType.STAGE_CHANGE: StageChangeData,
            EventType.FINISH: FinishData,
            EventType.CUSTOM: CustomData,
        }
        data_class = type_map.get(self.event_type)
        if data_class:
            data_class.model_validate(self.data)
        return self

    def get_typed_data(self) -> Union[
        AgentStartData,
        AgentEndData,
        AgentErrorData,
        LLMStartData,
        LLMStreamData,
        LLMEndData,
        ToolStartData,
        ToolEndData,
        MessageDeltaData,
        MessageCompleteData,
        NodeStartData,
        NodeEndData,
        StageChangeData,
        FinishData,
        CustomData,
        dict,
    ]:
        """获取类型化的事件数据。
        
        Returns:
            根据 event_type 返回对应的类型化数据模型，如果类型未知则返回原始 dict。
        """
        type_map = {
            EventType.AGENT_START: AgentStartData,
            EventType.AGENT_END: AgentEndData,
            EventType.AGENT_ERROR: AgentErrorData,
            EventType.LLM_START: LLMStartData,
            EventType.LLM_STREAM: LLMStreamData,
            EventType.LLM_END: LLMEndData,
            EventType.TOOL_START: ToolStartData,
            EventType.TOOL_END: ToolEndData,
            EventType.MESSAGE_DELTA: MessageDeltaData,
            EventType.MESSAGE_COMPLETE: MessageCompleteData,
            EventType.NODE_START: NodeStartData,
            EventType.NODE_END: NodeEndData,
            EventType.STAGE_CHANGE: StageChangeData,
            EventType.FINISH: FinishData,
            EventType.CUSTOM: CustomData,
        }
        
        data_class = type_map.get(self.event_type)
        if data_class:
            return data_class(**self.data)
        return self.data
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "evt_123abc",
                "session_id": "sess_456def",
                "timestamp": 1704067200.0,
                "event_type": "llm_stream",
                "run_id": "run_789ghi",
                "parent_ids": [],
                "tags": ["agent", "llm"],
                "metadata": {},
                "trace_id": "trace_langfuse_123",
                "observation_id": "obs_langfuse_456",
                "data": {
                    "delta": "Hello",
                    "content_type": "text"
                },
                "message_id": None
            }
        }
