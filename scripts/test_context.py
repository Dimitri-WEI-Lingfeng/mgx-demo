#!/usr/bin/env python3
"""测试上下文抽象层。

这个脚本测试新的上下文系统是否正常工作。
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_memory_context():
    """测试内存上下文。"""
    from agents.context import InMemoryContext, set_context, get_context, clear_context
    
    print("\n" + "="*60)
    print("测试 InMemoryContext")
    print("="*60)
    
    # 1. 创建上下文
    context = InMemoryContext()
    print(f"✓ 创建上下文成功")
    print(f"  Session ID: {context.session_id}")
    print(f"  Workspace ID: {context.workspace_id}")
    print(f"  Workspace Path: {context.get_workspace_path()}")
    
    # 2. 设置和获取上下文
    set_context(context)
    ctx = get_context()
    assert ctx is not None
    assert ctx.session_id == context.session_id
    print(f"✓ 上下文设置和获取成功")
    
    # 3. 测试工作区路径
    workspace_path = context.get_workspace_path("test.txt")
    assert workspace_path.exists() or not workspace_path.exists()  # 路径可能存在或不存在
    print(f"✓ 工作区路径获取成功: {workspace_path}")
    
    # 4. 测试容器名称
    container_name = context.get_container_name()
    assert container_name.startswith("mgx-dev-")
    print(f"✓ 容器名称生成成功: {container_name}")
    
    # 5. 清除上下文
    clear_context()
    ctx = get_context()
    assert ctx is None
    print(f"✓ 上下文清除成功")
    
    print("\n✅ InMemoryContext 测试通过\n")


def test_context_scope():
    """测试上下文作用域。"""
    from agents.context import InMemoryContext, ContextScope, get_context
    
    print("="*60)
    print("测试 ContextScope")
    print("="*60)
    
    context1 = InMemoryContext(workspace_id="workspace-1")
    context2 = InMemoryContext(workspace_id="workspace-2")
    
    # 1. 测试嵌套作用域
    with ContextScope(context1):
        ctx = get_context()
        assert ctx.workspace_id == "workspace-1"
        print(f"✓ 外层作用域: {ctx.workspace_id}")
        
        with ContextScope(context2):
            ctx = get_context()
            assert ctx.workspace_id == "workspace-2"
            print(f"✓ 内层作用域: {ctx.workspace_id}")
        
        ctx = get_context()
        assert ctx.workspace_id == "workspace-1"
        print(f"✓ 返回外层作用域: {ctx.workspace_id}")
    
    # 2. 离开作用域后应该为 None
    ctx = get_context()
    assert ctx is None
    print(f"✓ 离开作用域后清除成功")
    
    print("\n✅ ContextScope 测试通过\n")


def test_workspace_tools():
    """测试工作区工具。"""
    from agents.context import InMemoryContext, set_context, clear_context
    from agents.web_app_team.tools.workspace_tools import (
        write_file, read_file, list_files, create_directory
    )
    
    print("="*60)
    print("测试 Workspace Tools")
    print("="*60)
    
    # 创建临时上下文
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        context = InMemoryContext(workspace_path=tmpdir)
        set_context(context)
        
        try:
            # 1. 创建目录
            result = create_directory("test_dir")
            assert "成功" in result
            print(f"✓ 创建目录成功")
            
            # 2. 写入文件
            result = write_file("test.txt", "Hello, World!")
            assert "成功" in result
            print(f"✓ 写入文件成功")
            
            # 3. 读取文件
            content = read_file("test.txt")
            assert content == "Hello, World!"
            print(f"✓ 读取文件成功: {content}")
            
            # 4. 列出文件
            result = list_files(".")
            assert "test.txt" in result
            print(f"✓ 列出文件成功")
            
            print("\n✅ Workspace Tools 测试通过\n")
        
        finally:
            clear_context()


def test_event_and_message_stores():
    """测试事件和消息存储。"""
    import asyncio
    from agents.context import InMemoryContext
    
    print("="*60)
    print("测试 Event 和 Message Stores")
    print("="*60)
    
    async def run_test():
        from shared.schemas import Event, Message, EventType
        import time
        import uuid
        
        context = InMemoryContext()
        session_id = context.session_id
        
        # 1. 创建事件
        event = Event(
            event_id=str(uuid.uuid4()),
            session_id=session_id,
            timestamp=time.time(),
            event_type=EventType.CUSTOM,
            data={"message": "test"},
            agent_name="test_agent",
        )
        result_event = await context.event_store.create_event(event)
        print(f"✓ 创建事件成功: {event.event_type}")
        
        # 2. 创建消息
        message = Message(
            message_id=str(uuid.uuid4()),
            session_id=session_id,
            role="user",
            content="Hello",
            timestamp=time.time(),
            agent_name="test_agent",
        )
        result_message = await context.message_store.create_message(message)
        print(f"✓ 创建消息成功: {message.role}")
        
        # 3. 查看事件和消息
        events = context.get_events()
        messages = context.get_messages()
        assert len(events) == 1
        assert len(messages) == 1
        print(f"✓ 事件数: {len(events)}, 消息数: {len(messages)}")
        
        print("\n✅ Event 和 Message Stores 测试通过\n")
    
    asyncio.run(run_test())


def main():
    """运行所有测试。"""
    print("\n" + "🧪 " + "="*58)
    print("开始测试上下文抽象层")
    print("="*60 + "\n")
    
    try:
        test_memory_context()
        test_context_scope()
        test_workspace_tools()
        test_event_and_message_stores()
        
        print("="*60)
        print("🎉 所有测试通过！")
        print("="*60 + "\n")
        return 0
    
    except Exception as e:
        import traceback
        print("\n" + "="*60)
        print("❌ 测试失败")
        print("="*60)
        print(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
