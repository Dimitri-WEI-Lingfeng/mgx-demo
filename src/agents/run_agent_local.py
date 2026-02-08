#!/usr/bin/env python3
"""本地运行 agent 脚本 - 使用内存模式，不需要数据库。

这个脚本演示如何在本地开发环境中运行 web_app_team，
使用 InMemoryContext 避免对数据库的依赖。
"""
import asyncio
import signal
import sys
from pathlib import Path
import loguru

from shared.schemas.event import EventType

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agents.context import InMemoryContext, set_context
from agents.agent_factory import create_team_agent
from agents.web_app_team.state import create_initial_state
from agents.cli_ui import stream_agent_with_ui


async def run_local_agent(
    prompt: str,
    framework: str = "nextjs",
    context: InMemoryContext | None = None,
    workspace_path: str | None = None,
):
    """在本地运行 agent。
    
    Args:
        prompt: 用户需求描述
        framework: 目标框架（nextjs, fastapi-vite）
        workspace_path: 工作区路径（可选，默认自动创建）
        verbose: 是否显示详细信息
    """
    if context is None:
        raise ValueError("context 不能为 None")

    # 设置上下文
    set_context(context)
    
   
    print(f"\n{'='*60}")
    print(f"本地 Agent 运行环境")
    print(f"{'='*60}")
    print(f"Session ID: {context.session_id}")
    print(f"Workspace ID: {context.workspace_id}")
    print(f"Workspace Path: {context.get_workspace_path()}")
    print(f"Framework: {framework}")
    print(f"{'='*60}\n")
    
    print("正在创建 Web App 开发团队...")
    
    team_graph = create_team_agent(framework=framework)
    
    # 创建初始状态
    initial_state = create_initial_state(
        workspace_id=context.workspace_id,
        framework=framework,
        user_prompt=prompt,
    )
    
    
    print(f"\n开始处理需求：{prompt[:100]}...")
    print(f"\n{'='*60}\n")

    # 流式处理事件（使用 astream 以支持 async 节点和工具）
    # - "updates": 节点状态更新
    # - "messages": LLM token 流（返回 tuple: (message_chunk, metadata)）
    async_generator = team_graph.astream(
        initial_state,
        subgraphs=True,
        stream_mode=["updates", "messages"],
    )

    result = await stream_agent_with_ui(async_generator)
    return result
    
  

async def main():
    """主函数 - 演示示例。"""
    import argparse
    
    parser = argparse.ArgumentParser(description="本地运行 Agent（内存模式）")
    parser.add_argument("--prompt", "-p", default="实现一个 todo app", help="用户需求描述")
    parser.add_argument(
        "--framework", "-f",
        default="nextjs",
        choices=["nextjs", "fastapi-vite"],
        help="目标框架",
    )
    # default to user home directory
    default_path = Path.home() / "mgx_workspaces" 
    parser.add_argument(
        "--workspace", "-w",
        help="工作区路径（可选）",
        default=default_path
    )
   
    
    args = parser.parse_args()

    workspace_path = args.workspace

    # 创建内存上下文
    context = InMemoryContext(
        workspace_path=workspace_path,
        auto_create_container=True,
    )

    # 定义 signal handler
    def handle_signal(sig, frame):
        """处理 SIGINT (Ctrl+C) 和 SIGTERM 信号"""
        try:
            sig_name = signal.Signals(sig).name
        except (ValueError, AttributeError):
            sig_name = str(sig)
        print(f"\n\n收到 {sig_name} 信号，正在清理 context...")
        # 抛出 KeyboardInterrupt 来触发正常的退出流程
        raise KeyboardInterrupt()
    
    # 注册 signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        async with context:
            result = await run_local_agent(
                prompt=args.prompt,
                framework=args.framework,
                context=context,
                workspace_path=workspace_path,
            )
            
            if result is None:
                sys.exit(1)
                
    except KeyboardInterrupt:
        print("\n收到中断信号，正在清理 context 资源...")
        # async with 的 __aexit__ 会自动被调用来清理 context
        sys.exit(130)  # 130 = 128 + SIGINT(2)
    except Exception as e:
        print(f"\n发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        print("Context 清理完成")


if __name__ == "__main__":
    asyncio.run(main())
