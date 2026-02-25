"""各角色 Agent 的事件驱动实现。

每个 Agent 订阅特定事件，处理后发布新事件，实现并发协作。
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from agents.web_app_team.event_driven.base_agent import EventDrivenAgent
from agents.web_app_team.event_driven.team_events import TeamEventType, TeamEvent


class BossAgent(EventDrivenAgent):
    """Boss Agent - 需求提炼。

    订阅: USER_REQUEST, REVIEW_FEEDBACK(target=boss)
    发布: REQUIREMENTS_CREATED
    """

    def subscribed_events(self) -> list[TeamEventType]:
        return [TeamEventType.USER_REQUEST, TeamEventType.SEND_TO_AGENT]

    async def handle_event(self, event: TeamEvent) -> list[TeamEvent] | None:
        if event.event_type == TeamEventType.SEND_TO_AGENT and event.target_agent != self.name:
            return None

        prompt = event.payload.get("prompt") or event.payload.get("instruction", "")
        framework = await self.shared_state.get("framework", "nextjs")
        full_prompt = f"请分析用户需求并创建 requirements.md 文档。目标框架：{framework}\n\n用户需求：{prompt}"

        result = await self._invoke_agent(full_prompt)
        content = self._extract_last_ai_content(result)

        await self.shared_state.update(requirements_doc="requirements.md")

        return [
            self._make_event(
                TeamEventType.REQUIREMENTS_CREATED,
                payload={"content": content, "file": "requirements.md"},
            )
        ]


class ProductManagerAgent(EventDrivenAgent):
    """PM Agent - PRD 编写。

    订阅: REQUIREMENTS_CREATED, SEND_TO_AGENT, REVIEW_FEEDBACK
    发布: PRD_UPDATED
    """

    def subscribed_events(self) -> list[TeamEventType]:
        return [
            TeamEventType.REQUIREMENTS_CREATED,
            TeamEventType.SEND_TO_AGENT,
            TeamEventType.REVIEW_FEEDBACK,
        ]

    async def handle_event(self, event: TeamEvent) -> list[TeamEvent] | None:
        if event.event_type == TeamEventType.SEND_TO_AGENT and event.target_agent != self.name:
            return None
        if event.event_type == TeamEventType.REVIEW_FEEDBACK and event.target_agent != self.name:
            return None

        if event.event_type == TeamEventType.REQUIREMENTS_CREATED:
            prompt = "请阅读 requirements.md 并编写详细的 PRD 文档（prd.md）"
        elif event.event_type == TeamEventType.REVIEW_FEEDBACK:
            feedback = event.payload.get("feedback", "")
            prompt = f"请根据反馈修改 PRD 文档（prd.md）：\n{feedback}"
        else:
            prompt = event.payload.get("instruction", "请编写或更新 PRD 文档")

        result = await self._invoke_agent(prompt)
        content = self._extract_last_ai_content(result)
        await self.shared_state.update(prd_doc="prd.md")

        return [
            self._make_event(
                TeamEventType.PRD_UPDATED,
                payload={"content": content, "file": "prd.md"},
            )
        ]


class ArchitectAgent(EventDrivenAgent):
    """Architect Agent - 架构设计。

    订阅: PRD_UPDATED, SEND_TO_AGENT, REVIEW_FEEDBACK
    发布: DESIGN_UPDATED
    """

    def subscribed_events(self) -> list[TeamEventType]:
        return [
            TeamEventType.PRD_UPDATED,
            TeamEventType.SEND_TO_AGENT,
            TeamEventType.REVIEW_FEEDBACK,
        ]

    async def handle_event(self, event: TeamEvent) -> list[TeamEvent] | None:
        if event.event_type == TeamEventType.SEND_TO_AGENT and event.target_agent != self.name:
            return None
        if event.event_type == TeamEventType.REVIEW_FEEDBACK and event.target_agent != self.name:
            return None

        framework = await self.shared_state.get("framework", "nextjs")

        if event.event_type == TeamEventType.PRD_UPDATED:
            prompt = f"请阅读 prd.md 并设计技术架构，生成 design.md。目标框架：{framework}"
        elif event.event_type == TeamEventType.REVIEW_FEEDBACK:
            feedback = event.payload.get("feedback", "")
            prompt = f"请根据反馈修改架构设计（design.md）：\n{feedback}"
        else:
            prompt = event.payload.get("instruction", "请设计或更新技术架构")

        result = await self._invoke_agent(prompt)
        content = self._extract_last_ai_content(result)
        await self.shared_state.update(design_doc="design.md")

        return [
            self._make_event(
                TeamEventType.DESIGN_UPDATED,
                payload={"content": content, "file": "design.md"},
            )
        ]


class ProjectManagerAgent(EventDrivenAgent):
    """PJM Agent - 任务拆解。

    订阅: DESIGN_UPDATED, SEND_TO_AGENT
    发布: TASKS_CREATED

    注意：同时订阅 PRD_UPDATED 和 DESIGN_UPDATED，
    但只在 DESIGN_UPDATED 后执行（需要两者都就绪）。
    """

    def subscribed_events(self) -> list[TeamEventType]:
        return [
            TeamEventType.DESIGN_UPDATED,
            TeamEventType.SEND_TO_AGENT,
        ]

    async def handle_event(self, event: TeamEvent) -> list[TeamEvent] | None:
        if event.event_type == TeamEventType.SEND_TO_AGENT and event.target_agent != self.name:
            return None

        if event.event_type == TeamEventType.DESIGN_UPDATED:
            prompt = "请阅读 prd.md 和 design.md，将需求拆解为具体的开发任务，生成 tasks.md"
        else:
            prompt = event.payload.get("instruction", "请拆解任务")

        result = await self._invoke_agent(prompt)
        content = self._extract_last_ai_content(result)
        await self.shared_state.update(tasks_doc="tasks.md")

        return [
            self._make_event(
                TeamEventType.TASKS_CREATED,
                payload={"content": content, "file": "tasks.md"},
            )
        ]


class EngineerAgent(EventDrivenAgent):
    """Engineer Agent - 代码实现。

    订阅: TASKS_CREATED, SEND_TO_AGENT, TEST_FAILED, REVIEW_FEEDBACK
    发布: CODE_WRITTEN, CODE_SUMMARY
    """

    def subscribed_events(self) -> list[TeamEventType]:
        return [
            TeamEventType.TASKS_CREATED,
            TeamEventType.SEND_TO_AGENT,
            TeamEventType.TEST_FAILED,
            TeamEventType.REVIEW_FEEDBACK,
        ]

    async def handle_event(self, event: TeamEvent) -> list[TeamEvent] | None:
        if event.event_type == TeamEventType.SEND_TO_AGENT and event.target_agent != self.name:
            return None
        if event.event_type == TeamEventType.REVIEW_FEEDBACK and event.target_agent != self.name:
            return None

        framework = await self.shared_state.get("framework", "nextjs")

        if event.event_type == TeamEventType.TASKS_CREATED:
            prompt = f"请根据 design.md 和 tasks.md 实现代码。目标框架：{framework}。一次完成一个任务，测试后再继续。"
        elif event.event_type == TeamEventType.TEST_FAILED:
            failures = event.payload.get("failures", "")
            prompt = f"测试失败，请修复以下问题：\n{failures}"
        elif event.event_type == TeamEventType.REVIEW_FEEDBACK:
            feedback = event.payload.get("feedback", "")
            prompt = f"请根据反馈修改代码：\n{feedback}"
        else:
            prompt = event.payload.get("instruction", "请实现代码")

        result = await self._invoke_agent(prompt)
        content = self._extract_last_ai_content(result)

        events: list[TeamEvent] = [
            self._make_event(
                TeamEventType.CODE_WRITTEN,
                payload={"content": content},
            ),
        ]

        if content:
            events.append(
                self._make_event(
                    TeamEventType.CODE_SUMMARY,
                    payload={"summary": content[:500]},
                )
            )

        return events


class QAAgent(EventDrivenAgent):
    """QA Agent - 测试验证。

    订阅: CODE_WRITTEN, CODE_SUMMARY, SEND_TO_AGENT
    发布: TEST_REPORT, TEST_PASSED / TEST_FAILED
    """

    def subscribed_events(self) -> list[TeamEventType]:
        return [
            TeamEventType.CODE_WRITTEN,
            TeamEventType.SEND_TO_AGENT,
        ]

    async def handle_event(self, event: TeamEvent) -> list[TeamEvent] | None:
        if event.event_type == TeamEventType.SEND_TO_AGENT and event.target_agent != self.name:
            return None

        prompt = "请编写测试用例并执行测试，生成测试报告 test_report.md"

        result = await self._invoke_agent(prompt)
        content = self._extract_last_ai_content(result)
        await self.shared_state.update(test_report="test_report.md")

        events: list[TeamEvent] = [
            self._make_event(
                TeamEventType.TEST_REPORT,
                payload={"content": content, "file": "test_report.md"},
            ),
        ]

        lower = content.lower()
        has_failure = (
            ("test failed" in lower or "tests failed" in lower or "failure" in lower)
            and "passed" not in lower
        ) or ("error" in lower and "no error" not in lower and "passed" not in lower)
        if has_failure:
            events.append(
                self._make_event(
                    TeamEventType.TEST_FAILED,
                    payload={"failures": content[:1000]},
                )
            )
        else:
            events.append(
                self._make_event(
                    TeamEventType.TEST_PASSED,
                    payload={"report": content[:500]},
                )
            )

        return events
