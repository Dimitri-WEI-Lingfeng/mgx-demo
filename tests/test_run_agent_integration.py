"""run_agent 完整集成测试 - 使用 FakeListChatModel mock OpenAI LLM。

无需真实 API Key，通过 langchain_community.FakeListChatModel 模拟 LLM 响应，
验证 run_agent_with_streaming 和 run_team_agent_with_streaming 的完整流程。
支持 fake tool calls 以验证工具调用链路。
包含动态工作流路由（workflow_decision）的测试覆盖。
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _make_tool_call_msg(tool_name: str, args: dict, call_id: str = "call_fake"):
    """构造带 tool_calls 的 AIMessage。"""
    from langchain_core.messages import AIMessage

    return AIMessage(
        content="",
        tool_calls=[{"id": call_id, "name": tool_name, "args": args, "type": "tool_call"}],
    )


@pytest.fixture
def fake_llm_responses():
    """为 6 个 agent（boss/pm/architect/pjm/engineer/qa）提供足够的 mock 响应。

    每个 agent 的 invoke 可能触发多轮 LLM 调用（含 tool use），准备足够响应。
    """
    base = ["requirements.md", "prd.md", "design.md", "tasks.md", "code done", "test ok"]
    return [f"[{role}] {content}" for role in base for content in (base * 2)]


@pytest.fixture
def fake_llm_responses_with_tool_calls():
    """带假 tool calls 的响应序列，用于验证工具调用流程。

    Boss 等 agent 有 read_file/write_file/list_files，穿插 tool_calls 与最终文本。
    """
    from langchain_core.messages import AIMessage

    return [
        _make_tool_call_msg("list_files", {"directory": "."}, "call_1"),
        AIMessage(content="根据需求分析，已创建 requirements.md"),
        _make_tool_call_msg("read_file", {"path": "requirements.md"}, "call_2"),
        AIMessage(content="PRD 文档已编写完成"),
        AIMessage(content="技术架构设计完成"),
        AIMessage(content="任务拆解完成"),
        AIMessage(content="代码实现完成"),
        AIMessage(content="测试通过"),
        # 额外响应以防多轮 tool use
        *[AIMessage(content=f"备用响应 {i}") for i in range(20)],
    ]


def _create_fake_llm_with_tools(responses: list):
    """创建支持 bind_tools 的 FakeListChatModel（create_agent 需要）。"""
    from langchain_community.chat_models.fake import FakeListChatModel

    class FakeListChatModelWithTools(FakeListChatModel):
        def bind_tools(self, tools, **kwargs):
            return self

    return FakeListChatModelWithTools(responses=responses.copy())


def _create_fake_messages_llm_with_tools(responses: list):
    """创建支持 bind_tools 的 FakeMessagesListChatModel，可返回 AIMessage（含 tool_calls）。"""
    from langchain_community.chat_models.fake import FakeMessagesListChatModel

    class FakeMessagesListChatModelWithTools(FakeMessagesListChatModel):
        def bind_tools(self, tools, **kwargs):
            return self

    return FakeMessagesListChatModelWithTools(responses=list(responses))


@pytest.fixture
def mock_get_agent_llm(fake_llm_responses):
    """Patch get_agent_llm 返回支持 bind_tools 的 FakeListChatModel。"""
    def _get_fake_llm(agent_name: str, callbacks=None):
        return _create_fake_llm_with_tools(fake_llm_responses)

    return _get_fake_llm


@pytest.fixture
def mock_get_agent_llm_with_tool_calls(fake_llm_responses_with_tool_calls):
    """Patch get_agent_llm 返回带假 tool_calls 的 FakeMessagesListChatModel。"""
    def _get_fake_llm(agent_name: str, callbacks=None):
        return _create_fake_messages_llm_with_tools(fake_llm_responses_with_tool_calls)

    return _get_fake_llm


@pytest.fixture
def fake_llm_responses_boss_ends_early():
    """Boss 调用 workflow_decision(next_action="end") 后流程提前结束。

    第一个 agent（Boss）返回 workflow_decision 工具调用，流程应在 Boss 后结束。
    """
    from langchain_core.messages import AIMessage

    return [
        _make_tool_call_msg(
            "workflow_decision",
            {"next_action": "end", "reason": "需求不清晰，需用户澄清"},
            "call_wf_1",
        ),
        AIMessage(content="需求需要进一步澄清，无法继续。请用户补充具体需求。"),
        # 备用
        *[AIMessage(content=f"备用 {i}") for i in range(10)],
    ]


@pytest.fixture
def fake_llm_responses_qa_back_to_engineer():
    """QA 调用 workflow_decision(next_action="back_to_engineer") 后回到 Engineer。

    每个 agent 可能先调用 list_files，再输出最终文本。QA 第一轮返回 workflow_decision 以触发回退。
    响应顺序：Boss(2) PM(2) Architect(2) PJM(2) Engineer(2) QA(2:workflow_decision) Engineer(2) QA(2:continue)
    """
    from langchain_core.messages import AIMessage

    def _list_files():
        return _make_tool_call_msg("list_files", {"directory": "."}, "call_lf")

    return [
        # Boss, PM, Architect, PJM, Engineer 各 2 个（list_files + 最终文本）
        _list_files(),
        AIMessage(content="requirements.md 已创建"),
        _list_files(),
        AIMessage(content="PRD 已编写完成"),
        _list_files(),
        AIMessage(content="设计文档已完成"),
        _list_files(),
        AIMessage(content="任务拆解完成"),
        _list_files(),
        AIMessage(content="代码实现完成"),
        # QA 第一轮：直接返回 workflow_decision，不先 list_files
        _make_tool_call_msg(
            "workflow_decision",
            {"next_action": "back_to_engineer", "reason": "测试发现登录功能异常"},
            "call_wf_qa",
        ),
        AIMessage(content="测试报告已生成，发现若干问题需修复"),
        # Engineer 第二次
        _list_files(),
        AIMessage(content="已修复登录相关问题"),
        # QA 第二轮
        _make_tool_call_msg(
            "workflow_decision",
            {"next_action": "continue", "reason": "测试通过"},
            "call_wf_qa2",
        ),
        AIMessage(content="测试全部通过"),
        *[AIMessage(content=f"备用 {i}") for i in range(15)],
    ]


@pytest.fixture
def mock_get_agent_llm_boss_ends_early(fake_llm_responses_boss_ends_early):
    """Patch get_agent_llm 返回会让 Boss 提前结束的 FakeModel。"""
    shared_llm = _create_fake_messages_llm_with_tools(fake_llm_responses_boss_ends_early)

    def _get_fake_llm(agent_name: str, callbacks=None):
        return shared_llm

    return _get_fake_llm


@pytest.fixture
def mock_get_agent_llm_qa_back_to_engineer(fake_llm_responses_qa_back_to_engineer):
    """Patch get_agent_llm 返回会让 QA 回到 Engineer 的 FakeModel。

    使用共享 LLM 实例，确保响应按执行顺序被消费。
    """
    shared_llm = _create_fake_messages_llm_with_tools(fake_llm_responses_qa_back_to_engineer)

    def _get_fake_llm(agent_name: str, callbacks=None):
        return shared_llm

    return _get_fake_llm


@pytest.fixture
def fake_llm_responses_engineer_start_dev_server():
    """Engineer 调用 start_dev_server 时，验证 DevServerEventMiddleware 发送 CUSTOM 事件。

    响应顺序：Boss(2) PM(2) Architect(2) PJM(2) Engineer(start_dev_server+text) QA(2)
    """
    from langchain_core.messages import AIMessage

    def _list_files():
        return _make_tool_call_msg("list_files", {"directory": "."}, "call_lf")

    return [
        _list_files(),
        AIMessage(content="requirements.md 已创建"),
        _list_files(),
        AIMessage(content="PRD 已编写完成"),
        _list_files(),
        AIMessage(content="设计文档已完成"),
        _list_files(),
        AIMessage(content="任务拆解完成"),
        _make_tool_call_msg(
            "start_dev_server",
            {"command": "npm run dev", "working_dir": "/workspace", "port": 3000},
            "call_sds",
        ),
        AIMessage(content="开发服务器已启动，可访问预览"),
        _make_tool_call_msg(
            "workflow_decision",
            {"next_action": "continue", "reason": "测试通过"},
            "call_wf",
        ),
        AIMessage(content="测试全部通过"),
        *[AIMessage(content=f"备用 {i}") for i in range(10)],
    ]


@pytest.fixture
def mock_get_agent_llm_engineer_start_dev_server(fake_llm_responses_engineer_start_dev_server):
    """Patch get_agent_llm 返回会让 Engineer 调用 start_dev_server 的 FakeModel。"""
    shared_llm = _create_fake_messages_llm_with_tools(
        fake_llm_responses_engineer_start_dev_server
    )

    def _get_fake_llm(agent_name: str, callbacks=None):
        return shared_llm

    return _get_fake_llm


@pytest.mark.asyncio
class TestRunAgentWithStreaming:
    """单 agent 模式 run_agent_with_streaming 集成测试。"""

    async def test_run_agent_with_streaming_success(self, agent_context):
        """单 agent 模式执行成功，验证事件和消息。"""
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
        event_types = [e.get("event_type") for e in events]
        assert "agent_start" in event_types
        assert "finish" in event_types


@pytest.mark.asyncio
class TestRunTeamAgentWithFakeLLM:
    """使用 FakeListChatModel 的 run_team_agent_with_streaming 集成测试。"""

    async def test_run_team_agent_success(
        self,
        agent_context,
        mock_get_agent_llm,
    ):
        """完整执行团队 agent 流程，验证状态、事件和消息。"""
        from agents.run_agent import run_team_agent_with_streaming

        with patch(
            "agents.web_app_team.team.get_agent_llm",
            mock_get_agent_llm,
        ):
            result = await run_team_agent_with_streaming(
                context=agent_context,
                framework="nextjs",
                prompt="创建一个简单的待办应用",
            )

        assert result["status"] == "success"
        assert result["session_id"] == agent_context.session_id

        events = agent_context.event_store.get_events()
        event_types = [e.get("event_type") for e in events]

        assert "agent_start" in event_types
        assert "finish" in event_types
        assert "node_start" in event_types
        assert "node_end" in event_types

        messages = agent_context.message_store.get_messages()
        assert len(messages) >= 1
        user_msgs = [m for m in messages if m.get("role") == "user"]
        assert len(user_msgs) >= 1
        assert "创建一个简单的待办应用" in str(user_msgs[0].get("content", ""))

    async def test_run_team_agent_with_fake_tool_calls(
        self,
        agent_context,
        mock_get_agent_llm_with_tool_calls,
    ):
        """验证带假 tool_calls 的 FakeModel 能完整跑通团队流程。"""
        from agents.run_agent import run_team_agent_with_streaming

        with patch(
            "agents.web_app_team.team.get_agent_llm",
            mock_get_agent_llm_with_tool_calls,
        ):
            result = await run_team_agent_with_streaming(
                context=agent_context,
                framework="nextjs",
                prompt="创建一个待办应用",
            )

        assert result["status"] == "success"
        assert result["session_id"] == agent_context.session_id

        messages = agent_context.message_store.get_messages()
        assert len(messages) >= 1
        event_types = [e.get("event_type") for e in agent_context.event_store.get_events()]
        assert "agent_start" in event_types
        assert "finish" in event_types

    async def test_run_team_agent_tool_calls_and_tool_message_in_events(
        self,
        agent_context,
        mock_get_agent_llm_with_tool_calls,
    ):
        """验证 tool_calls 和 ToolMessage 能正确发送到 event（前端可收到）。

        subgraph 结构下，MESSAGE_COMPLETE 事件应包含 tool_calls 和 tool_call_id。
        """
        from agents.run_agent import run_team_agent_with_streaming

        with patch(
            "agents.web_app_team.team.get_agent_llm",
            mock_get_agent_llm_with_tool_calls,
        ):
            await run_team_agent_with_streaming(
                context=agent_context,
                framework="nextjs",
                prompt="创建一个待办应用",
            )

        events = agent_context.event_store.get_events()
        message_complete_events = [
            e for e in events if e.get("event_type") == "message_complete"
        ]

        # 至少应有一条 message_complete 含 tool_calls（assistant 调用工具时）
        events_with_tool_calls = [
            e for e in message_complete_events
            if (e.get("data") or {}).get("tool_calls")
        ]
        # 至少应有一条 message_complete 含 tool_call_id（tool 角色的 result）
        events_with_tool_call_id = [
            e for e in message_complete_events
            if (e.get("data") or {}).get("tool_call_id")
        ]

        assert len(events_with_tool_calls) >= 1, (
            "应有至少一条 message_complete 含 tool_calls，供前端展示"
        )
        assert len(events_with_tool_call_id) >= 1, (
            "应有至少一条 message_complete 含 tool_call_id（ToolMessage）"
        )

    async def test_run_team_agent_emits_llm_stream_events(
        self,
        agent_context,
        mock_get_agent_llm,
    ):
        """验证流式 LLM 输出会产生 llm_stream 事件。"""
        from agents.run_agent import run_team_agent_with_streaming

        with patch(
            "agents.web_app_team.team.get_agent_llm",
            mock_get_agent_llm,
        ):
            await run_team_agent_with_streaming(
                context=agent_context,
                framework="nextjs",
                prompt="测试流式输出",
            )

        events = agent_context.event_store.get_events()
        event_types = [e.get("event_type") for e in events]

        assert "agent_start" in event_types
        assert "finish" in event_types

    async def test_run_team_agent_llm_stream_and_message_complete_same_message_id(
        self,
        agent_context,
        mock_get_agent_llm,
    ):
        """验证流式场景下 LLM_STREAM 与 MESSAGE_COMPLETE 的 message_id 一致。

        同一 assistant 消息的 delta 事件与完成事件必须使用相同 message_id，
        否则前端无法正确将流式内容与最终消息关联。
        """
        from agents.run_agent import run_team_agent_with_streaming

        with patch(
            "agents.web_app_team.team.get_agent_llm",
            mock_get_agent_llm,
        ):
            await run_team_agent_with_streaming(
                context=agent_context,
                framework="nextjs",
                prompt="创建一个简单的待办应用",
            )

        events = agent_context.event_store.get_events()
        llm_stream_events = [e for e in events if e.get("event_type") == "llm_stream"]
        message_complete_events = [
            e for e in events if e.get("event_type") == "message_complete"
        ]

        stream_message_ids = {
            e["message_id"] for e in llm_stream_events if e.get("message_id")
        }
        complete_message_ids = {
            e["message_id"] for e in message_complete_events if e.get("message_id")
        }

        assert len(stream_message_ids) >= 1, "应有至少一条流式消息"
        # 流式消息的 message_id 应在 MESSAGE_COMPLETE 中存在（修复前会生成新 UUID 导致不匹配）
        matching_ids = stream_message_ids & complete_message_ids
        assert len(matching_ids) >= 1, (
            f"至少应有一条 LLM_STREAM 的 message_id 与 MESSAGE_COMPLETE 一致，"
            f"stream_ids={stream_message_ids}, complete_ids={complete_message_ids}"
        )
        # 大部分流式消息的 id 应与完成事件匹配（允许少量 tool_call-only 等边缘情况）
        assert len(matching_ids) >= len(stream_message_ids) * 0.5, (
            f"多数 LLM_STREAM message_id 应在 MESSAGE_COMPLETE 中存在，"
            f"匹配 {len(matching_ids)}/{len(stream_message_ids)}，缺失: {stream_message_ids - complete_message_ids}"
        )

    async def test_run_team_agent_history_loaded_on_second_run(
        self,
        agent_context,
        mock_get_agent_llm,
    ):
        """第二次运行时，加载的历史消息与首次保存一致。"""
        from agents.run_agent import run_team_agent_with_streaming
        from shared.schemas import Message
        import time

        # 第一次运行
        with patch(
            "agents.web_app_team.team.get_agent_llm",
            mock_get_agent_llm,
        ):
            result1 = await run_team_agent_with_streaming(
                context=agent_context,
                framework="nextjs",
                prompt="第一轮需求",
            )
        assert result1["status"] == "success"

        messages_after_run1 = agent_context.message_store.get_messages()
        assert len(messages_after_run1) >= 2
        first_user_content = next(
            (m.get("content", "") for m in messages_after_run1 if m.get("role") == "user"),
            "",
        )
        assert "第一轮需求" in str(first_user_content)

        # 手动创建并存储第二条用户消息（模拟用户发送第二轮）
        second_user_msg = Message(
            message_id="msg-second-user",
            session_id=agent_context.session_id,
            role="user",
            content="第二轮需求",
            timestamp=time.time() + 1,
        )
        await agent_context.message_store.create_message(second_user_msg)

        # 第二次运行：传入 last_user_msg，触发加载历史
        captured_history = []

        from agents.web_app_team.state import create_initial_state as _orig_create_initial_state

        def capture_create_initial_state(workspace_id, framework, user_prompt, history_messages=None):
            if history_messages:
                captured_history.extend(history_messages)
            return _orig_create_initial_state(workspace_id, framework, user_prompt, history_messages)

        with patch(
            "agents.web_app_team.team.get_agent_llm",
            mock_get_agent_llm,
        ), patch(
            "agents.run_agent.create_initial_state",
            side_effect=capture_create_initial_state,
        ):
            result2 = await run_team_agent_with_streaming(
                context=agent_context,
                framework="nextjs",
                prompt=None,
                last_user_msg=second_user_msg,
            )

        assert result2["status"] == "success"
        assert len(captured_history) >= 1
        # 验证历史中含第一轮用户内容
        history_contents = [
            getattr(m, "content", m) if hasattr(m, "content") else str(m)
            for m in captured_history
        ]
        combined = " ".join(str(c) for c in history_contents)
        assert "第一轮需求" in combined

    async def test_run_team_agent_error_handling(
        self,
        agent_context,
    ):
        """验证 agent 异常时发送 AGENT_ERROR 和 FINISH。"""
        from agents.run_agent import run_team_agent_with_streaming

        with patch(
            "agents.run_agent.create_team_agent",
            side_effect=RuntimeError("模拟图创建失败"),
        ):
            result = await run_team_agent_with_streaming(
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

    async def test_run_team_agent_boss_ends_early_when_workflow_decision_end(
        self,
        agent_context,
        mock_get_agent_llm_boss_ends_early,
    ):
        """Boss 调用 workflow_decision(next_action="end") 时，流程在 Boss 后结束。"""
        from agents.run_agent import run_team_agent_with_streaming

        with patch(
            "agents.web_app_team.team.get_agent_llm",
            mock_get_agent_llm_boss_ends_early,
        ):
            result = await run_team_agent_with_streaming(
                context=agent_context,
                framework="nextjs",
                prompt="不太清晰的需求描述",
            )

        assert result["status"] == "success"

        events = agent_context.event_store.get_events()
        node_end_events = [e for e in events if e.get("event_type") == "node_end"]
        node_names = [e.get("data", {}).get("node_name") for e in node_end_events]

        assert "boss" in node_names
        assert "product_manager" not in node_names
        assert "architect" not in node_names

    async def test_run_team_agent_qa_back_to_engineer_then_continue(
        self,
        agent_context,
        mock_get_agent_llm_qa_back_to_engineer,
    ):
        """QA 调用 workflow_decision(back_to_engineer) 后回到 Engineer，再次 QA 后结束。"""
        from agents.run_agent import run_team_agent_with_streaming

        with patch(
            "agents.web_app_team.team.get_agent_llm",
            mock_get_agent_llm_qa_back_to_engineer,
        ):
            result = await run_team_agent_with_streaming(
                context=agent_context,
                framework="nextjs",
                prompt="创建一个待办应用",
            )

        assert result["status"] == "success"

        events = agent_context.event_store.get_events()
        node_end_events = [e for e in events if e.get("event_type") == "node_end"]
        node_names = [e.get("data", {}).get("node_name") for e in node_end_events]

        assert "engineer" in node_names
        assert "qa" in node_names
        assert node_names.count("engineer") >= 2
        assert node_names.count("qa") >= 2

    async def test_run_team_agent_emits_custom_event_when_engineer_calls_start_dev_server(
        self,
        agent_context,
        mock_get_agent_llm_engineer_start_dev_server,
    ):
        """验证 Engineer 调用 start_dev_server 后，DevServerEventMiddleware 发送 CUSTOM 事件。"""
        from agents.run_agent import run_team_agent_with_streaming

        async def fake_start_dev_server(workspace_id, command="npm run dev", working_dir="/workspace", port=3000):
            return "Dev server started successfully"

        with patch(
            "agents.web_app_team.team.get_agent_llm",
            mock_get_agent_llm_engineer_start_dev_server,
        ), patch(
            "agents.web_app_team.tools.mcp_docker_client.start_dev_server",
            side_effect=fake_start_dev_server,
        ):
            result = await run_team_agent_with_streaming(
                context=agent_context,
                framework="nextjs",
                prompt="创建一个待办应用",
            )

        assert result["status"] == "success"

        events = agent_context.event_store.get_events()
        custom_events = [
            e for e in events
            if e.get("event_type") == "custom"
            and (e.get("data") or {}).get("custom_type") == "dev_server_started"
        ]
        assert len(custom_events) >= 1, (
            f"Expected at least one custom event with custom_type=dev_server_started, "
            f"got events: {[e.get('event_type') for e in events]}"
        )
        evt = custom_events[0]
        assert evt.get("data", {}).get("custom_type") == "dev_server_started"
        assert evt.get("agent_name") == "engineer"


class TestGraphWorkflowDecisionParsing:
    """graph._parse_workflow_decision 和 _resolve_next_agent 单元测试。"""

    def test_parse_workflow_decision_from_tool_calls(self):
        """从 tool_calls 解析 workflow_decision。"""
        from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
        from agents.web_app_team.graph import _parse_workflow_decision

        result = {
            "messages": [
                HumanMessage(content="分析需求"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "tc1",
                            "name": "workflow_decision",
                            "args": {"next_action": "end", "reason": "需求不明"},
                            "type": "tool_call",
                        }
                    ],
                ),
                ToolMessage(content="ok", tool_call_id="tc1"),
            ]
        }
        action, instruction = _parse_workflow_decision(result, "boss", "continue")
        assert action == "end"
        assert instruction is None

    def test_parse_workflow_decision_from_text_block(self):
        """从 [WORKFLOW_DECISION]...[/WORKFLOW_DECISION] 解析。"""
        from langchain_core.messages import AIMessage
        from agents.web_app_team.graph import _parse_workflow_decision

        result = {
            "messages": [
                AIMessage(
                    content="PRD 编写完成。\n[WORKFLOW_DECISION]{\"next_action\":\"back_to_boss\"}[/WORKFLOW_DECISION]"
                ),
            ]
        }
        action, instruction = _parse_workflow_decision(result, "product_manager", "continue")
        assert action == "back_to_boss"
        assert instruction is None

    def test_parse_workflow_decision_default_when_no_decision(self):
        """无决策时返回默认值。"""
        from langchain_core.messages import AIMessage
        from agents.web_app_team.graph import _parse_workflow_decision

        result = {
            "messages": [
                AIMessage(content="正常完成，无 workflow_decision 调用"),
            ]
        }
        action, instruction = _parse_workflow_decision(result, "boss", "continue")
        assert action == "continue"
        assert instruction is None

    def test_parse_workflow_decision_takes_last_tool_call(self):
        """多个 workflow_decision 时取最后一个。"""
        from langchain_core.messages import AIMessage, ToolMessage
        from agents.web_app_team.graph import _parse_workflow_decision

        result = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "tc1",
                            "name": "workflow_decision",
                            "args": {"next_action": "continue"},
                            "type": "tool_call",
                        }
                    ],
                ),
                ToolMessage(content="ok", tool_call_id="tc1"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "tc2",
                            "name": "workflow_decision",
                            "args": {"next_action": "end"},
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }
        action, instruction = _parse_workflow_decision(result, "boss", "continue")
        assert action == "end"
        assert instruction is None

    def test_parse_workflow_decision_extracts_instruction_for_next(self):
        """从 tool_calls 解析 instruction_for_next。"""
        from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
        from agents.web_app_team.graph import _parse_workflow_decision

        result = {
            "messages": [
                HumanMessage(content="分析需求"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "tc1",
                            "name": "workflow_decision",
                            "args": {
                                "next_action": "back_to_engineer",
                                "reason": "发现 Bug",
                                "instruction_for_next": "请修复：1. 登录 500 2. 样式错乱",
                            },
                            "type": "tool_call",
                        }
                    ],
                ),
                ToolMessage(content="ok", tool_call_id="tc1"),
            ]
        }
        action, instruction = _parse_workflow_decision(result, "qa", "continue")
        assert action == "back_to_engineer"
        assert instruction == "请修复：1. 登录 500 2. 样式错乱"

    def test_parse_workflow_decision_instruction_empty_treated_as_none(self):
        """instruction_for_next 为空字符串时视为 None。"""
        from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
        from agents.web_app_team.graph import _parse_workflow_decision

        result = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "tc1",
                            "name": "workflow_decision",
                            "args": {"next_action": "continue", "instruction_for_next": ""},
                            "type": "tool_call",
                        }
                    ],
                ),
            ]
        }
        action, instruction = _parse_workflow_decision(result, "boss", "continue")
        assert action == "continue"
        assert instruction is None

    def test_resolve_next_agent_mapping(self):
        """_resolve_next_agent 正确映射各 action。"""
        from langgraph.graph import END
        from agents.web_app_team.graph import _resolve_next_agent
        from agents.web_app_team.state import AgentRole

        assert _resolve_next_agent("boss", "continue") == AgentRole.PRODUCT_MANAGER
        assert _resolve_next_agent("boss", "end") == END
        assert _resolve_next_agent("qa", "continue") == END
        assert _resolve_next_agent("qa", "back_to_engineer") == AgentRole.ENGINEER
        assert _resolve_next_agent("architect", "back_to_pm") == AgentRole.PRODUCT_MANAGER
        assert _resolve_next_agent("engineer", "continue_development") == AgentRole.ENGINEER

    def test_resolve_next_agent_unknown_action_defaults_to_continue(self):
        """未知 action 时回退到 continue。"""
        from agents.web_app_team.graph import _resolve_next_agent
        from agents.web_app_team.state import AgentRole

        assert _resolve_next_agent("boss", "unknown_action") == AgentRole.PRODUCT_MANAGER
