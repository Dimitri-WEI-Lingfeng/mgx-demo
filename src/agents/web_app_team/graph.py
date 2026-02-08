"""LangGraph 工作流编排。

定义团队协作的工作流图。
"""

import json
import re
from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.language_models import BaseChatModel

from agents.web_app_team.state import TeamState, WorkflowStage, AgentRole


def _create_agent_subgraph(
    agent: CompiledStateGraph,
    node_name: str,
    default_prompt: str | None,
    stage: str | None,
    extra_return: dict | None = None,
) -> CompiledStateGraph:
    """创建以 agent 为 subgraph 节点的包装图，使 astream(subgraphs=True) 能流出 ToolMessage。

    Args:
        agent: create_agent 返回的图
        node_name: 节点名（用于 default_prompt 和日志）
        default_prompt: 默认指令（可含 {framework}），None 时用空字符串
        stage: current_stage 值，如 WorkflowStage.REQUIREMENT
        extra_return: 额外返回字段，如 {"prd_document": "prd.md"}

    Returns:
        编译后的包装图，可直接作为父图节点
    """
    extra_return = extra_return or {}
    default_prompt = default_prompt or ""

    async def prepare_node(state: TeamState) -> dict:
        instruction = state.get("next_agent_instruction") or default_prompt
        if "{framework}" in instruction:
            instruction = instruction.format(framework=state.get("framework", ""))
        # 仅用于 agent 内部处理，不发送到前端、不持久化
        msg = HumanMessage(content=instruction, additional_kwargs={"__internal__": True})
        return {"messages": [msg]}

    def parse_node(state: TeamState) -> dict:
        # agent 完成后，state 中已有 agent 产出的 messages
        result = {"messages": state["messages"]}
        next_action, next_instruction = _parse_workflow_decision(
            result, node_name, "continue"
        )
        next_agent = _resolve_next_agent(node_name, next_action)
        out = {
            "next_agent": next_agent,
            "next_agent_instruction": next_instruction,
            **extra_return,
        }
        if stage:
            out["current_stage"] = stage
        return out

    # 子图 state 与 TeamState 共享 messages 等 key
    sub_builder = StateGraph(TeamState)
    sub_builder.add_node("prepare", prepare_node)
    sub_builder.add_node("agent", agent)
    sub_builder.add_node("parse", parse_node)
    sub_builder.add_edge(START, "prepare")
    sub_builder.add_edge("prepare", "agent")
    sub_builder.add_edge("agent", "parse")
    sub_builder.add_edge("parse", END)
    return sub_builder.compile()

# intent 节点可路由到的 agent 列表（用于 LLM 返回解析）
INTENT_AGENTS = ("boss", "product_manager", "architect", "project_manager", "engineer", "qa")

INTENT_PROMPT = """你是一个意图分类器。根据用户最新消息和对话上下文，判断用户意图，返回应该路由到的 agent。

可选 agent 及含义：
- boss: 新需求、功能需求、产品需求、PRD、需求分析
- engineer: 启动开发服务、运行命令、写代码、修改代码、实现功能、部署
- qa: 运行测试、测试
- product_manager: 修改 PRD
- architect: 修改架构
- project_manager: 修改任务

用户最新消息：{last_user_content}

对话上下文（最近几条）：{context}

只返回一个词，必须是以下之一：boss, engineer, qa, product_manager, architect, project_manager
"""

# next_action -> next_agent 映射（按节点）
ACTION_TO_AGENT = {
    "boss": {
        "continue": AgentRole.PRODUCT_MANAGER,
        "end": END,
    },
    "product_manager": {
        "continue": AgentRole.ARCHITECT,
        "back_to_boss": AgentRole.BOSS,
        "end": END,
    },
    "architect": {
        "continue": AgentRole.PROJECT_MANAGER,
        "back_to_pm": AgentRole.PRODUCT_MANAGER,
        "end": END,
    },
    "project_manager": {
        "continue": AgentRole.ENGINEER,
        "back_to_architect": AgentRole.ARCHITECT,
        "back_to_pm": AgentRole.PRODUCT_MANAGER,
        "end": END,
    },
    "engineer": {
        "continue": AgentRole.QA,
        "continue_development": AgentRole.ENGINEER,
        "back_to_architect": AgentRole.ARCHITECT,
        "end": END,
    },
    "qa": {
        "continue": END,
        "back_to_engineer": AgentRole.ENGINEER,
        "end": END,
    },
}


