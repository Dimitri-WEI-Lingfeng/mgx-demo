# 动态工作流路由

日期：2026-02-07

## 概述

完善 `graph.py` 中的工作流编排，使每个节点的 `next_agent` 根据 agent 实际输出动态决定，而非硬编码。

## 变更内容

### 1. 新增 workflow_decision 工具

- 文件：`src/agents/web_app_team/tools/workflow_decision.py`
- agent 在需要结束、回退或继续时调用此工具，传入 `next_action` 和可选 `reason`

### 2. 所有 6 个 agent 增加 workflow_decision 工具

- Boss、PM、Architect、PJM、Engineer、QA 均增加该工具

### 3. 更新各 agent 的 prompt

- 每个 prompt 增加「工作流决策」说明，指导 agent 在何种情况下调用 `workflow_decision` 及传参

### 4. 决策解析与路由逻辑

- `_parse_workflow_decision`: 从 agent 结果中解析 next_action，优先从 tool_calls 获取，其次从文本 `[WORKFLOW_DECISION]{...}[/WORKFLOW_DECISION]` 解析
- `_resolve_next_agent`: 将 next_action 映射为 next_agent
- `ACTION_TO_AGENT`: 各节点支持的动作及对应下一节点

### 5. 各节点支持的决策

| 节点 | next_action | 下一节点 |
|------|-------------|----------|
| Boss | continue | PM |
| Boss | end | END |
| PM | continue | Architect |
| PM | back_to_boss | Boss |
| PM | end | END |
| Architect | continue | PJM |
| Architect | back_to_pm | PM |
| Architect | end | END |
| PJM | continue | Engineer |
| PJM | back_to_architect | Architect |
| PJM | back_to_pm | PM |
| PJM | end | END |
| Engineer | continue | QA |
| Engineer | continue_development | Engineer |
| Engineer | back_to_architect | Architect |
| Engineer | end | END |
| QA | continue | END |
| QA | back_to_engineer | Engineer |
| QA | end | END |

### 6. 条件边完整性

补齐所有回退边，使 router 能正确路由到 boss、product_manager、architect、engineer、END。

## 涉及文件

- `src/agents/web_app_team/tools/workflow_decision.py` (新建)
- `src/agents/web_app_team/tools/__init__.py`
- `src/agents/web_app_team/graph.py`
- `src/agents/web_app_team/prompts/*.py` (6 个)
- `src/agents/web_app_team/agents/*.py` (6 个)

## 验收

- 集成测试 `tests/test_run_agent_integration.py` 全部通过
- 未调用 workflow_decision 时使用默认 continue，流程按原逻辑执行
