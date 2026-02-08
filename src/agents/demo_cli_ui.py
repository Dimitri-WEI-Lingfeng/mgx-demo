#!/usr/bin/env python3
"""演示 CLI UI 功能的示例脚本。

这个脚本展示了如何使用 AgentStreamUI 来美化打印各种事件。
"""

import asyncio
import time
from agents.cli_ui import AgentStreamUI


async def demo_events():
    """演示各种事件的打印效果。"""
    
    ui = AgentStreamUI(show_timestamps=True, verbose=True)
    
    # 1. 打印头部
    ui.print_header(
        "🚀 Agent Stream UI 演示",
        "展示各种事件的美化输出效果"
    )
    
    # 2. 打印信息表格
    ui.print_info_table({
        "Session ID": "sess_demo_12345",
        "Workspace ID": "ws_demo_67890",
        "Framework": "nextjs",
        "Status": "Running",
    })
    
    # 3. 模拟 Boss Agent 开始工作
    ui.print_event({
        "event_type": "agent_start",
        "timestamp": time.time(),
        "data": {
            "agent_name": "Boss Agent",
        }
    })

    await asyncio.sleep(0.5)

    # 4. 模拟工具调用
    ui.print_event({
        "event_type": "tool_start",
        "timestamp": time.time(),
        "data": {
            "tool_name": "read_file",
            "input": {
                "file_path": "/workspace/requirements.md",
            }
        }
    })

    await asyncio.sleep(0.3)

    ui.print_event({
        "event_type": "tool_end",
        "timestamp": time.time(),
        "data": {
            "tool_name": "read_file",
        }
    })

    await asyncio.sleep(0.5)

    # 5. 模拟 LLM 流式输出
    ui.print_event({
        "event_type": "llm_start",
        "timestamp": time.time(),
        "data": {
            "model": "gpt-4",
        }
    })
    
    message = "我已经分析了用户的需求，现在开始创建 requirements.md 文档。"
    for i, char in enumerate(message):
        ui.print_event({
            "event_type": "llm_stream",
            "timestamp": time.time(),
            "data": {
                "delta": char,
            }
        })
        await asyncio.sleep(0.02)

    ui.console.print()  # 换行

    ui.print_event({
        "event_type": "llm_end",
        "timestamp": time.time(),
        "data": {}
    })

    await asyncio.sleep(0.5)

    # 6. Agent 完成
    ui.print_event({
        "event_type": "agent_end",
        "timestamp": time.time(),
        "data": {
            "agent_name": "Boss Agent",
        }
    })

    await asyncio.sleep(0.5)

    # 7. 阶段变更
    ui.print_stage_change("requirement", "design")

    await asyncio.sleep(0.5)

    # 8. Product Manager Agent 开始工作
    ui.print_event({
        "event_type": "agent_start",
        "timestamp": time.time(),
        "data": {
            "agent_name": "Product Manager Agent",
        }
    })

    await asyncio.sleep(0.5)

    ui.print_event({
        "event_type": "tool_start",
        "timestamp": time.time(),
        "data": {
            "tool_name": "write_file",
            "input": {
                "file_path": "/workspace/prd.md",
                "content": "# Product Requirements Document\n\n...",
            }
        }
    })

    await asyncio.sleep(0.3)

    ui.print_event({
        "event_type": "tool_end",
        "timestamp": time.time(),
        "data": {
            "tool_name": "write_file",
        }
    })

    await asyncio.sleep(0.5)

    ui.print_event({
        "event_type": "agent_end",
        "timestamp": time.time(),
        "data": {
            "agent_name": "Product Manager Agent",
        }
    })

    await asyncio.sleep(0.5)

    # 9. 完成事件
    ui.print_event({
        "event_type": "finish",
        "timestamp": time.time(),
        "data": {
            "status": "completed",
        }
    })

    await asyncio.sleep(0.5)

    # 10. 打印摘要
    result = {
        "current_stage": "design",
        "messages": ["msg1", "msg2", "msg3"],
        "prd_document": "prd.md",
        "design_document": None,
        "tasks": [{"id": 1}, {"id": 2}],
        "code_changes": None,
        "test_results": None,
    }
    
    ui.print_summary(result)


def demo_error():
    """演示错误显示。"""
    ui = AgentStreamUI()
    
    ui.print_header("错误处理演示")
    
    # 模拟错误
    ui.print_event({
        "event_type": "agent_error",
        "timestamp": time.time(),
        "data": {
            "agent_name": "Engineer Agent",
            "error": "Failed to execute docker command",
        }
    })
    
    # 使用异常显示
    try:
        raise ValueError("这是一个测试错误")
    except Exception as e:
        import traceback
        traceback.print_exc()
        ui.print_error(e)


if __name__ == "__main__":
    print("\n" + "="*60)
    print("演示 1: 各种事件展示")
    print("="*60)
    asyncio.run(demo_events())
    
    print("\n" + "="*60)
    print("演示 2: 错误处理")
    print("="*60)
    demo_error()
