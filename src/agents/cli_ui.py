"""CLI Agent UI - 美化打印 Agent Stream Events。

这个模块提供了一套美观的 CLI 界面来展示 agent 的工作流程和事件流。
使用 rich 库来实现彩色输出、进度条、表格等功能。
"""

from typing import Any, Dict, Optional
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich.tree import Tree
from rich import box
from rich.markdown import Markdown
import json
import loguru
import langchain_core.messages as langchain_messages


class AgentStreamUI:
    """Agent Stream 事件的 UI 展示器。"""

    # Agent 角色对应的 emoji 和颜色
    AGENT_STYLES = {
        "boss": ("👔", "bold magenta"),
        "product_manager": ("📋", "bold blue"),
        "architect": ("🏗️", "bold cyan"),
        "project_manager": ("📊", "bold yellow"),
        "engineer": ("💻", "bold green"),
        "qa": ("🧪", "bold red"),
    }

    # 事件类型对应的 emoji 和颜色
    EVENT_STYLES = {
        "agent_start": ("▶️", "bold green"),
        "agent_end": ("✅", "bold green"),
        "agent_error": ("❌", "bold red"),
        "tool_start": ("🔧", "cyan"),
        "tool_end": ("✔️", "cyan"),
        "llm_start": ("🤖", "yellow"),
        "llm_stream": ("💬", "yellow"),
        "llm_end": ("✓", "yellow"),
        "message_delta": ("📝", "blue"),
        "message_complete": ("📄", "bold blue"),
        "custom": ("🔔", "magenta"),
        "finish": ("🎉", "bold green"),
    }

    # 工作流阶段对应的 emoji
    STAGE_STYLES = {
        "requirement": ("📝", "Requirements Analysis"),
        "design": ("🏗️", "Architecture Design"),
        "development": ("💻", "Code Development"),
        "testing": ("🧪", "Testing & QA"),
        "completed": ("✅", "Completed"),
    }

    def __init__(self, show_timestamps: bool = True, verbose: bool = False):
        """初始化 UI。

        Args:
            show_timestamps: 是否显示时间戳
            verbose: 是否显示详细信息（包括元数据等）
        """
        self.console = Console()
        self.show_timestamps = show_timestamps
        self.verbose = verbose

        # 统计信息
        self.stats: Dict[str, Any] = {
            "events": 0,
            "agents": {},
            "tools": {},
            "start_time": None,
        }

        # 当前活动的 agent
        self.current_agent: Optional[str] = None
        self.current_stage: Optional[str] = None

        # 消息缓冲区（用于增量消息）
        self.message_buffer: Dict[str, str] = {}

    def print_header(self, title: str, subtitle: str = ""):
        """打印标题头。"""
        self.console.print()
        panel = Panel(
            f"[bold white]{title}[/]\n[dim]{subtitle}[/]" if subtitle else f"[bold white]{title}[/]",
            border_style="bold blue",
            box=box.DOUBLE,
        )
        self.console.print(panel)
        self.console.print()

    def print_info_table(self, data: Dict[str, Any]):
        """打印信息表格。"""
        table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")

        for key, value in data.items():
            table.add_row(key, str(value))

        self.console.print(table)
        self.console.print()

    def print_event(self, event: Dict[str, Any]):
        """打印单个事件。

        Args:
            event: 事件字典，包含 event_type, data 等字段
        """
        events_count = self.stats.get("events", 0)
        if isinstance(events_count, int):
            self.stats["events"] = events_count + 1

        event_type = event.get("event_type", "unknown")
        data = event.get("data", {})
        timestamp = event.get("timestamp")

        # 获取事件样式
        emoji, style = self.EVENT_STYLES.get(event_type, ("•", "white"))
        # 处理不同类型的事件
        if event_type == "agent_start":
            self._handle_agent_start(event, emoji, style)
        elif event_type == "agent_end":
            self._handle_agent_end(event, emoji, style)
        elif event_type == "agent_error":
            self._handle_agent_error(event, emoji, style)
        elif event_type == "tool_start":
            self._handle_tool_start(event, emoji, style)
        elif event_type == "tool_end":
            self._handle_tool_end(event, emoji, style)
        elif event_type == "llm_stream":
            self._handle_llm_stream(event, emoji, style)
        elif event_type == "message_delta":
            self._handle_message_delta(event, emoji, style)
        elif event_type == "message_complete":
            self._handle_message_complete(event, emoji, style)
        elif event_type == "finish":
            self._handle_finish(event, emoji, style)
        else:
            # 默认处理
            self._handle_default_event(event, emoji, style)

    def _handle_agent_start(self, event: Dict, emoji: str, style: str):
        """处理 agent 开始事件。"""
        data = event.get("data", {})
        agent_name = data.get("agent_name", "Unknown Agent")

        # 提取 agent role（从 agent_name 中）
        agent_role = agent_name.lower().replace(" ", "_").replace("agent", "").strip("_")
        agent_emoji, agent_color = self.AGENT_STYLES.get(agent_role, ("🤖", "white"))

        self.current_agent = agent_name

        # 更新统计
        agents = self.stats.get("agents", {})
        if isinstance(agents, dict):
            if agent_name not in agents:
                agents[agent_name] = {"count": 0, "tools": 0}
            agent_stats = agents[agent_name]
            if isinstance(agent_stats, dict) and "count" in agent_stats:
                if isinstance(agent_stats["count"], int):
                    agent_stats["count"] += 1

        # 打印 agent 开始面板
        self.console.print()
        panel = Panel(
            f"[{agent_color}]{agent_emoji} {agent_name} 开始工作[/]",
            border_style=agent_color,
            box=box.ROUNDED,
        )
        self.console.print(panel)

    def _handle_agent_end(self, event: Dict, emoji: str, style: str):
        """处理 agent 结束事件。"""
        data = event.get("data", {})
        agent_name = data.get("agent_name", self.current_agent or "Unknown Agent")

        self.console.print(f"  [{style}]{emoji} {agent_name} 工作完成[/]")
        self.current_agent = None
        self.console.print()

    def _handle_agent_error(self, event: Dict, emoji: str, style: str):
        """处理 agent 错误事件。"""
        data = event.get("data", {})
        error = data.get("error", "Unknown error")

        self.console.print(
            Panel(
                f"[{style}]{emoji} 错误: {error}[/]",
                border_style="red",
                box=box.HEAVY,
            )
        )

    def _handle_tool_start(self, event: Dict, emoji: str, style: str):
        """处理工具开始事件。"""
        data = event.get("data", {})
        tool_name = data.get("tool_name", "Unknown Tool")
        tool_input = data.get("input", {})

        # 更新统计
        tools = self.stats.get("tools", {})
        if isinstance(tools, dict):
            if tool_name not in tools:
                tools[tool_name] = 0
            if isinstance(tools[tool_name], int):
                tools[tool_name] += 1

        agents = self.stats.get("agents", {})
        if self.current_agent and isinstance(agents, dict) and self.current_agent in agents:
            agent_stats = agents[self.current_agent]
            if isinstance(agent_stats, dict) and "tools" in agent_stats:
                if isinstance(agent_stats["tools"], int):
                    agent_stats["tools"] += 1

        # 打印工具调用
        self.console.print(f"  [{style}]{emoji} 调用工具: [bold]{tool_name}[/][/]")

        if self.verbose and tool_input:
            self.console.print(f"    [dim]参数: {self._format_dict(tool_input)}[/]")

    def _handle_tool_end(self, event: Dict, emoji: str, style: str):
        """处理工具结束事件。"""
        data = event.get("data", {})
        tool_name = data.get("tool_name", "Unknown Tool")

        self.console.print(f"  [{style}]{emoji} 工具完成: [bold]{tool_name}[/][/]")

    def _handle_llm_stream(self, event: Dict, emoji: str, style: str):
        """处理 LLM 流式输出事件。"""
        data = event.get("data", {})
        delta = data.get("delta", "")
        node = data.get("node", "")

        if delta:
            # 流式输出（不换行）
            # 如果 verbose 模式，显示节点信息
            if self.verbose and node:
                self.console.print(f"[dim]({node})[/] ", end="")
            self.console.print(delta, end="", style=style)

    def _handle_message_delta(self, event: Dict, emoji: str, style: str):
        """处理消息增量事件。"""
        data = event.get("data", {})
        delta = data.get("delta", "")
        message_id = event.get("message_id")

        # 累积消息
        if message_id:
            msg_id = str(message_id)
            if msg_id not in self.message_buffer:
                self.message_buffer[msg_id] = ""
            self.message_buffer[msg_id] += str(delta)

        # 实时显示（不换行）
        if delta:
            self.console.print(delta, end="", style=style)

    def _handle_message_complete(self, event: Dict, emoji: str, style: str):
        """处理消息完成事件。"""
        data = event.get("data", {})
        message_id = event.get("message_id")

        # 如果有缓冲的消息，显示完整消息
        if message_id:
            msg_id = str(message_id)
            if msg_id in self.message_buffer:
                complete_message = self.message_buffer[msg_id]
                self.console.print()  # 换行

                # 如果消息很长，用面板显示
                if len(complete_message) > 200:
                    self.console.print(
                        Panel(
                            complete_message,
                            title=f"{emoji} 完整消息",
                            border_style=style,
                            box=box.ROUNDED,
                        )
                    )

                # 清除缓冲
                del self.message_buffer[msg_id]
            else:
                self.console.print()  # 只是换行
        else:
            self.console.print()  # 只是换行

    def _handle_finish(self, event: Dict, emoji: str, style: str):
        """处理完成事件。"""
        data = event.get("data", {})

        self.console.print()
        self.console.print(
            Panel(
                f"[{style}]{emoji} 工作流程已完成！[/]",
                border_style="bold green",
                box=box.DOUBLE,
            )
        )

    def _handle_default_event(self, event: Dict, emoji: str, style: str):
        """处理默认事件。"""
        event_type = event.get("event_type", "unknown")
        data = event.get("data", {})

        if self.verbose:
            self.console.print(f"  [{style}]{emoji} {event_type}[/]")
            if data:
                self.console.print(f"    [dim]{self._format_dict(data)}[/]")

    def _format_dict(self, d: Dict, max_length: int = 100) -> str:
        """格式化字典为字符串。"""
        s = json.dumps(d, ensure_ascii=False, indent=2)
        if len(s) > max_length:
            s = s[:max_length] + "..."
        return s

    def print_stage_change(self, old_stage: str, new_stage: str):
        """打印阶段变更。"""
        old_emoji, old_name = self.STAGE_STYLES.get(old_stage, ("", old_stage))
        new_emoji, new_name = self.STAGE_STYLES.get(new_stage, ("", new_stage))

        self.current_stage = new_stage

        self.console.print()
        self.console.print(
            Panel(
                f"[dim]{old_emoji} {old_name}[/] → [bold cyan]{new_emoji} {new_name}[/]",
                border_style="cyan",
                box=box.ROUNDED,
            )
        )
        self.console.print()

    def print_summary(self, result: Dict[str, Any]):
        """打印执行摘要。"""
        self.console.print()
        self.console.print("[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]")
        self.console.print()

        # 结果摘要表格
        table = Table(title="📊 执行摘要", box=box.ROUNDED, show_header=True, header_style="bold magenta")
        table.add_column("项目", style="cyan")
        table.add_column("值", style="white")

        # 基本信息
        table.add_row("当前阶段", self._format_stage(result.get("current_stage", "unknown")))
        table.add_row("消息数量", str(len(result.get("messages", []))))

        # 产物
        if result.get("prd_document"):
            table.add_row("PRD 文档", "✅ 已生成")

        if result.get("design_document"):
            table.add_row("设计文档", "✅ 已生成")

        if result.get("tasks"):
            table.add_row("任务列表", f"✅ {len(result.get('tasks', []))} 个任务")

        if result.get("code_changes"):
            table.add_row("代码变更", f"✅ {len(result.get('code_changes', []))} 个变更")

        if result.get("test_results"):
            table.add_row("测试结果", "✅ 已生成")

        self.console.print(table)
        self.console.print()

        # 事件统计
        self._print_event_stats()

        self.console.print()
        self.console.print("[bold cyan]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]")
        self.console.print()

    def _print_event_stats(self):
        """打印事件统计。"""
        # Agent 统计
        if self.stats["agents"]:
            agent_table = Table(title="🤖 Agent 活动统计", box=box.SIMPLE, show_header=True)
            agent_table.add_column("Agent", style="cyan")
            agent_table.add_column("执行次数", style="yellow", justify="right")
            agent_table.add_column("工具调用", style="green", justify="right")

            for agent_name, stats in self.stats["agents"].items():
                agent_table.add_row(
                    agent_name,
                    str(stats["count"]),
                    str(stats["tools"]),
                )

            self.console.print(agent_table)
            self.console.print()

        # 工具统计
        if self.stats["tools"]:
            tool_table = Table(title="🔧 工具调用统计", box=box.SIMPLE, show_header=True)
            tool_table.add_column("工具", style="cyan")
            tool_table.add_column("调用次数", style="yellow", justify="right")

            # 按调用次数排序
            sorted_tools = sorted(self.stats["tools"].items(), key=lambda x: x[1], reverse=True)

            for tool_name, count in sorted_tools:
                tool_table.add_row(tool_name, str(count))

            self.console.print(tool_table)
            self.console.print()

        # 总体统计
        self.console.print(f"[bold]总事件数:[/] [yellow]{self.stats['events']}[/]")

    def _format_stage(self, stage: str) -> str:
        """格式化阶段名称。"""
        emoji, name = self.STAGE_STYLES.get(stage, ("", stage))
        return f"{emoji} {name}"

    def print_error(self, error: Exception):
        """打印错误信息。"""
        import traceback

        self.console.print()
        self.console.print(
            Panel(
                f"[bold red]❌ 执行失败[/]\n\n[red]{str(error)}[/]\n\n[dim]{traceback.format_exc()}[/]",
                border_style="bold red",
                box=box.HEAVY,
            )
        )
        self.console.print()


