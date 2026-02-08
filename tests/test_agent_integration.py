"""Agent 集成测试。"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture(autouse=True)
def add_src_to_path():
    """确保 src 在 Python 路径中。"""
    import sys
    from pathlib import Path
    src = Path(__file__).parent.parent / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


class TestAgentImports:
    """测试 agent 模块导入。"""

    def test_import_agent_factory(self):
        """测试 agent_factory 导入。"""
        from agents.agent_factory import create_code_generation_agent, create_team_agent

        assert create_code_generation_agent is not None
        assert create_team_agent is not None

    def test_import_run_agent(self):
        """测试 run_agent 导入。"""
        from agents.run_agent import (
            run_agent_with_streaming,
            run_team_agent_with_streaming,
            create_event,
            create_message,
        )

        assert run_agent_with_streaming is not None
        assert run_team_agent_with_streaming is not None
        assert create_event is not None
        assert create_message is not None

    def test_import_web_app_team(self):
        """测试 web_app_team 导入。"""
        from agents.web_app_team import create_web_app_team
        from agents.web_app_team.graph import create_team_graph
        from agents.web_app_team.state import create_initial_state

        assert create_web_app_team is not None
        assert create_team_graph is not None
        assert create_initial_state is not None


class TestEventCreation:
    """测试 Event 创建与校验。"""

    def test_create_event_agent_start(self):
        """测试 AGENT_START 事件创建。"""
        from shared.schemas import Event, EventType
        import uuid
        import time

        event = Event(
            event_id=str(uuid.uuid4()),
            session_id="test-session",
            timestamp=time.time(),
            event_type=EventType.AGENT_START,
            data={"prompt": "创建一个待办应用", "framework": "nextjs"},
        )
        assert event.event_type == EventType.AGENT_START
        typed = event.get_typed_data()
        assert typed.prompt == "创建一个待办应用"
        assert typed.framework == "nextjs"

    def test_create_event_stage_change_with_aliases(self):
        """测试 STAGE_CHANGE 事件支持 old_stage/new_stage 别名。"""
        from shared.schemas import Event, EventType
        import uuid
        import time

        event = Event(
            event_id=str(uuid.uuid4()),
            session_id="test-session",
            timestamp=time.time(),
            event_type=EventType.STAGE_CHANGE,
            data={"old_stage": "requirement", "new_stage": "design"},
        )
        typed = event.get_typed_data()
        assert typed.from_stage == "requirement"
        assert typed.to_stage == "design"

    def test_create_event_node_start_without_agent_name(self):
        """测试 NODE_START 事件 agent_name 可选。"""
        from shared.schemas import Event, EventType
        import uuid
        import time

        event = Event(
            event_id=str(uuid.uuid4()),
            session_id="test-session",
            timestamp=time.time(),
            event_type=EventType.NODE_START,
            data={"node_name": "boss"},
        )
        assert event.event_type == EventType.NODE_START
        typed = event.get_typed_data()
        assert typed.node_name == "boss"


@pytest.mark.asyncio
class TestAgentContext:
    """测试 Agent 上下文与事件存储。"""

    async def test_memory_context_event_flow(self, agent_context):
        """测试内存模式下事件创建与存储流程。"""
        from shared.schemas import Event, EventType
        import uuid
        import time

        event = Event(
            event_id=str(uuid.uuid4()),
            session_id=agent_context.session_id,
            timestamp=time.time(),
            event_type=EventType.AGENT_START,
            data={"prompt": "测试", "framework": "nextjs"},
        )
        await agent_context.event_store.create_event(event)

        events = agent_context.event_store.get_events()
        assert len(events) == 1
        assert events[0]["event_type"] == "agent_start"
        assert events[0]["data"]["prompt"] == "测试"

    async def test_memory_context_message_flow(self, agent_context):
        """测试内存模式下消息创建与存储流程。"""
        from shared.schemas import Message

        msg = Message(
            message_id="msg-1",
            session_id=agent_context.session_id,
            role="user",
            content="创建一个待办应用",
            timestamp=123.0,
        )
        await agent_context.message_store.create_message(msg)

        messages = agent_context.message_store.get_messages()
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "创建一个待办应用"

    async def test_memory_context_get_session_messages_paginated(self, agent_context):
        """测试 InMemoryMessageStore.get_session_messages_paginated。"""
        from shared.schemas import Message

        session_id = agent_context.session_id
        msgs = [
            Message(message_id="m1", session_id=session_id, role="user", content="1", timestamp=100.0),
            Message(message_id="m2", session_id=session_id, role="assistant", content="2", timestamp=101.0),
            Message(message_id="m3", session_id=session_id, role="user", content="3", timestamp=102.0),
        ]
        for m in msgs:
            await agent_context.message_store.create_message(m)

        # 最近 n 条
        result = await agent_context.message_store.get_session_messages_paginated(
            session_id=session_id, limit=2, last_message_id=None
        )
        assert len(result) == 2
        assert result[0].message_id == "m2"
        assert result[1].message_id == "m3"

        # before m3
        result = await agent_context.message_store.get_session_messages_paginated(
            session_id=session_id, limit=2, before_message_id="m3"
        )
        assert len(result) == 2
        assert result[0].message_id == "m1"
        assert result[1].message_id == "m2"


@pytest.mark.asyncio
class TestRunAgentIntegration:
    """测试 run_agent 集成（mock LLM）。"""

    @pytest.mark.skip(reason="需要 mock agent.invoke，且 env 可能无 API key")
    async def test_run_agent_with_streaming_single_mode(self, agent_context):
        """测试单 agent 模式运行（需 mock）。"""
        from agents.run_agent import run_agent_with_streaming

        mock_agent = MagicMock()
        mock_agent.invoke = MagicMock(
            return_value={"output": "已根据需求生成代码"}
        )

        with patch(
            "agents.run_agent.create_code_generation_agent",
            return_value=mock_agent,
        ):
            result = await run_agent_with_streaming(
                context=agent_context,
                framework="nextjs",
                prompt="创建一个简单的待办应用",
            )

        assert result["status"] == "success"
        assert result["session_id"] == agent_context.session_id
        events = agent_context.event_store.get_events()
        assert any(e.get("event_type") == "agent_start" for e in events)
        assert any(e.get("event_type") == "finish" for e in events)

    async def test_run_agent_error_emits_agent_error_event(self, agent_context):
        """测试 agent 异常时发送 AGENT_ERROR 和 FINISH 事件。"""
        from agents.run_agent import run_agent_with_streaming

        mock_agent = MagicMock()
        mock_agent.invoke = MagicMock(side_effect=ValueError("模拟 LLM 错误"))

        with patch(
            "agents.run_agent.create_code_generation_agent",
            return_value=mock_agent,
        ):
            # invoke 是同步的，run_agent 用 asyncio.to_thread
            result = await run_agent_with_streaming(
                context=agent_context,
                framework="nextjs",
                prompt="测试",
            )

        assert result["status"] == "failed"
        assert "error" in result

        events = agent_context.event_store.get_events()
        event_types = [e.get("event_type") for e in events]
        assert "agent_error" in event_types
        assert "finish" in event_types


class TestTeamAgent:
    """测试团队 Agent。"""

    def test_create_initial_state(self):
        """测试创建初始状态。"""
        from agents.web_app_team.state import create_initial_state

        state = create_initial_state(
            workspace_id="test-ws",
            framework="nextjs",
            user_prompt="创建一个博客应用",
        )
        assert state["workspace_id"] == "test-ws"
        assert state["framework"] == "nextjs"
        assert any("创建一个博客应用" in str(m.content) for m in state["messages"])
        assert "messages" in state
        assert state["current_stage"] == "requirement"
        assert "next_agent_instruction" in state
        assert state["next_agent_instruction"] is None
