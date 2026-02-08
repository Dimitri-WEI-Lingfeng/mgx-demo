#!/usr/bin/env python3
"""快速开始示例 - 使用内存模式运行 Agent

这个示例展示如何在本地开发环境中快速运行 web_app_team，
无需数据库连接。
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


async def example_1_basic():
    """示例 1: 基础使用 - 创建一个简单的应用"""
    print("\n" + "="*60)
    print("示例 1: 基础使用")
    print("="*60 + "\n")
    
    from agents.context import InMemoryContext, set_context
    from agents.agent_factory import create_team_agent
    from agents.web_app_team.state import create_initial_state
    
    # 1. 创建内存上下文（会自动生成 ID）
    context = InMemoryContext()
    
    print(f"✓ 上下文已创建")
    print(f"  Session ID: {context.session_id}")
    print(f"  Workspace ID: {context.workspace_id}")
    print(f"  Workspace Path: {context.get_workspace_path()}")
    
    # 2. 设置为当前上下文
    set_context(context)
    
    # 3. 创建 Agent 团队
    print(f"\n正在创建 Agent 团队...")
    team = create_team_agent(framework="nextjs")
    
    # 4. 创建初始状态
    state = create_initial_state(
        workspace_id=context.workspace_id,
        framework="nextjs",
        user_prompt="创建一个简单的计数器应用，有增加和减少按钮"
    )
    
    # 5. 运行（这里只创建不实际运行，因为比较耗时）
    print(f"\n✓ Agent 团队已创建并准备就绪")
    print(f"\n如需实际运行，取消注释下面的代码：")
    print(f"# result = await asyncio.to_thread(team.invoke, state)")
    
    # 6. 查看上下文信息
    events = context.get_events()
    messages = context.get_messages()
    print(f"\n当前统计：")
    print(f"  事件数: {len(events)}")
    print(f"  消息数: {len(messages)}")


async def example_2_custom_workspace():
    """示例 2: 指定工作区路径"""
    print("\n" + "="*60)
    print("示例 2: 指定工作区路径")
    print("="*60 + "\n")
    
    from agents.context import InMemoryContext, ContextScope
    import tempfile
    
    # 创建临时目录作为工作区
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. 创建上下文并指定工作区路径
        context = InMemoryContext(
            session_id="my-session",
            workspace_id="my-workspace",
            workspace_path=tmpdir,
        )
        
        print(f"✓ 自定义上下文已创建")
        print(f"  Session ID: {context.session_id}")
        print(f"  Workspace ID: {context.workspace_id}")
        print(f"  Workspace Path: {context.get_workspace_path()}")
        
        # 2. 使用 ContextScope 自动管理上下文
        with ContextScope(context):
            from agents.web_app_team.tools.workspace_tools import (
                write_file, read_file, list_files
            )

            # 3. 测试文件操作
            await write_file.ainvoke({"path": "README.md", "content": "# 我的项目\n\n这是一个测试项目。"})
            content = await read_file.ainvoke({"path": "README.md"})
            files = list_files.invoke({"directory": "."})
            
            print(f"\n✓ 文件操作测试成功")
            print(f"  创建文件: README.md")
            print(f"  文件内容: {content[:30]}...")
            print(f"  文件列表:\n{files}")


async def example_3_event_tracking():
    """示例 3: 事件和消息追踪"""
    print("\n" + "="*60)
    print("示例 3: 事件和消息追踪")
    print("="*60 + "\n")
    
    from agents.context import InMemoryContext, set_context
    from shared.schemas import Event, Message, EventType
    import time
    import uuid
    
    # 1. 创建上下文
    context = InMemoryContext()
    set_context(context)
    
    session_id = context.session_id
    
    # 2. 模拟一些事件和消息
    event = Event(
        event_id=str(uuid.uuid4()),
        session_id=session_id,
        timestamp=time.time(),
        event_type=EventType.AGENT_START,
        data={"prompt": "创建一个待办事项应用", "framework": "demo"},
        agent_name="example_agent",
    )
    await context.event_store.create_event(event)
    
    message = Message(
        message_id=str(uuid.uuid4()),
        session_id=session_id,
        role="user",
        content="创建一个待办事项应用",
        timestamp=time.time(),
        agent_name="example_agent",
    )
    await context.message_store.create_message(message)
    
    event = Event(
        event_id=str(uuid.uuid4()),
        session_id=session_id,
        timestamp=time.time(),
        event_type=EventType.CUSTOM,
        data={"message": "正在分析需求..."},
        agent_name="example_agent",
    )
    await context.event_store.create_event(event)
    
    message = Message(
        message_id=str(uuid.uuid4()),
        session_id=session_id,
        role="assistant",
        content="我理解了，您需要一个待办事项应用...",
        timestamp=time.time(),
        agent_name="example_agent",
    )
    await context.message_store.create_message(message)
    
    event = Event(
        event_id=str(uuid.uuid4()),
        session_id=session_id,
        timestamp=time.time(),
        event_type=EventType.AGENT_END,
        data={"status": "success"},
        agent_name="example_agent",
    )
    await context.event_store.create_event(event)
    
    # 3. 查看事件和消息
    events = context.get_events()
    messages = context.get_messages()
    
    print(f"✓ 记录了 {len(events)} 个事件和 {len(messages)} 条消息\n")
    
    print("事件列表：")
    for i, event in enumerate(events, 1):
        print(f"  {i}. {event['event_type']}: {event['data']}")
    
    print("\n消息列表：")
    for i, msg in enumerate(messages, 1):
        content = msg['content'][:50] + "..." if len(msg['content']) > 50 else msg['content']
        print(f"  {i}. {msg['role']}: {content}")


async def example_4_context_scope():
    """示例 4: 使用 ContextScope 管理作用域"""
    print("\n" + "="*60)
    print("示例 4: 使用 ContextScope 管理作用域")
    print("="*60 + "\n")
    
    from agents.context import InMemoryContext, ContextScope, get_context
    
    # 创建两个不同的上下文
    context_a = InMemoryContext(workspace_id="project-a")
    context_b = InMemoryContext(workspace_id="project-b")
    
    print("测试嵌套作用域：\n")
    
    # 使用 ContextScope A
    with ContextScope(context_a):
        ctx = get_context()
        print(f"✓ 进入作用域 A: {ctx.workspace_id}")
        
        # 嵌套使用 ContextScope B
        with ContextScope(context_b):
            ctx = get_context()
            print(f"  ✓ 进入作用域 B: {ctx.workspace_id}")
        
        # 返回作用域 A
        ctx = get_context()
        print(f"✓ 返回作用域 A: {ctx.workspace_id}")
    
    # 离开所有作用域
    ctx = get_context()
    print(f"✓ 离开所有作用域: {ctx}")


async def example_5_workspace_tools():
    """示例 5: 完整的工作区操作"""
    print("\n" + "="*60)
    print("示例 5: 完整的工作区操作")
    print("="*60 + "\n")
    
    from agents.context import InMemoryContext, set_context, clear_context
    from agents.web_app_team.tools.workspace_tools import (
        create_directory,
        write_file,
        read_file,
        list_files,
        search_in_files,
    )
    import tempfile
    
    # 使用临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        context = InMemoryContext(workspace_path=tmpdir)
        set_context(context)
        
        try:
            print("执行一系列工作区操作...\n")
            
            # 1. 创建目录结构
            print("1. 创建目录结构")
            await create_directory.ainvoke({"path": "src"})
            await create_directory.ainvoke({"path": "src/components"})
            await create_directory.ainvoke({"path": "src/utils"})

            # 2. 创建文件
            print("2. 创建文件")
            await write_file.ainvoke({"path": "src/index.tsx", "content": "export default function App() { return <div>Hello</div>; }"})
            await write_file.ainvoke({"path": "src/components/Header.tsx", "content": "export function Header() { return <header>My App</header>; }"})
            await write_file.ainvoke({"path": "src/utils/helpers.ts", "content": "export function formatDate(date: Date) { return date.toISOString(); }"})
            await write_file.ainvoke({"path": "README.md", "content": "# 我的项目\n\n这是一个示例项目。"})

            # 3. 列出文件
            print("3. 列出文件")
            files = await list_files.ainvoke({"directory": "."})
            print(f"   根目录:\n{files}\n")

            # 4. 搜索文件内容
            print("4. 搜索包含 'export' 的文件")
            results = await search_in_files.ainvoke({"pattern": "export", "directory": ".", "file_extension": ".tsx"})
            print(f"   搜索结果:\n{results[:200]}...\n")

            # 5. 读取文件
            print("5. 读取 README.md")
            content = await read_file.ainvoke({"path": "README.md"})
            print(f"   内容: {content}\n")
            
            print("✓ 所有工作区操作完成")
            
        finally:
            clear_context()


async def main():
    """运行所有示例"""
    print("\n" + "🚀 " + "="*58)
    print("内存模式快速开始示例")
    print("="*60 + "\n")
    
    print("这些示例展示了如何在本地开发环境中使用内存模式。")
    print("无需数据库连接，快速启动和调试。\n")
    
    # 运行所有示例
    await example_1_basic()
    await example_2_custom_workspace()
    await example_3_event_tracking()
    await example_4_context_scope()
    await example_5_workspace_tools()
    
    print("\n" + "="*60)
    print("✅ 所有示例运行完成！")
    print("="*60 + "\n")
    
    print("下一步：")
    print("  1. 查看文档: src/agents/context/README.md")
    print("  2. 运行测试: uv run python scripts/test_context.py")
    print("  3. 本地开发: uv run python scripts/run_agent_local.py --help")
    print()


if __name__ == "__main__":
    asyncio.run(main())
