"""各个 Agent 的提示词模板。"""

WORKSPACE_ROOT_CONSTRAINT = """
## Workspace 根目录约束（重要）
- 所有项目相关文件（文档、代码、配置）必须位于 workspace 根目录内
- 文件操作工具（read_file、write_file、list_files 等）的路径参数均**相对于 workspace 根目录**
- 正确示例：prd.md、design.md、tasks.md、frontend/src/App.tsx、backend/api/main.py
- 禁止：使用绝对路径（如 /home/xxx）、或指向 workspace 外的路径
- 根目录可用 "." 表示，如 list_files(".") 列出根目录
"""

__all__ = ["WORKSPACE_ROOT_CONSTRAINT"]