class SimpleStreamUI:
    """简化版的 Stream UI - 适合快速调试。"""

    def __init__(self):
        self.console = Console()
        self.event_count = 0

    def print_header(self, title: str, subtitle: str = ""):
        """打印标题。"""
        self.console.print(f"\n{'='*60}")
        self.console.print(f"{title}")
        if subtitle:
            self.console.print(subtitle)
        self.console.print(f"{'='*60}\n")

    def print_info_table(self, data: Dict[str, Any]):
        """打印信息表格。"""
        for key, value in data.items():
            self.console.print(f"{key}: {value}")
        self.console.print()

    def print_event(self, event: Dict[str, Any]):
        """打印事件（简单格式）。"""
        self.event_count += 1
        event_type = event.get("event_type", "unknown")
        data = event.get("data", {})

        # 只打印重要事件
        if event_type in ["agent_start", "agent_end", "tool_start", "message_complete", "finish"]:
            self.console.print(f"[{self.event_count}] {event_type}: {data}")

    def print_stage_change(self, old_stage: str, new_stage: str):
        """打印阶段变更。"""
        self.console.print(f"\n>>> Stage: {old_stage} → {new_stage}\n")

    def print_summary(self, result: Dict[str, Any]):
        """打印摘要。"""
        self.console.print(f"\n{'='*60}")
        self.console.print("执行完成")
        self.console.print(f"总事件数: {self.event_count}")
        self.console.print(f"{'='*60}\n")

    def print_error(self, error: Exception):
        """打印错误。"""
        self.console.print(f"\n[red]❌ 错误: {error}[/]\n")


