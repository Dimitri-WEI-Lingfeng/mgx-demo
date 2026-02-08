"""工作流决策工具。

供 agent 在需要结束、回退或继续时，向工作流编排发出下一步决策。
"""

from langchain.tools import tool


@tool
async def workflow_decision(
    next_action: str,
    reason: str = "",
    instruction_for_next: str = "",
) -> str:
    """向工作流编排发出下一步决策。

    在以下情况时应调用此工具：
    - 需求不清晰需用户澄清时：next_action="end"
    - 需求/PRD/设计文档有问题需回退时：next_action="back_to_boss" | "back_to_pm" | "back_to_architect"
    - 还有未完成任务需继续时：next_action="continue_development"
    - 测试失败需修复时：next_action="back_to_engineer"
    - 正常完成进入下一阶段时：next_action="continue"

    回退或循环时，务必传入 instruction_for_next 指定下一节点的具体任务，例如：
    - PM 回退 Boss 时：说明 requirements.md 需补充的内容
    - Architect 回退 PM 时：说明 PRD 需修改内容
    - QA 回退 Engineer 时：传入问题摘要和修复建议
    - Engineer 继续开发时：传入下一任务说明

    Args:
        next_action: 下一步动作。可选值：continue, end, back_to_boss, back_to_pm,
            back_to_architect, back_to_engineer, continue_development
        reason: 决策原因（可选）
        instruction_for_next: 下一节点的具体指令（回退/循环时务必传入，供下一节点作为任务输入）

    Returns:
        确认消息
    """
    return f"工作流决策已记录: {next_action}" + (f" ({reason})" if reason else "")
