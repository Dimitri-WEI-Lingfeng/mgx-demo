# CLI UI 快速开始指南

## 概述

Agent CLI UI 是一个专门设计用于美化打印 agent stream events 的命令行界面工具。它提供了漂亮的彩色输出、emoji 图标、表格展示和实时统计功能。

## 快速开始

### 1. 安装依赖

```bash
cd /Users/feng/codes/mgx-demo
uv add rich
```

### 2. 运行演示

查看所有 UI 功能的演示：

```bash
uv run src/agents/demo_cli_ui.py
```

### 3. 在实际 Agent 中使用

```bash
# 使用美化的 Rich UI（默认，推荐）
uv run src/agents/run_agent_local.py --prompt "创建一个待办事项应用"

# 使用详细模式（显示工具参数和元数据）
uv run src/agents/run_agent_local.py --prompt "创建一个待办事项应用" --verbose

# 使用简单 UI（轻量级）
uv run src/agents/run_agent_local.py --prompt "创建一个待办事项应用" --ui simple

# 不使用 UI（原始输出，适合日志记录）
uv run src/agents/run_agent_local.py --prompt "创建一个待办事项应用" --ui none
```

## 主要功能

### 🎨 美化的事件展示

- **彩色输出**: 不同事件类型使用不同颜色
- **Emoji 图标**: 每个事件类型和 Agent 角色都有专属 emoji
- **表格和面板**: 结构化展示信息
- **实时流式输出**: LLM 生成内容实时显示

### 👥 Agent 角色识别

| Agent | Emoji | 描述 |
|-------|-------|------|
| Boss | 👔 | 需求提炼 |
| Product Manager | 📋 | PRD 编写 |
| Architect | 🏗️ | 技术设计 |
| Project Manager | 📊 | 任务拆解 |
| Engineer | 💻 | 代码实现 |
| QA | 🧪 | 测试验证 |

### 📊 事件类型

| 事件类型 | Emoji | 说明 |
|---------|-------|------|
| agent_start | ▶️ | Agent 开始工作 |
| agent_end | ✅ | Agent 完成工作 |
| tool_start | 🔧 | 工具调用开始 |
| tool_end | ✔️ | 工具调用完成 |
| llm_stream | 💬 | LLM 流式输出 |
| message_complete | 📄 | 完整消息 |
| finish | 🎉 | 工作流完成 |

### 📈 自动统计

- **Agent 活动统计**: 每个 Agent 的执行次数和工具调用次数
- **工具调用统计**: 按调用次数排序的工具使用情况
- **事件总数**: 实时统计所有事件数量
- **工作流程摘要**: 自动汇总生成的文档、任务等

## 代码使用示例

### 基础使用

```python
from agents.cli_ui import AgentStreamUI

# 创建 UI 实例
ui = AgentStreamUI(show_timestamps=True, verbose=False)

# 1. 打印头部信息
ui.print_header(
    "🚀 My Agent Application",
    "Processing user request..."
)

# 2. 打印配置信息
ui.print_info_table({
    "Session ID": "sess_123456",
    "Workspace": "/path/to/workspace",
    "Framework": "nextjs",
    "Status": "Running",
})

# 3. 处理事件流
for event in event_stream:
    # 检测阶段变化
    if "current_stage" in event:
        new_stage = event["current_stage"]
        if new_stage != current_stage:
            ui.print_stage_change(current_stage, new_stage)
            current_stage = new_stage
    
    # 打印事件
    ui.print_event(event)

# 4. 打印摘要
ui.print_summary(result)
```

### 错误处理

```python
try:
    # 执行 agent 操作
    result = agent.run()
except Exception as e:
    # 美化打印错误
    ui.print_error(e)
```

## UI 模式选择

### Rich UI (推荐)

**适用场景**:
- ✅ 交互式开发和调试
- ✅ 演示和展示
- ✅ 日常使用

**特点**:
- 完整的美化输出
- 表格、面板、颜色
- 实时统计和摘要

**使用**:
```bash
uv run src/agents/run_agent_local.py --prompt "..." --ui rich
```

### Simple UI

**适用场景**:
- ✅ 快速调试
- ✅ 性能敏感场景
- ✅ 简单的事件记录