async def stream_agent_with_ui(agent_generator):
    """异步消费 agent 流并展示 UI。支持 astream 返回的 async generator。"""
    import time

    ui = AgentStreamUI()

    try:
        result = None
        last_node = None
        current_stage = None
        current_node = None
        llm_streaming = False  # 跟踪是否正在流式输出 LLM tokens

        async for stream_output in agent_generator:
            # stream_output 的格式：(stream_mode, chunk)
            assert len(stream_output) == 3
            namespace, stream_mode, chunk = stream_output
            if not namespace:
                ui.console.print("namespace is None")
                ui.console.print_json(data=str(chunk))
                continue
            try:
                current_node = namespace[0].split(":")[0]
            except Exception:
                import traceback
                traceback.print_exc()
                raise

            if stream_mode == "updates":
                # 处理状态更新事件
                # chunk 格式: {node_name: {state_updates}}
                node_output = chunk
                # 如果之前在流式输出 LLM tokens，先换行
                if llm_streaming:
                    ui.console.print()  # 换行
                    llm_streaming = False

                if current_node != last_node:
                    if last_node:
                        # 上一个节点结束
                        ui.print_event(
                            {
                                "event_type": "agent_end",
                                "timestamp": time.time(),
                                "data": {"agent_name": last_node.replace("_", " ").title()},
                            }
                        )
                    # 新节点开始
                    ui.print_event(
                        {
                            "event_type": "agent_start",
                            "timestamp": time.time(),
                            "data": {"agent_name": current_node.replace("_", " ").title()},
                        }
                    )
                    last_node = current_node

                # 检查阶段变化
                if isinstance(node_output, dict) and "current_stage" in node_output:
                    new_stage = node_output["current_stage"]
                    if new_stage and new_stage != current_stage:
                        ui.print_stage_change(current_stage, new_stage)
                        current_stage = new_stage

                # 保存最后的结果
                if isinstance(node_output, dict):
                    result = node_output

            elif stream_mode == "messages":
                # 处理 LLM token 流
                # chunk 格式: (message_chunk, metadata) - 这是一个 tuple！
                message_chunk, metadata = chunk

                if isinstance(message_chunk, langchain_messages.AIMessageChunk):
                    # 标记正在流式输出
                    if not llm_streaming:
                        # 第一个 token，显示一个提示
                        ui.console.print(f"\n  💬 ", end="")
                        llm_streaming = True

                    # 使用 CLI UI 显示 LLM 流式输出
                    ui.print_event(
                        {
                            "event_type": "llm_stream",
                            "timestamp": time.time(),
                            "data": {
                                "delta": message_chunk.content,
                                "node": metadata.get("langgraph_node", "unknown"),
                                "tags": metadata.get("tags", []),
                            },
                        }
                    )
                elif isinstance(message_chunk, langchain_messages.ToolMessage):
                    ui.console.print("tool message: " + str(message_chunk))
                elif isinstance(message_chunk, langchain_messages.AIMessage):
                    ui.console.print("ai message: " + str(message_chunk))
                else:
                    ui.console.print("messages type: " + str(type(message_chunk)))
                    ui.console.print("other message: " + str(message_chunk))

        # 如果 LLM 流式输出未结束，换行
        if ui and llm_streaming:
            ui.console.print()

        # 最后一个节点结束
        if ui and current_node:
            ui.print_event(
                {
                    "event_type": "agent_end",
                    "timestamp": time.time(),
                    "data": {"agent_name": current_node.replace("_", " ").title()},
                }
            )
            ui.print_event(
                {
                    "event_type": "finish",
                    "timestamp": time.time(),
                    "data": {"status": "completed"},
                }
            )

        # 打印结果摘要
        if ui:
            ui.print_summary(result)
        else:
            print(f"\n{'='*60}")
            print(f"执行完成")
            print(f"{'='*60}")
            print(f"当前阶段: {result.get('current_stage')}")
            print(f"消息数量: {len(result.get('messages', []))}")

            if result.get("prd_document"):
                print(f"\n✓ PRD 文档已生成")

            if result.get("design_document"):
                print(f"✓ 设计文档已生成")

            if result.get("tasks"):
                print(f"✓ 任务列表已生成 ({len(result.get('tasks', []))} 个任务)")

            print(f"\n{'='*60}\n")

        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        if ui:
            ui.print_error(e)
        else:
            print(f"\n❌ 执行失败：{e}")
        return None
