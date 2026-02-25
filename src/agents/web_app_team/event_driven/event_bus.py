"""异步事件总线：发布/订阅模型，支持并发处理。

EventBus 是整个事件驱动架构的核心，负责：
1. 管理 Agent 的事件订阅
2. 分发事件到所有订阅者
3. 并发执行订阅者的处理函数
4. 维护事件历史用于调试和回溯
"""

from __future__ import annotations

import asyncio
import traceback
from collections import defaultdict
from typing import Callable, Awaitable, Any

from loguru import logger

from agents.web_app_team.event_driven.team_events import TeamEventType, TeamEvent


EventHandler = Callable[[TeamEvent], Awaitable[list[TeamEvent] | None]]


class EventBus:
    """异步事件总线。

    支持多个 handler 订阅同一事件类型，事件发布时并发调用所有订阅者。
    handler 可以返回新的 TeamEvent 列表，这些事件会被继续分发（级联触发）。
    """

    def __init__(self, max_cascade_depth: int = 20) -> None:
        self._handlers: dict[TeamEventType, list[tuple[str, EventHandler]]] = defaultdict(list)
        self._event_history: list[TeamEvent] = []
        self._max_cascade_depth = max_cascade_depth
        self._running = False
        self._queue: asyncio.Queue[TeamEvent] = asyncio.Queue()
        self._on_event_callbacks: list[Callable[[TeamEvent], Awaitable[None]]] = []

    def subscribe(
        self,
        event_type: TeamEventType,
        handler: EventHandler,
        agent_name: str = "unknown",
    ) -> None:
        """订阅事件。

        Args:
            event_type: 要订阅的事件类型
            handler: 异步处理函数，接收 TeamEvent，可返回新事件列表
            agent_name: 订阅者名称（用于日志）
        """
        self._handlers[event_type].append((agent_name, handler))
        logger.debug(f"[EventBus] {agent_name} 订阅了 {event_type.value}")

    def subscribe_many(
        self,
        event_types: list[TeamEventType],
        handler: EventHandler,
        agent_name: str = "unknown",
    ) -> None:
        """批量订阅多个事件类型。"""
        for et in event_types:
            self.subscribe(et, handler, agent_name)

    def on_event(self, callback: Callable[[TeamEvent], Awaitable[None]]) -> None:
        """注册全局事件回调（用于 SSE 推送等旁路观测）。"""
        self._on_event_callbacks.append(callback)

    async def publish(self, event: TeamEvent) -> None:
        """发布事件到队列。"""
        await self._queue.put(event)

    async def publish_many(self, events: list[TeamEvent]) -> None:
        """批量发布事件。"""
        for e in events:
            await self._queue.put(e)

    async def _dispatch(self, event: TeamEvent, depth: int = 0) -> None:
        """分发事件到所有订阅者，并发执行。

        Args:
            event: 要分发的事件
            depth: 当前级联深度，防止无限递归
        """
        if depth > self._max_cascade_depth:
            logger.warning(f"[EventBus] 级联深度超过 {self._max_cascade_depth}，丢弃事件: {event}")
            return

        self._event_history.append(event)

        for cb in self._on_event_callbacks:
            try:
                await cb(event)
            except Exception:
                logger.error(f"[EventBus] on_event 回调异常:\n{traceback.format_exc()}")

        handlers = self._handlers.get(event.event_type, [])
        if not handlers:
            logger.debug(f"[EventBus] 事件 {event.event_type.value} 没有订阅者")
            return

        # SEND_TO_AGENT 类型只分发给目标 agent
        if event.event_type == TeamEventType.SEND_TO_AGENT and event.target_agent:
            handlers = [(name, h) for name, h in handlers if name == event.target_agent]

        logger.info(
            f"[EventBus] 分发 {event.event_type.value} "
            f"(from={event.source_agent}) -> {[n for n, _ in handlers]}"
        )

        async def _run_handler(name: str, handler: EventHandler) -> list[TeamEvent]:
            try:
                result = await handler(event)
                return result or []
            except Exception:
                logger.error(f"[EventBus] handler {name} 处理 {event.event_type.value} 异常:\n{traceback.format_exc()}")
                return [
                    TeamEvent(
                        event_type=TeamEventType.WORKFLOW_ERROR,
                        source_agent=name,
                        payload={"error": traceback.format_exc(), "original_event": repr(event)},
                    )
                ]

        tasks = [_run_handler(name, h) for name, h in handlers]
        results = await asyncio.gather(*tasks)

        cascaded_events: list[TeamEvent] = []
        for result_list in results:
            cascaded_events.extend(result_list)

        for cascaded in cascaded_events:
            await self._dispatch(cascaded, depth + 1)

    async def run(self) -> None:
        """启动事件循环，从队列中取出事件并分发。

        调用 stop() 后退出循环。
        """
        self._running = True
        logger.info("[EventBus] 事件循环启动")
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            await self._dispatch(event)
            self._queue.task_done()
        logger.info("[EventBus] 事件循环结束")

    def stop(self) -> None:
        """停止事件循环。"""
        self._running = False

    @property
    def event_history(self) -> list[TeamEvent]:
        return list(self._event_history)

    def get_subscriptions(self) -> dict[str, list[str]]:
        """返回所有订阅关系（用于调试）。"""
        result: dict[str, list[str]] = defaultdict(list)
        for event_type, handler_list in self._handlers.items():
            for agent_name, _ in handler_list:
                result[agent_name].append(event_type.value)
        return dict(result)