**特点**:
- 轻量级输出
- 基础彩色支持
- 只显示重要事件

**使用**:
```bash
uv run src/agents/run_agent_local.py --prompt "..." --ui simple
```

### None (无 UI)

**适用场景**:
- ✅ CI/CD 环境
- ✅ 日志文件记录
- ✅ 脚本自动化

**特点**:
- 原始输出
- 完整事件详情
- 易于解析

**使用**:
```bash
uv run src/agents/run_agent_local.py --prompt "..." --ui none
```

## 高级功能

### 详细模式

显示工具调用参数、元数据等详细信息：

```bash
uv run src/agents/run_agent_local.py --prompt "..." --verbose
```

### 自定义事件

```python
# 创建自定义事件
custom_event = {
    "event_type": "custom",
    "timestamp": time.time(),
    "data": {
        "message": "Custom operation completed",
        "details": {...}
    }
}

ui.print_event(custom_event)
```

### 阶段追踪

```python
# 打印阶段变更
ui.print_stage_change("requirement", "design")
```

## 最佳实践

### 1. 选择合适的 UI 模式

- 开发调试: Rich UI + verbose
- 生产运行: None
- 演示展示: Rich UI

### 2. 合理使用详细模式

只在需要时使用 `--verbose`，避免输出过多信息。

### 3. 结构化事件数据

确保事件数据包含必要字段：
- `event_type`: 事件类型（必需）
- `timestamp`: 时间戳（建议）
- `data`: 事件数据（必需）

### 4. 错误处理

始终使用 `ui.print_error()` 来美化打印错误信息。

## 常见问题

### Q: 输出乱码怎么办？

A: 确保终端支持 UTF-8 编码：

```bash
export LANG=en_US.UTF-8
```

### Q: Rich 库未安装？

A: 运行以下命令安装：

```bash
uv add rich
# 或
pip install rich
```

### Q: 如何只显示特定类型的事件？

A: 在调用 `print_event` 之前过滤事件：

```python
for event in event_stream:
    if event.get("event_type") in ["agent_start", "agent_end"]:
        ui.print_event(event)
```

### Q: 如何自定义颜色和样式？

A: 修改 `AgentStreamUI` 类中的样式字典：

```python
AGENT_STYLES = {
    "my_agent": ("🎯", "bold purple"),
}

EVENT_STYLES = {
    "my_event": ("🔔", "magenta"),
}
```

## 相关文档

- 📄 [详细使用文档](../src/agents/CLI_UI_README.md)
- 🎯 [演示脚本](../src/agents/demo_cli_ui.py)
- 📋 [Change Log](../change-logs/2026-02-01-cli-ui-enhancement.md)
- 🏗️ [项目架构文档](./project_description.md)

## 示例输出

运行演示脚本查看实际效果：

```bash
uv run src/agents/demo_cli_ui.py
```

你会看到：
- 🎨 彩色的头部和面板
- 📊 美观的信息表格
- 👔 Agent 工作流程展示
- 🔧 工具调用记录
- 💬 LLM 流式输出
- 📈 统计信息和摘要
- ❌ 错误处理演示

## 性能考虑

- **Rich UI**: 适度的性能开销，适合大多数场景
- **Simple UI**: 最小的性能开销，适合高频事件
- **None**: 无额外开销，原始输出

## 扩展和定制

### 添加新的 Agent 角色

1. 在 `AGENT_STYLES` 字典中添加条目
2. 选择合适的 emoji 和颜色
3. 确保 agent_name 格式正确

### 添加新的事件类型

1. 在 `EVENT_STYLES` 字典中添加条目
2. 在 `print_event` 方法中添加处理逻辑
3. 编写对应的 `_handle_xxx` 方法

### 创建自定义 UI 类

```python
from agents.cli_ui import AgentStreamUI

class MyCustomUI(AgentStreamUI):
    def _handle_custom_event(self, event, emoji, style):
        # 自定义事件处理逻辑
        pass
```

## 更新日志

- **2026-02-01**: 初始版本发布
  - 完整的 Rich UI 实现
  - 三种 UI 模式
  - 统计和摘要功能
  - 详细文档和演示

## 反馈和贡献

欢迎提供反馈和建议！如有问题或改进建议，请联系开发团队。
