"""事件驱动 Agent 基类。

EventDrivenAgent 将现有的 LangGraph Agent 包装为事件驱动模型：
- 订阅指定事件类型
- 收到事件后调用底层 LangGraph Agent 执行
- 执行完成后发布新事件通知其他 Agent
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Any

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langgraph.graph.state import CompiledStateGraph
from loguru import logger

from agents.web_app_team.event_driven.event_bus import EventBus
from agents.web_app_team.event_driven.team_events import TeamEventType, TeamEvent
from agents.web_app_team.event_driven.shared_state import SharedArtifactState


class EventDrivenAgent(ABC):
    """事件驱动 Agent 基类。

    子类需要实现:
    - subscribed_events: 返回要订阅的事件类型列表
    - handle_event: 处理事件并返回新事件
    """

    def __init__(
        self,
        name: str,
        agent: CompiledStateGraph,
        event_bus: EventBus,
        shared_state: SharedArtifactState,
    ) -> None:
        self.name = name
        self.agent = agent
        self.event_bus = event_bus
        self.shared_state = shared_state
        self._register()

    def _register(self) -> None:
        """向 EventBus 注册自己订阅的事件。"""
        events = self.subscribed_events()
        self.event_bus.subscribe_many(events, self.handle_event, agent_name=self.name)
        logger.info(f"[{self.name}] 注册完成，订阅事件: {[e.value for e in events]}")

    @abstractmethod
    def subscribed_events(self) -> list[TeamEventType]:
        """返回该 Agent 要订阅的事件类型列表。"""
        ...

    @abstractmethod
    async def handle_event(self, event: TeamEvent) -> list[TeamEvent] | None:
        """处理收到的事件。

        Args:
            event: 收到的团队事件

        Returns:
            处理后要发布的新事件列表，或 None
        """
        ...

    async def _invoke_agent(self, prompt: str, history: list[BaseMessage] | None = None) -> dict[str, Any]:
        """调用底层 LangGraph Agent。

        Args:
            prompt: 指令/提示
            history: 可选的历史消息

        Returns:
            Agent 的执行结果 state
        """
        messages: list[BaseMessage] = []
        if history:
            messages.extend(history)
        messages.append(HumanMessage(content=prompt))

        state = {"messages": messages}
        logger.info(f"[{self.name}] 开始执行，prompt: {prompt[:100]}...")

        result = await self.agent.ainvoke(state)
        logger.info(f"[{self.name}] 执行完成")
        return result

    async def _stream_agent(self, prompt: str, history: list[BaseMessage] | None = None):
        """流式调用底层 LangGraph Agent（用于 SSE 推送）。

        Yields:
            (namespace, stream_mode, chunk) 三元组
        """
        messages: list[BaseMessage] = []
        if history:
            messages.extend(history)
        messages.append(HumanMessage(content=prompt))

        state = {"messages": messages}
        logger.info(f"[{self.name}] 开始流式执行，prompt: {prompt[:100]}...")

        async for output in self.agent.astream(
            state,
            stream_mode=["updates", "messages"],
            subgraphs=True,
        ):
            yield output

    def _extract_last_ai_content(self, result: dict[str, Any]) -> str:
        """从 Agent 执行结果中提取最后一条 AI 消息内容。"""
        messages = result.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                content = msg.content
                if isinstance(content, list):
                    return " ".join(
                        c.get("text", "") if isinstance(c, dict) else str(c) for c in content
                    )
                return str(content)
        return ""

    def _make_event(
        self,
        event_type: TeamEventType,
        payload: dict[str, Any] | None = None,
        target_agent: str | None = None,
    ) -> TeamEvent:
        """创建一个 TeamEvent。"""
        return TeamEvent(
            event_type=event_type,
            source_agent=self.name,
            payload=payload or {},
            target_agent=target_agent,
        )
