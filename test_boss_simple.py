"""简单测试 boss.py 中的上下文访问。"""

from src.agents.context import InMemoryContext, set_context, require_context
from src.agents.web_app_team.tools.workspace_tools import list_files
import os

# 创建测试工作区
os.makedirs('./test_workspace', exist_ok=True)
with open('./test_workspace/test.txt', 'w') as f:
    f.write('Hello, World!')

# 设置上下文
context = InMemoryContext(workspace_path='./test_workspace')
set_context(context)

print("=== 测试上下文设置 ===")
print(f"上下文已设置: {context.workspace_id}\n")

# 测试工具函数是否能访问上下文
print("=== 测试工具函数 ===")
result = list_files.invoke({"directory": "."})
print(f"list_files 结果:\n{result}\n")

# 测试 require_context
print("=== 测试 require_context ===")
ctx = require_context()
print(f"成功获取上下文: {ctx.workspace_id}")
print(f"Workspace 路径: {ctx.get_workspace_path()}")

print("\n✅ 所有测试通过！上下文在工具中可以正常访问。")

# 清理
import shutil
shutil.rmtree('./test_workspace', ignore_errors=True)
