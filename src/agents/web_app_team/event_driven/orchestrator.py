"""事件驱动编排器。

替代原有的 LangGraph 顺序工作流，通过 EventBus 协调所有 Agent。
提供与 run_agent.py 兼容的接口。
"""

from __future__ import annotations

import asyncio
import time
import traceback
import uuid
from typing import Any, Callable, Awaitable

from langchain_openai import ChatOpenAI
from langgraph.graph.state import CompiledStateGraph
from loguru import logger

from agents.web_app_team.event_driven.event_bus import EventBus
from agents.web_app_team.event_driven.team_events import TeamEventType, TeamEvent
from agents.web_app_team.event_driven.shared_state import SharedArtifactState
from agents.web_app_team.event_driven.agents import (
    BossAgent,
    ProductManagerAgent,
    ArchitectAgent,
    ProjectManagerAgent,
    EngineerAgent,
    QAAgent,
)

# 终止事件集合
_TERMINAL_EVENTS = {
    TeamEventType.WORKFLOW_COMPLETE,
    TeamEventType.WORKFLOW_ERROR,
    TeamEventType.TEST_PASSED,
}


class EventDrivenOrchestrator:
    """事件驱动的团队编排器。

    创建 EventBus 和所有 Agent，发布初始事件启动工作流，
    监听终止事件判断何时完成。
    """

    def __init__(
        self,
        boss_agent: CompiledStateGraph,
        pm_agent: CompiledStateGraph,
        architect_agent: CompiledStateGraph,
        pjm_agent: CompiledStateGraph,
        engineer_agent: CompiledStateGraph,
        qa_agent: CompiledStateGraph,
        framework: str = "nextjs",
        workspace_id: str = "",
        max_cascade_depth: int = 20,
    ) -> None:
        self.event_bus = EventBus(max_cascade_depth=max_cascade_depth)
        self.shared_state = SharedArtifactState(
            workspace_id=workspace_id,
            framework=framework,
        )

        self._completion_event = asyncio.Event()
        self._final_status: str = "success"
        self._final_error: str | None = None

        self.agents: list = []
        self._create_agents(
            boss_agent, pm_agent, architect_agent,
            pjm_agent, engineer_agent, qa_agent,
        )

        self.event_bus.subscribe(
            TeamEventType.TEST_PASSED,
            self._on_terminal,
            agent_name="orchestrator",
        )
        self.event_bus.subscribe(
            TeamEventType.WORKFLOW_COMPLETE,
            self._on_terminal,
            agent_name="orchestrator",
        )
        self.event_bus.subscribe(
            TeamEventType.WORKFLOW_ERROR,
            self._on_error,
            agent_name="orchestrator",
        )

    def _create_agents(
        self,
        boss_agent: CompiledStateGraph,
        pm_agent: CompiledStateGraph,
        architect_agent: CompiledStateGraph,
        pjm_agent: CompiledStateGraph,
        engineer_agent: CompiledStateGraph,
        qa_agent: CompiledStateGraph,
    ) -> None:
        """创建所有事件驱动 Agent 并注册到 EventBus。"""
        self.agents = [
            BossAgent("boss", boss_agent, self.event_bus, self.shared_state),
            ProductManagerAgent("product_manager", pm_agent, self.event_bus, self.shared_state),
            ArchitectAgent("architect", architect_agent, self.event_bus, self.shared_state),
            ProjectManagerAgent("project_manager", pjm_agent, self.event_bus, self.shared_state),
            EngineerAgent("engineer", engineer_agent, self.event_bus, self.shared_state),
            QAAgent("qa", qa_agent, self.event_bus, self.shared_state),
        ]

    async def _on_terminal(self, event: TeamEvent) -> list[TeamEvent] | None:
        """终止事件处理：测试通过或流程完成。"""
        logger.info(f"[Orchestrator] 收到终止事件: {event.event_type.value}")
        self._final_status = "success"
        self._completion_event.set()
        self.event_bus.stop()
        return None

    async def _on_error(self, event: TeamEvent) -> list[TeamEvent] | None:
        """错误事件处理。"""
        error = event.payload.get("error", "unknown error")
        logger.error(f"[Orchestrator] 工作流错误: {error}")
        self._final_status = "failed"
        self._final_error = str(error)
        self._completion_event.set()
        self.event_bus.stop()
        return None

    def on_team_event(self, callback: Callable[[TeamEvent], Awaitable[None]]) -> None:
        """注册 TeamEvent 全局回调（用于 SSE 推送到前端）。"""
        self.event_bus.on_event(callback)

    async def run(self, prompt: str, timeout: float = 1800) -> dict[str, Any]:
        """运行事件驱动工作流。

        Args:
            prompt: 用户需求描述
            timeout: 最大执行时间（秒）

        Returns:
            包含 status 和其他结果信息的字典
        """
        logger.info(f"[Orchestrator] 启动事件驱动工作流，prompt: {prompt[:100]}...")

        subs = self.event_bus.get_subscriptions()
        logger.info(f"[Orchestrator] 订阅关系:\n" + "\n".join(
            f"  {agent}: {events}" for agent, events in subs.items()
        ))

        bus_task = asyncio.create_task(self.event_bus.run())

        initial_event = TeamEvent(
            event_type=TeamEventType.USER_REQUEST,
            source_agent="user",
            payload={"prompt": prompt},
        )
        await self.event_bus.publish(initial_event)

        try:
            await asyncio.wait_for(self._completion_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"[Orchestrator] 工作流超时 ({timeout}s)")
            self._final_status = "timeout"
            self.event_bus.stop()

        await asyncio.sleep(0.1)
        if not bus_task.done():
            bus_task.cancel()
            try:
                await bus_task
            except asyncio.CancelledError:
                pass

        state_snapshot = await self.shared_state.snapshot()
        return {
            "status": self._final_status,
            "error": self._final_error,
            "state": state_snapshot,
            "event_count": len(self.event_bus.event_history),
            "events": [
                {
                    "type": e.event_type.value,
                    "source": e.source_agent,
                    "target": e.target_agent,
                }
                for e in self.event_bus.event_history
            ],
        }
