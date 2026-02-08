"""各个角色的 Agent 实现。"""

from agents.web_app_team.agents.boss import create_boss_agent
from agents.web_app_team.agents.product_manager import create_pm_agent
from agents.web_app_team.agents.architect import create_architect_agent
from agents.web_app_team.agents.project_manager import create_pjm_agent
from agents.web_app_team.agents.engineer import create_engineer_agent
from agents.web_app_team.agents.qa import create_qa_agent

__all__ = [
    "create_boss_agent",
    "create_pm_agent",
    "create_architect_agent",
    "create_pjm_agent",
    "create_engineer_agent",
    "create_qa_agent",
]
