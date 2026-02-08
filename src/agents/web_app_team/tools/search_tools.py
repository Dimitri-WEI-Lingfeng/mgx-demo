"""搜索工具 - 代码搜索、Web 搜索等。"""

import asyncio
import os
import re
import traceback
from pathlib import Path

from langchain.tools import tool


def _search_web_sync(query: str) -> str:
    """同步执行 Web 搜索（供 to_thread 使用）。"""
    from tavily import TavilyClient

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "未配置 TAVILY_API_KEY，无法使用 Web 搜索功能"

    client = TavilyClient(api_key=api_key)
    response = client.search(query, max_results=3)

    results = []
    for item in response.get("results", []):
        title = item.get("title", "无标题")
        content = item.get("content", "")
        url = item.get("url", "")
        results.append(f"标题: {title}\nURL: {url}\n内容: {content}\n")

    if not results:
        return "未找到相关搜索结果"

    return "\n---\n".join(results)


@tool
async def search_web(query: str) -> str:
    """使用搜索引擎搜索 Web 内容。
    
    适用于查询最新的技术文档、解决方案、讨论等。

    Args:
        query: 搜索查询，例如"Next.js 14 app router 使用"、"FastAPI WebSocket 示例"

    Returns:
        搜索结果摘要
    """
    # 检查是否启用 Web 搜索
    enable_web_search = os.getenv("ENABLE_WEB_SEARCH", "false").lower() == "true"

    if not enable_web_search:
        return "Web 搜索功能未启用。请设置 ENABLE_WEB_SEARCH=true 并配置 TAVILY_API_KEY。"

    try:
        return await asyncio.to_thread(_search_web_sync, query)
    except ImportError:
        return "未安装 tavily-python 包，无法使用 Web 搜索。请运行：pip install tavily-python"
    except Exception as e:
        traceback.print_exc()
        return f"Web 搜索失败：{str(e)}"


def _find_files_by_name_sync(filename_pattern: str) -> str:
    """同步按文件名查找（供 to_thread 使用）。"""
    from agents.web_app_team.tools.workspace_tools import _get_workspace_path

    workspace_path = _get_workspace_path("")
    matches = []
    for file_path in workspace_path.rglob(filename_pattern):
        if file_path.is_file():
            rel_path = file_path.relative_to(workspace_path)
            matches.append(str(rel_path))
    if not matches:
        return f"未找到匹配 '{filename_pattern}' 的文件"
    return "\n".join(matches)


@tool
async def find_files_by_name(filename_pattern: str) -> str:
    """在 workspace 中按文件名查找文件。
    
    Args:
        filename_pattern: 文件名模式（支持通配符），例如 "*.tsx", "test_*.py"
    
    Returns:
        匹配的文件路径列表
    """
    try:
        return await asyncio.to_thread(_find_files_by_name_sync, filename_pattern)
    except Exception as e:
        traceback.print_exc()
        return f"查找文件失败：{str(e)}"


def _analyze_file_structure_sync(directory: str) -> str:
    """同步分析目录结构（供 to_thread 使用）。"""
    from agents.web_app_team.tools.workspace_tools import _get_workspace_path

    dir_path = _get_workspace_path(directory)
    if not dir_path.exists() or not dir_path.is_dir():
        return f"错误：目录 {directory} 不存在"

    def build_tree(path: Path, prefix: str = "", max_depth: int = 3, current_depth: int = 0) -> list[str]:
        if current_depth >= max_depth:
            return []
        lines = []
        items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
        for i, item in enumerate(items):
            if item.name.startswith(".") or item.name in ["node_modules", "__pycache__", "dist", "build"]:
                continue
            is_last = i == len(items) - 1
            current_prefix = "└── " if is_last else "├── "
            next_prefix = "    " if is_last else "│   "
            if item.is_dir():
                lines.append(f"{prefix}{current_prefix}{item.name}/")
                lines.extend(build_tree(item, prefix + next_prefix, max_depth, current_depth + 1))
            else:
                lines.append(f"{prefix}{current_prefix}{item.name}")
        return lines

    tree_lines = [f"{dir_path.name}/"] + build_tree(dir_path)
    return "\n".join(tree_lines)


@tool
async def analyze_file_structure(directory: str = ".") -> str:
    """分析目录结构，返回层级树形视图。
    
    Args:
        directory: 要分析的目录（相对于 workspace 根目录）
    
    Returns:
        目录树形结构
    """
    try:
        return await asyncio.to_thread(_analyze_file_structure_sync, directory)
    except Exception as e:
        traceback.print_exc()
        return f"分析目录结构失败：{str(e)}"
