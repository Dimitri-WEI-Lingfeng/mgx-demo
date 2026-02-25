# 异步事件驱动 Multi-Agent 系统

**日期**: 2026-02-25

## 概述

将原有的 LangGraph 顺序工作流改造为异步事件驱动架构。每个 Agent 订阅多个不同类型的事件，可以并发执行。

## 新增文件

```
src/agents/web_app_team/event_driven/
├── __init__.py           # 模块入口
├── team_events.py        # TeamEventType 枚举 + TeamEvent 数据类
├── event_bus.py          # EventBus 异步发布/订阅核心
├── shared_state.py       # SharedArtifactState 线程安全共享状态
├── base_agent.py         # EventDrivenAgent 抽象基类
├── agents.py             # 各角色 Agent 的事件驱动实现
├── orchestrator.py       # EventDrivenOrchestrator 编排器
└── team_factory.py       # 事件驱动团队工厂函数
```

## 架构设计

### 事件类型 (TeamEventType)

| 事件类型 | 说明 | 发布者 | 订阅者 |
|---|---|---|---|
| `USER_REQUEST` | 用户需求输入 | 用户/系统 | Boss |
| `REQUIREMENTS_CREATED` | 需求文档创建 | Boss | PM |
| `PRD_UPDATED` | PRD 文档更新 | PM | Architect |
| `DESIGN_UPDATED` | 架构设计更新 | Architect | PJM |
| `TASKS_CREATED` | 任务列表创建 | PJM | Engineer |
| `CODE_WRITTEN` | 代码实现完成 | Engineer | QA |
| `CODE_SUMMARY` | 代码变更摘要 | Engineer | （观测用）|
| `TEST_REPORT` | 测试报告 | QA | （观测用）|
| `TEST_PASSED` | 测试通过 | QA | Orchestrator |
| `TEST_FAILED` | 测试失败 | QA | Engineer |
| `SEND_TO_AGENT` | 定向发送 | 任意 | 指定 target |
| `REVIEW_FEEDBACK` | 审查反馈 | 任意 | PM/Architect/Engineer |

### EventBus

- 异步 pub/sub，事件发布后**并发**调用所有订阅者
- 订阅者可返回新事件，实现**级联触发**
- `SEND_TO_AGENT` 事件只路由到 `target_agent`
- 内置级联深度限制（默认 20），防止无限递归
- 支持全局回调（用于 SSE 推送等旁路观测）

### 并发执行

```
USER_REQUEST
    └─→ Boss (并发处理)
         └─→ REQUIREMENTS_CREATED
              └─→ PM
                   └─→ PRD_UPDATED
                        └─→ Architect
                             └─→ DESIGN_UPDATED
                                  └─→ PJM
                                       └─→ TASKS_CREATED
                                            └─→ Engineer
                                                 └─→ CODE_WRITTEN
                                                      └─→ QA
                                                           ├─→ TEST_PASSED → 完成
                                                           └─→ TEST_FAILED → Engineer（修复）
```

未来可扩展为真正并发：例如 Architect 和 PM 同时订阅某些事件，并行工作。

## 使用方式

### 命令行

```bash
# 事件驱动模式（新）
uv run python src/agents/run_agent_local.py --mode event_driven --prompt "创建一个 todo app"

# 顺序模式（原有，默认）
uv run python src/agents/run_agent_local.py --mode team --prompt "创建一个 todo app"
```

### 环境变量

```bash
# 在容器中使用事件驱动模式
AGENT_MODE=event_driven
```

### 代码调用

```python
from agents.agent_factory import create_event_driven_team_agent

orchestrator = create_event_driven_team_agent(
    framework="nextjs",
    workspace_id="ws-123",
)

# 注册全局事件回调（用于 SSE 推送）
orchestrator.on_team_event(my_callback)

result = await orchestrator.run(prompt="创建一个 todo app")
```

## 兼容性

- **完全向后兼容**：原有的 `team` 模式不受影响
- `AGENT_MODE=team`（默认）使用原有 LangGraph 顺序工作流
- `AGENT_MODE=event_driven` 使用新的事件驱动架构
- 两种模式复用相同的 Agent 创建逻辑（prompts、tools、middleware）

## 测试

新增 22 个测试用例覆盖：
- `TestTeamEvent`: 事件数据类
- `TestEventBus`: 发布/订阅、并发执行、级联事件、深度限制、路由
- `TestSharedArtifactState`: 线程安全状态管理
- `TestEventDrivenOrchestrator`: 完整工作流、错误处理、超时、并发
