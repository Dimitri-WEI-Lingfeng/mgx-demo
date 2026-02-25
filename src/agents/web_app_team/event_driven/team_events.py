"""团队内部事件类型定义。

这些事件是 Agent 之间通信的载体，与 SSE 推送给前端的 Event 不同。
TeamEvent 是内部协作事件，前端的 Event 是观测/展示事件。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TeamEventType(str, Enum):
    """团队协作事件类型。"""

    # --- 用户输入 ---
    USER_REQUEST = "user_request"

    # --- 需求阶段 ---
    REQUIREMENTS_CREATED = "requirements_created"
    PRD_UPDATED = "prd_updated"

    # --- 设计阶段 ---
    DESIGN_UPDATED = "design_updated"

    # --- 任务阶段 ---
    TASKS_CREATED = "tasks_created"

    # --- 开发阶段 ---
    CODE_WRITTEN = "code_written"
    CODE_SUMMARY = "code_summary"

    # --- 测试阶段 ---
    TEST_REPORT = "test_report"
    TEST_PASSED = "test_passed"
    TEST_FAILED = "test_failed"

    # --- Agent 间通信 ---
    SEND_TO_AGENT = "send_to_agent"
    REVIEW_FEEDBACK = "review_feedback"

    # --- 生命周期 ---
    AGENT_DONE = "agent_done"
    WORKFLOW_COMPLETE = "workflow_complete"
    WORKFLOW_ERROR = "workflow_error"


@dataclass
class TeamEvent:
    """团队协作事件。

    Attributes:
        event_type: 事件类型
        source_agent: 发出事件的 agent 名称
        target_agent: 目标 agent（仅 SEND_TO_AGENT 时使用）
        payload: 事件数据
        metadata: 额外元数据
    """

    event_type: TeamEventType
    source_agent: str
    payload: dict[str, Any] = field(default_factory=dict)
    target_agent: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        target = f" -> {self.target_agent}" if self.target_agent else ""
        return f"TeamEvent({self.event_type.value}, from={self.source_agent}{target})"