def _parse_workflow_decision(result: dict, current_node: str, default_action: str) -> tuple[str, str | None]:
    """从 agent 结果中解析 next_action 和 instruction_for_next。

    优先从 tool_calls 获取，其次从文本解析 [WORKFLOW_DECISION]{...}[/WORKFLOW_DECISION]。

    Args:
        result: agent.invoke() 的返回值
        current_node: 当前节点名
        default_action: 解析失败时的默认动作

    Returns:
        (next_action, instruction_for_next) 元组，instruction_for_next 可为 None
    """
    messages = result.get("messages", [])
    next_action_from_tool = None
    instruction_from_tool = None

    for msg in reversed(messages):
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {})
                if name == "workflow_decision" and isinstance(args, dict):
                    action = args.get("next_action")
                    if action:
                        next_action_from_tool = action
                        instruction_from_tool = args.get("instruction_for_next") or None
                        if instruction_from_tool is not None and instruction_from_tool.strip() == "":
                            instruction_from_tool = None
                        break
        if next_action_from_tool is not None:
            break

    if next_action_from_tool:
        return (next_action_from_tool, instruction_from_tool)

    # 尝试从最后一条 AIMessage 的 content 解析
    for msg in reversed(messages):
        content = getattr(msg, "content", None)
        if isinstance(content, str) and content:
            match = re.search(
                r"\[WORKFLOW_DECISION\](.*?)\[/WORKFLOW_DECISION\]",
                content,
                re.DOTALL,
            )
            if match:
                try:
                    data = json.loads(match.group(1).strip())
                    action = data.get("next_action")
                    if action:
                        instruction = data.get("instruction_for_next") or None
                        if instruction is not None and instruction.strip() == "":
                            instruction = None
                        return (action, instruction)
                except (json.JSONDecodeError, ValueError):
                    pass

    return (default_action, None)


def _resolve_next_agent(current_node: str, next_action: str) -> str:
    """将 next_action 映射为 next_agent。"""
    mapping = ACTION_TO_AGENT.get(current_node, {})
    return mapping.get(next_action, mapping.get("continue", END))


def _get_last_user_content(messages: list) -> str:
    """从 messages 中提取最后一条用户消息内容。"""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            content = getattr(msg, "content", None)
            return content if isinstance(content, str) else ""
    return ""


def _parse_intent_from_llm_response(response: str) -> str:
    """从 LLM 返回的文本中解析 intent agent。"""
    s = (response or "").strip().lower()
    for agent in INTENT_AGENTS:
        if agent in s:
            return agent
    return "boss"


# 各节点默认 prompt（首次进入时使用，循环回退时由上一节点通过 instruction_for_next 覆盖）
DEFAULT_PROMPTS = {
    "boss": "请分析用户需求并创建 requirements.md 文档。目标框架：{framework}",
    "product_manager": "请阅读 requirements.md 并编写详细的 PRD 文档（prd.md）",
    "architect": "请阅读 prd.md 并设计技术架构，生成 design.md。目标框架：{framework}",
    "project_manager": "请阅读 prd.md 和 design.md，将需求拆解为具体的开发任务，生成 tasks.md",
    "engineer": "请根据 design.md 和 tasks.md 实现代码。目标框架：{framework}。一次完成一个任务，测试后再继续。",
    "qa": "请编写测试用例并执行测试，生成测试报告 test_report.md",
}


