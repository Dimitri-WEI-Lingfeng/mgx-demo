"""Workspace 文件操作工具。

基于现有的 WorkspaceService 实现，为 agent 提供文件读写能力。
"""

import asyncio
import traceback
from pathlib import Path

import aiofiles
import loguru
from langchain.tools import tool


def _get_workspace_path(relative_path: str = "") -> Path:
    """获取workspace中文件的完整路径。
    
    Args:
        relative_path: 相对于 workspace 根目录的路径
    
    Returns:
        安全的绝对路径
    
    Raises:
        RuntimeError: 如果上下文未设置
        ValueError: 如果路径试图逃逸 workspace
    """
    from agents.context import require_context
    
    context = require_context()
    return context.get_workspace_path(relative_path)


@tool
async def read_file(path: str) -> str:
    """读取 workspace 中的文件内容。

    Args:
        path: 相对于 workspace 根目录的文件路径，例如 "README.md" 或 "src/main.py"

    Returns:
        文件内容
    """
    try:
        file_path = _get_workspace_path(path)

        if not file_path.exists():
            return f"错误：文件 {path} 不存在"

        if not file_path.is_file():
            return f"错误：{path} 不是一个文件"

        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            content = await f.read()
        loguru.logger.info(f"读取文件 {file_path} 成功")
        return content

    except ValueError as e:
        return f"错误：{str(e)}"
    except Exception as e:
        traceback.print_exc()
        return f"错误：读取文件失败 - {str(e)}"


@tool
async def write_file(path: str, content: str) -> str:
    """写入内容到 workspace 中的文件。

    Args:
        path: 相对于 workspace 根目录的文件路径
        content: 要写入的内容

    Returns:
        成功消息或错误信息
    """
    try:
        file_path = _get_workspace_path(path)

        # 确保父目录存在
        file_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(content)

        size = file_path.stat().st_size
        loguru.logger.success(f"已写入 {size} 字节到 {file_path}")
        return f"成功：已写入 {size} 字节到 {path}"

    except ValueError as e:
        return f"错误：{str(e)}"
    except Exception as e:
        traceback.print_exc()
        return f"错误：写入文件失败 - {str(e)}"


def _list_files_sync(directory: str) -> str:
    """同步列出目录（供 to_thread 使用）。"""
    dir_path = _get_workspace_path(directory)
    if not dir_path.exists():
        return f"错误：目录 {directory} 不存在"
    if not dir_path.is_dir():
        return f"错误：{directory} 不是一个目录"
    entries = []
    for item in sorted(dir_path.iterdir()):
        if item.name.startswith("."):
            continue
        if item.is_dir():
            entries.append(f"[目录] {item.name}/")
        else:
            size = item.stat().st_size
            entries.append(f"[文件] {item.name} ({size} 字节)")
    if not entries:
        return f"目录 {directory} 为空"
    return "\n".join(entries)


@tool
async def list_files(directory: str = ".") -> str:
    """列出 workspace 中指定目录的文件和子目录。

    Args:
        directory: 相对于 workspace 根目录的目录路径，默认为根目录

    Returns:
        文件和目录列表（每行一个）
    """
    try:
        return await asyncio.to_thread(_list_files_sync, directory)
    except ValueError as e:
        loguru.logger.error(e)
        return f"错误：{str(e)}"
    except Exception as e:
        traceback.print_exc()
        loguru.logger.error(e)
        return f"错误：列出文件失败 - {str(e)}"


@tool
async def delete_file(path: str) -> str:
    """删除 workspace 中的文件。
    
    Args:
        path: 相对于 workspace 根目录的文件路径
    
    Returns:
        成功消息或错误信息
    """
    try:
        def _delete_sync():
            file_path = _get_workspace_path(path)
            if not file_path.exists():
                return f"错误：文件 {path} 不存在"
            if not file_path.is_file():
                return f"错误：{path} 不是一个文件"
            file_path.unlink()
            return f"成功：已删除 {path}"

        return await asyncio.to_thread(_delete_sync)
    except ValueError as e:
        return f"错误：{str(e)}"
    except Exception as e:
        traceback.print_exc()
        return f"错误：删除文件失败 - {str(e)}"


@tool
async def create_directory(path: str) -> str:
    """在 workspace 中创建目录。
    
    Args:
        path: 相对于 workspace 根目录的目录路径
    
    Returns:
        成功消息或错误信息
    """
    try:
        def _create_sync():
            dir_path = _get_workspace_path(path)
            if dir_path.exists():
                return f"目录 {path} 已存在"
            dir_path.mkdir(parents=True, exist_ok=True)
            return f"成功：已创建目录 {path}"

        return await asyncio.to_thread(_create_sync)
    except ValueError as e:
        return f"错误：{str(e)}"
    except Exception as e:
        traceback.print_exc()
        return f"错误：创建目录失败 - {str(e)}"


@tool
async def search_in_files(pattern: str, directory: str = ".", file_extension: str = None) -> str:
    """在 workspace 的文件中搜索文本模式。

    Args:
        pattern: 要搜索的文本模式（支持正则表达式）
        directory: 要搜索的目录，默认为根目录
        file_extension: 可选的文件扩展名过滤（如 ".py", ".tsx"）

    Returns:
        匹配结果，每行显示文件名、行号和匹配的内容
    """
    import re

    try:
        dir_path = _get_workspace_path(directory)

        if not dir_path.exists() or not dir_path.is_dir():
            return f"错误：目录 {directory} 不存在"

        matches = []
        pattern_re = re.compile(pattern)

        # 递归搜索文件
        for file_path in dir_path.rglob("*"):
            # 跳过目录和隐藏文件
            if not file_path.is_file() or file_path.name.startswith("."):
                continue

            # 过滤文件扩展名
            if file_extension and file_path.suffix != file_extension:
                continue

            try:
                async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                    content = await f.read()
                for line_num, line in enumerate(content.splitlines(), 1):
                    if pattern_re.search(line):
                        rel_path = file_path.relative_to(dir_path.parent)
                        matches.append(f"{rel_path}:{line_num}: {line.strip()}")

                        # 限制结果数量
                        if len(matches) >= 50:
                            matches.append("... (结果太多，已截断)")
                            return "\n".join(matches)
            except (UnicodeDecodeError, PermissionError):
                # 跳过无法读取的文件（如二进制文件），无需 traceback
                continue

        if not matches:
            return f"未找到匹配 '{pattern}' 的内容"

        return "\n".join(matches)

    except ValueError as e:
        traceback.print_exc()
        return f"错误：{str(e)}"
    except re.error as e:
        traceback.print_exc()
        return f"错误：无效的正则表达式 - {str(e)}"
    except Exception as e:
        traceback.print_exc()
        return f"错误：搜索失败 - {str(e)}"
