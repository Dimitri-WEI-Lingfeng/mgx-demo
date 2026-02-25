"""事件驱动 multi-agent 系统单元测试。"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agents.web_app_team.event_driven.event_bus import EventBus
from agents.web_app_team.event_driven.team_events import TeamEventType, TeamEvent
from agents.web_app_team.event_driven.shared_state import SharedArtifactState
from agents.web_app_team.event_driven.orchestrator import EventDrivenOrchestrator


class TestTeamEvent:
    """TeamEvent 数据类测试。"""

    def test_create_event(self):
        event = TeamEvent(
            event_type=TeamEventType.USER_REQUEST,
            source_agent="user",
            payload={"prompt": "hello"},
        )
        assert event.event_type == TeamEventType.USER_REQUEST
        assert event.source_agent == "user"
        assert event.payload == {"prompt": "hello"}
        assert event.target_agent is None

    def test_create_event_with_target(self):
        event = TeamEvent(
            event_type=TeamEventType.SEND_TO_AGENT,
            source_agent="boss",
            target_agent="engineer",
            payload={"instruction": "fix bug"},
        )
        assert event.target_agent == "engineer"

    def test_repr(self):
        event = TeamEvent(
            event_type=TeamEventType.PRD_UPDATED,
            source_agent="pm",
        )
        assert "prd_updated" in repr(event)
        assert "pm" in repr(event)


class TestEventBus:
    """EventBus 发布/订阅测试。"""

    @pytest.fixture
    def bus(self):
        return EventBus(max_cascade_depth=5)

    async def test_subscribe_and_dispatch(self, bus: EventBus):
        received = []

        async def handler(event: TeamEvent):
            received.append(event)
            return None

        bus.subscribe(TeamEventType.USER_REQUEST, handler, agent_name="test")

        event = TeamEvent(
            event_type=TeamEventType.USER_REQUEST,
            source_agent="user",
            payload={"prompt": "test"},
        )
        await bus._dispatch(event)
        assert len(received) == 1
        assert received[0].source_agent == "user"

    async def test_multiple_subscribers_concurrent(self, bus: EventBus):
        call_order = []

        async def handler_a(event: TeamEvent):
            await asyncio.sleep(0.05)
            call_order.append("a")
            return None

        async def handler_b(event: TeamEvent):
            call_order.append("b")
            return None

        bus.subscribe(TeamEventType.USER_REQUEST, handler_a, agent_name="agent_a")
        bus.subscribe(TeamEventType.USER_REQUEST, handler_b, agent_name="agent_b")

        event = TeamEvent(
            event_type=TeamEventType.USER_REQUEST,
            source_agent="user",
        )
        await bus._dispatch(event)

        assert len(call_order) == 2
        assert "a" in call_order
        assert "b" in call_order
        # b should finish before a due to sleep (concurrent execution)
        assert call_order[0] == "b"

    async def test_cascade_events(self, bus: EventBus):
        """测试级联事件：handler 返回新事件，EventBus 会继续分发。"""
        events_seen = []

        async def handler_req(event: TeamEvent):
            events_seen.append(event.event_type)
            return [
                TeamEvent(
                    event_type=TeamEventType.REQUIREMENTS_CREATED,
                    source_agent="boss",
                    payload={"file": "requirements.md"},
                )
            ]

        async def handler_prd(event: TeamEvent):
            events_seen.append(event.event_type)
            return None

        bus.subscribe(TeamEventType.USER_REQUEST, handler_req, agent_name="boss")
        bus.subscribe(TeamEventType.REQUIREMENTS_CREATED, handler_prd, agent_name="pm")

        event = TeamEvent(
            event_type=TeamEventType.USER_REQUEST,
            source_agent="user",
        )
        await bus._dispatch(event)

        assert TeamEventType.USER_REQUEST in events_seen
        assert TeamEventType.REQUIREMENTS_CREATED in events_seen

    async def test_max_cascade_depth(self, bus: EventBus):
        """测试级联深度限制防止无限递归。"""
        call_count = 0

        async def looping_handler(event: TeamEvent):
            nonlocal call_count
            call_count += 1
            return [
                TeamEvent(
                    event_type=TeamEventType.REVIEW_FEEDBACK,
                    source_agent="loop",
                )
            ]

        bus.subscribe(TeamEventType.REVIEW_FEEDBACK, looping_handler, agent_name="loop")

        event = TeamEvent(
            event_type=TeamEventType.REVIEW_FEEDBACK,
            source_agent="test",
        )
        await bus._dispatch(event)

        assert call_count <= bus._max_cascade_depth + 1

    async def test_send_to_agent_routing(self, bus: EventBus):
        """测试 SEND_TO_AGENT 只发送给目标 agent。"""
        received_by = []

        async def handler_a(event: TeamEvent):
            received_by.append("a")
            return None

        async def handler_b(event: TeamEvent):
            received_by.append("b")
            return None

        bus.subscribe(TeamEventType.SEND_TO_AGENT, handler_a, agent_name="agent_a")
        bus.subscribe(TeamEventType.SEND_TO_AGENT, handler_b, agent_name="agent_b")

        event = TeamEvent(
            event_type=TeamEventType.SEND_TO_AGENT,
            source_agent="boss",
            target_agent="agent_b",
            payload={"instruction": "do something"},
        )
        await bus._dispatch(event)

        assert received_by == ["agent_b"]

    async def test_on_event_callback(self, bus: EventBus):
        """测试全局事件回调。"""
        observed = []

        async def observer(event: TeamEvent):
            observed.append(event.event_type)

        bus.on_event(observer)

        event = TeamEvent(
            event_type=TeamEventType.CODE_WRITTEN,
            source_agent="engineer",
        )
        await bus._dispatch(event)

        assert TeamEventType.CODE_WRITTEN in observed

    async def test_event_history(self, bus: EventBus):
        event = TeamEvent(
            event_type=TeamEventType.USER_REQUEST,
            source_agent="user",
        )
        await bus._dispatch(event)
        assert len(bus.event_history) == 1

    def test_get_subscriptions(self, bus: EventBus):
        async def noop(event):
            return None

        bus.subscribe(TeamEventType.USER_REQUEST, noop, agent_name="boss")
        bus.subscribe(TeamEventType.PRD_UPDATED, noop, agent_name="architect")
        bus.subscribe(TeamEventType.PRD_UPDATED, noop, agent_name="pjm")

        subs = bus.get_subscriptions()
        assert "boss" in subs
        assert "user_request" in subs["boss"]
        assert "architect" in subs
        assert "pjm" in subs

    async def test_handler_error_doesnt_crash_bus(self, bus: EventBus):
        """测试 handler 抛出异常时 EventBus 不崩溃。"""
        async def bad_handler(event: TeamEvent):
            raise RuntimeError("oops")

        async def good_handler(event: TeamEvent):
            return None

        bus.subscribe(TeamEventType.USER_REQUEST, bad_handler, agent_name="bad")
        bus.subscribe(TeamEventType.WORKFLOW_ERROR, good_handler, agent_name="monitor")

        event = TeamEvent(
            event_type=TeamEventType.USER_REQUEST,
            source_agent="user",
        )
        # Should not raise
        await bus._dispatch(event)
        # Error handler should have been called via cascade
        assert any(e.event_type == TeamEventType.WORKFLOW_ERROR for e in bus.event_history)

    async def test_subscribe_many(self, bus: EventBus):
        received = []

        async def handler(event: TeamEvent):
            received.append(event.event_type)
            return None

        bus.subscribe_many(
            [TeamEventType.USER_REQUEST, TeamEventType.PRD_UPDATED],
            handler,
            agent_name="multi",
        )

        await bus._dispatch(TeamEvent(event_type=TeamEventType.USER_REQUEST, source_agent="u"))
        await bus._dispatch(TeamEvent(event_type=TeamEventType.PRD_UPDATED, source_agent="pm"))

        assert TeamEventType.USER_REQUEST in received
        assert TeamEventType.PRD_UPDATED in received


class TestSharedArtifactState:
    """SharedArtifactState 线程安全测试。"""

    async def test_update_and_get(self):
        state = SharedArtifactState(workspace_id="ws-1", framework="nextjs")
        await state.update(prd_doc="prd.md")
        val = await state.get("prd_doc")
        assert val == "prd.md"

    async def test_update_extra(self):
        state = SharedArtifactState()
        await state.update(custom_field="hello")
        val = await state.get("custom_field")
        assert val == "hello"

    async def test_snapshot(self):
        state = SharedArtifactState(workspace_id="ws-2", framework="fastapi-vite")
        await state.update(requirements_doc="req.md", design_doc="design.md")
        snap = await state.snapshot()
        assert snap["workspace_id"] == "ws-2"
        assert snap["requirements_doc"] == "req.md"
        assert snap["design_doc"] == "design.md"

    async def test_concurrent_updates(self):
        state = SharedArtifactState()
        
        async def update_a():
            for _ in range(100):
                await state.update(prd_doc="a")
                await asyncio.sleep(0)
        
        async def update_b():
            for _ in range(100):
                await state.update(prd_doc="b")
                await asyncio.sleep(0)
        
        await asyncio.gather(update_a(), update_b())
        val = await state.get("prd_doc")
        assert val in ("a", "b")


class TestEventDrivenOrchestrator:
    """Orchestrator 集成测试（使用 mock agent）。"""

    def _make_mock_agent(self, response_content: str = "done"):
        """创建 mock 的 CompiledStateGraph。"""
        from langchain_core.messages import AIMessage

        mock = AsyncMock()
        mock.ainvoke = AsyncMock(return_value={
            "messages": [AIMessage(content=response_content)]
        })
        mock.astream = AsyncMock()
        return mock

    async def test_full_workflow_completes(self):
        """测试完整工作流从 USER_REQUEST 到 TEST_PASSED。"""
        boss = self._make_mock_agent("requirements created")
        pm = self._make_mock_agent("PRD written")
        architect = self._make_mock_agent("design created")
        pjm = self._make_mock_agent("tasks split")
        engineer = self._make_mock_agent("code implemented")
        qa = self._make_mock_agent("all tests passed, no failures")

        orchestrator = EventDrivenOrchestrator(
            boss_agent=boss,
            pm_agent=pm,
            architect_agent=architect,
            pjm_agent=pjm,
            engineer_agent=engineer,
            qa_agent=qa,
            framework="nextjs",
            workspace_id="test-ws",
        )

        result = await orchestrator.run(prompt="创建一个 todo app", timeout=30)

        assert result["status"] == "success"
        assert result["event_count"] > 0

        event_types = [e["type"] for e in result["events"]]
        assert "user_request" in event_types
        assert "requirements_created" in event_types
        assert "prd_updated" in event_types
        assert "design_updated" in event_types
        assert "tasks_created" in event_types
        assert "code_written" in event_types
        assert "test_report" in event_types
        assert "test_passed" in event_types

    async def test_workflow_handles_error(self):
        """测试 Agent 抛出异常时工作流能正确处理。"""
        boss = self._make_mock_agent("ok")
        boss.ainvoke = AsyncMock(side_effect=RuntimeError("LLM error"))
        pm = self._make_mock_agent("ok")
        architect = self._make_mock_agent("ok")
        pjm = self._make_mock_agent("ok")
        engineer = self._make_mock_agent("ok")
        qa = self._make_mock_agent("ok")

        orchestrator = EventDrivenOrchestrator(
            boss_agent=boss,
            pm_agent=pm,
            architect_agent=architect,
            pjm_agent=pjm,
            engineer_agent=engineer,
            qa_agent=qa,
            framework="nextjs",
        )

        result = await orchestrator.run(prompt="test error", timeout=10)
        assert result["status"] == "failed"

    async def test_on_team_event_callback(self):
        """测试全局事件回调。"""
        observed_events = []

        async def observer(event: TeamEvent):
            observed_events.append(event.event_type.value)

        boss = self._make_mock_agent("requirements")
        pm = self._make_mock_agent("prd")
        architect = self._make_mock_agent("design")
        pjm = self._make_mock_agent("tasks")
        engineer = self._make_mock_agent("code")
        qa = self._make_mock_agent("all passed")

        orchestrator = EventDrivenOrchestrator(
            boss_agent=boss,
            pm_agent=pm,
            architect_agent=architect,
            pjm_agent=pjm,
            engineer_agent=engineer,
            qa_agent=qa,
            framework="nextjs",
        )
        orchestrator.on_team_event(observer)

        await orchestrator.run(prompt="hello", timeout=30)
        assert len(observed_events) > 0
        assert "user_request" in observed_events

    async def test_timeout(self):
        """测试超时机制。"""
        async def slow_invoke(state):
            await asyncio.sleep(10)
            return {"messages": []}

        boss = self._make_mock_agent("ok")
        boss.ainvoke = slow_invoke
        pm = self._make_mock_agent("ok")
        architect = self._make_mock_agent("ok")
        pjm = self._make_mock_agent("ok")
        engineer = self._make_mock_agent("ok")
        qa = self._make_mock_agent("ok")

        orchestrator = EventDrivenOrchestrator(
            boss_agent=boss,
            pm_agent=pm,
            architect_agent=architect,
            pjm_agent=pjm,
            engineer_agent=engineer,
            qa_agent=qa,
            framework="nextjs",
        )

        result = await orchestrator.run(prompt="test", timeout=2)
        assert result["status"] == "timeout"

    async def test_concurrent_agent_execution(self):
        """验证多个 Agent 可以并发执行。"""
        execution_log = []

        async def slow_boss_invoke(state):
            from langchain_core.messages import AIMessage
            execution_log.append(("boss_start", asyncio.get_event_loop().time()))
            await asyncio.sleep(0.1)
            execution_log.append(("boss_end", asyncio.get_event_loop().time()))
            return {"messages": [AIMessage(content="requirements ok")]}

        boss = self._make_mock_agent("ok")
        boss.ainvoke = slow_boss_invoke
        pm = self._make_mock_agent("prd")
        architect = self._make_mock_agent("design")
        pjm = self._make_mock_agent("tasks")
        engineer = self._make_mock_agent("code")
        qa = self._make_mock_agent("all passed")

        orchestrator = EventDrivenOrchestrator(
            boss_agent=boss,
            pm_agent=pm,
            architect_agent=architect,
            pjm_agent=pjm,
            engineer_agent=engineer,
            qa_agent=qa,
            framework="nextjs",
        )

        result = await orchestrator.run(prompt="test concurrency", timeout=30)
        assert result["status"] == "success"
        assert len(execution_log) == 2
