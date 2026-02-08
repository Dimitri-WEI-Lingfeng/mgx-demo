"""DevServerEvent middleware - 当 start_dev_server 工具调用成功后发送 CUSTOM 事件到前端。

通过 wrap_tool_call 在外层拦截工具调用，无需修改工具本身。
"""

import time
import uuid
from typing import Any, Callable

from langchain.agents.middleware.types import AgentMiddleware, AgentState
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from typing_extensions import override

from agents.context import require_context
from shared.schemas import Event, EventType


def _get_tool_name(tool_call: Any) -> str:
    """从 tool_call 提取工具名称。"""
    if isinstance(tool_call, dict):
        return str(tool_call.get("name", ""))
    return str(getattr(tool_call, "name", "") or "")


class DevServerEventMiddleware(AgentMiddleware[AgentState[Any], Any]):
    """在 start_dev_server 工具调用成功后，向 EventStore 写入 CUSTOM 事件。"""

    @override
    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        """同步包装：先执行工具，成功后若为 start_dev_server 则发送事件。"""
        result = handler(request)
        tool_name = _get_tool_name(request.tool_call)
        if tool_name == "start_dev_server":
            self._emit_dev_server_started_event_sync()
        return result

    @override
    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Any],
    ) -> ToolMessage | Command:
        """异步包装：先执行工具，成功后若为 start_dev_server 则发送事件。"""
        result = await handler(request)
        tool_name = _get_tool_name(request.tool_call)
        if tool_name == "start_dev_server":
            await self._emit_dev_server_started_event()
        return result

    def _emit_dev_server_started_event_sync(self) -> None:
        """同步发送 dev_server_started 事件（fallback，工具为同步时使用）。"""
        try:
            context = require_context()
            event = Event(
                event_id=str(uuid.uuid4()),
                session_id=context.session_id,
                timestamp=time.time(),
                event_type=EventType.CUSTOM,
                agent_name="engineer",
                data={"custom_type": "dev_server_started"},
            )
            import asyncio

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(context.event_store.create_event(event))
            except RuntimeError:
                asyncio.run(context.event_store.create_event(event))
        except Exception:
            pass  # 不因事件发送失败影响工具执行

    async def _emit_dev_server_started_event(self) -> None:
        """异步发送 dev_server_started 事件。"""
        try:
            context = require_context()
            event = Event(
                event_id=str(uuid.uuid4()),
                session_id=context.session_id,
                timestamp=time.time(),
                event_type=EventType.CUSTOM,
                agent_name="engineer",
                data={"custom_type": "dev_server_started"},
            )
            await context.event_store.create_event(event)
        except Exception:
            pass  # 不因事件发送失败影响工具执行
