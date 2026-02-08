"""团队共享状态定义。

定义了团队在协作过程中共享的状态结构。
"""

from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
import operator


class TeamState(TypedDict):
    """团队共享状态。
    
    Attributes:
        messages: 消息历史（使用 operator.add 累加）
        current_stage: 当前工作阶段
        workspace_id: Workspace ID
        framework: 目标框架（nextjs, fastapi-vite）
        prd_document: PRD 文档内容
        design_document: 设计文档内容
        tasks: 任务列表
        code_changes: 代码变更记录
        test_results: 测试结果
        next_agent: 下一个要执行的 agent
        next_agent_instruction: 上一节点通过 workflow_decision 为下一节点指定的指令（回退/循环时使用）
    """
    
    # 消息历史 - 使用 operator.add 来累加消息
    messages: Annotated[Sequence[BaseMessage], operator.add]
    
    # 当前工作阶段
    current_stage: str  # requirement, design, development, testing, completed
    
    # 基础配置
    workspace_id: str
    framework: str
    
    # 文档和产物
    prd_document: str | None
    design_document: str | None
    tasks: list[dict] | None
    code_changes: list[dict] | None
    test_results: dict | None
    
    # 流程控制
    next_agent: str | None  # boss, pm, architect, pjm, engineer, qa, END
    next_agent_instruction: str | None  # 上一节点为下一节点指定的指令


class WorkflowStage:
    """工作流阶段常量。"""
    
    REQUIREMENT = "requirement"  # 需求分析
    DESIGN = "design"  # 架构设计
    DEVELOPMENT = "development"  # 代码开发
    TESTING = "testing"  # 测试验证
    COMPLETED = "completed"  # 完成


class AgentRole:
    """Agent 角色常量。"""
    
    BOSS = "boss"
    PRODUCT_MANAGER = "product_manager"
    ARCHITECT = "architect"
    PROJECT_MANAGER = "project_manager"
    ENGINEER = "engineer"
    QA = "qa"


def create_initial_state(
    workspace_id: str,
    framework: str,
    user_prompt: str,
    history_messages: list[BaseMessage] | None = None,
) -> TeamState:
    """创建初始状态。
    
    Args:
        workspace_id: Workspace ID
        framework: 目标框架
        user_prompt: 用户输入的需求描述
        history_messages: 历史消息列表（可选）
    
    Returns:
        初始化的团队状态
    """
    from langchain_core.messages import HumanMessage
    
    # 构建消息列表：历史消息 + 当前用户消息
    messages = []
    if history_messages:
        messages.extend(history_messages)
    messages.append(HumanMessage(content=user_prompt))
    
    return {
        "messages": messages,
        "current_stage": WorkflowStage.REQUIREMENT,
        "workspace_id": workspace_id,
        "framework": framework,
        "prd_document": None,
        "design_document": None,
        "tasks": None,
        "code_changes": None,
        "test_results": None,
        "next_agent": AgentRole.BOSS,
        "next_agent_instruction": None,
    }
