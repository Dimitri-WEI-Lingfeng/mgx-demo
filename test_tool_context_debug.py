"""调试工具装饰器和上下文的交互。"""

import threading
from langchain.tools import tool
from src.agents.context import InMemoryContext, set_context, get_context, require_context

print("=" * 60)
print("测试 1: 直接调用 require_context")
print("=" * 60)

context = InMemoryContext(workspace_path='./test')
set_context(context)

print(f"主线程 ID: {threading.get_ident()}")
print(f"主线程上下文: {get_context().workspace_id}\n")

try:
    ctx = require_context()
    print(f"✅ 直接调用成功: {ctx.workspace_id}\n")
except Exception as e:
    print(f"❌ 直接调用失败: {e}\n")

print("=" * 60)
print("测试 2: 在装饰器函数中调用")
print("=" * 60)

@tool
def test_tool_simple() -> str:
    """测试工具 - 简单版本"""
    thread_id = threading.get_ident()
    print(f"  工具执行线程 ID: {thread_id}")
    
    ctx = get_context()
    print(f"  get_context() 结果: {ctx}")
    
    if ctx:
        print(f"  ✅ 成功获取上下文: {ctx.workspace_id}")
        return f"Success: {ctx.workspace_id}"
    else:
        print(f"  ❌ 上下文为 None")
        return "Error: Context is None"

print(f"调用工具...")
result = test_tool_simple.invoke({})
print(f"工具返回: {result}\n")

print("=" * 60)
print("测试 3: 使用 require_context")
print("=" * 60)

@tool
def test_tool_require() -> str:
    """测试工具 - 使用 require_context"""
    try:
        ctx = require_context()
        print(f"  ✅ require_context 成功: {ctx.workspace_id}")
        return f"Success: {ctx.workspace_id}"
    except Exception as e:
        print(f"  ❌ require_context 失败: {e}")
        return f"Error: {str(e)}"

print(f"调用工具...")
result = test_tool_require.invoke({})
print(f"工具返回: {result}\n")

print("=" * 60)
print("测试 4: 在新线程中调用工具")
print("=" * 60)

def worker():
    print(f"  子线程 ID: {threading.get_ident()}")
    print(f"  子线程上下文: {get_context()}")
    
    result = test_tool_require.invoke({})
    print(f"  工具返回: {result}")

thread = threading.Thread(target=worker)
thread.start()
thread.join()