def create_team_graph(
    boss_agent: CompiledStateGraph,
    pm_agent: CompiledStateGraph,
    architect_agent: CompiledStateGraph,
    pjm_agent: CompiledStateGraph,
    engineer_agent: CompiledStateGraph,
    qa_agent: CompiledStateGraph,
    intent_llm: BaseChatModel | None = None,
) -> CompiledStateGraph:
    """创建团队工作流图。
    
    Args:
        boss_agent: Boss Agent graph
        pm_agent: Product Manager Agent graph
        architect_agent: Architect Agent graph
        pjm_agent: Project Manager Agent graph
        engineer_agent: Engineer Agent graph
        qa_agent: QA Agent graph
        intent_llm: 用于 intent 节点判断用户意图的 LLM；若为 None 则 messages 非空时默认 boss
    
    Returns:
        编译后的工作流图
    """
    
    # intent 节点：选择首个 agent
    # messages 为空（无 AIMessage，即新会话）时强制 boss；否则通过 LLM 判断
    async def intent_node(state: TeamState) -> TeamState:
        """Intent 节点：根据 messages 和用户意图选择首个 agent。"""
        print("\n=== Intent 节点：选择首个 Agent ===")
        messages = list(state.get("messages", []))
        
        # 无 AIMessage = 新会话，强制 boss
        has_agent_output = any(
            isinstance(m, AIMessage) for m in messages
        )
        if not has_agent_output:
            print("  新会话，路由到 Boss")
            return {"next_agent": AgentRole.BOSS, "next_agent_instruction": None}
        
        # 有历史，通过 LLM 判断 intent
        if intent_llm is None:
            print("  无 intent_llm，默认路由到 Boss")
            return {"next_agent": AgentRole.BOSS, "next_agent_instruction": None}
        
        last_user_content = _get_last_user_content(messages)
        if not last_user_content:
            print("  无法提取用户消息，默认路由到 Boss")
            return {"next_agent": AgentRole.BOSS, "next_agent_instruction": None}
        
        # 取最近几条作为上下文
        context_msgs = messages[-6:] if len(messages) > 6 else messages
        context = "\n".join(
            f"{'用户' if isinstance(m, HumanMessage) else '助手'}: {getattr(m, 'content', '')[:200]}"
            for m in context_msgs
        )
        
        try:
            prompt = INTENT_PROMPT.format(
                last_user_content=last_user_content[:500],
                context=context[:800],
            )
            response = await intent_llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content if hasattr(response, "content") else ""
            if isinstance(content, list):
                content = "".join(
                    c.get("text", "") if isinstance(c, dict) else str(c)
                    for c in content
                )
            else:
                content = str(content) if content else ""
            intent_agent = _parse_intent_from_llm_response(content)
            print(f"  LLM 判断 intent -> {intent_agent}")
            next_agent = getattr(AgentRole, intent_agent.upper(), AgentRole.BOSS)
            return {"next_agent": next_agent, "next_agent_instruction": None}
        except Exception as e:
            print(f"  Intent LLM 调用失败: {e}，默认路由到 Boss")
            return {"next_agent": AgentRole.BOSS, "next_agent_instruction": None}
    
    # 将各 agent 包装为 subgraph 节点，使 astream(subgraphs=True) 能流出 ToolMessage
    boss_subgraph = _create_agent_subgraph(
        boss_agent,
        "boss",
        DEFAULT_PROMPTS["boss"],
        WorkflowStage.REQUIREMENT,
        extra_return={},
    )
    pm_subgraph = _create_agent_subgraph(
        pm_agent,
        "product_manager",
        DEFAULT_PROMPTS["product_manager"],
        WorkflowStage.DESIGN,
        extra_return={"prd_document": "prd.md"},
    )
    architect_subgraph = _create_agent_subgraph(
        architect_agent,
        "architect",
        DEFAULT_PROMPTS["architect"],
        None,
        extra_return={"design_document": "design.md"},
    )
    pjm_subgraph = _create_agent_subgraph(
        pjm_agent,
        "project_manager",
        DEFAULT_PROMPTS["project_manager"],
        None,
        extra_return={"tasks": []},
    )
    engineer_subgraph = _create_agent_subgraph(
        engineer_agent,
        "engineer",
        DEFAULT_PROMPTS["engineer"],
        WorkflowStage.DEVELOPMENT,
        extra_return={"code_changes": []},
    )
    qa_subgraph = _create_agent_subgraph(
        qa_agent,
        "qa",
        DEFAULT_PROMPTS["qa"],
        WorkflowStage.TESTING,
        extra_return={"test_results": {}},
    )
    
    # 路由函数：决定下一个执行的节点
    def router(state: TeamState) -> Literal["boss", "product_manager", "architect", "project_manager", "engineer", "qa", END]:
        """根据 next_agent 决定下一个节点。"""
        next_agent = state.get("next_agent")
        
        route_map = {
            AgentRole.BOSS: "boss",
            AgentRole.PRODUCT_MANAGER: "product_manager",
            AgentRole.ARCHITECT: "architect",
            AgentRole.PROJECT_MANAGER: "project_manager",
            AgentRole.ENGINEER: "engineer",
            AgentRole.QA: "qa",
            END: END,
        }
        
        return route_map.get(next_agent, END)
    
    # 构建图
    workflow = StateGraph(TeamState)
    
    # 添加节点（boss/pm/architect 等为 subgraph，使 stream 能流出 ToolMessage）
    workflow.add_node("intent", intent_node)
    workflow.add_node("boss", boss_subgraph)
    workflow.add_node("product_manager", pm_subgraph)
    workflow.add_node("architect", architect_subgraph)
    workflow.add_node("project_manager", pjm_subgraph)
    workflow.add_node("engineer", engineer_subgraph)
    workflow.add_node("qa", qa_subgraph)
    
    # 设置入口点：intent 优先
    workflow.set_entry_point("intent")
    
    # intent 节点的条件边：根据 next_agent 路由
    workflow.add_conditional_edges(
        "intent",
        router,
        {
            "boss": "boss",
            "product_manager": "product_manager",
            "architect": "architect",
            "project_manager": "project_manager",
            "engineer": "engineer",
            "qa": "qa",
            END: END,
        },
    )
    
    # 添加条件边（使用 router 函数）
    workflow.add_conditional_edges(
        "boss",
        router,
        {
            "product_manager": "product_manager",
            END: END,
        }
    )
    
    workflow.add_conditional_edges(
        "product_manager",
        router,
        {
            "architect": "architect",
            "boss": "boss",
            END: END,
        }
    )
    
    workflow.add_conditional_edges(
        "architect",
        router,
        {
            "project_manager": "project_manager",
            "product_manager": "product_manager",  # 可能需要修改 PRD
            END: END,
        }
    )
    
    workflow.add_conditional_edges(
        "project_manager",
        router,
        {
            "engineer": "engineer",
            "architect": "architect",
            "product_manager": "product_manager",
            END: END,
        }
    )
    
    workflow.add_conditional_edges(
        "engineer",
        router,
        {
            "qa": "qa",
            "engineer": "engineer",
            "architect": "architect",
            END: END,
        }
    )
    
    workflow.add_conditional_edges(
        "qa",
        router,
        {
            "engineer": "engineer",  # 发现问题，回到 Engineer 修复
            END: END,
        }
    )
    
    # 编译图
    return workflow.compile()
