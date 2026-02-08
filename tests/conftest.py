"""Pytest fixtures for MGX tests."""

import tempfile
from pathlib import Path

import pytest

# Ensure src is on path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def temp_workspace():
    """创建临时工作区目录。"""
    with tempfile.TemporaryDirectory(prefix="mgx-test-workspace-") as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def memory_context(temp_workspace):
    """创建使用临时目录的 InMemoryContext。"""
    from agents.context import InMemoryContext

    context = InMemoryContext(
        session_id="test-session",
        workspace_id="test-workspace",
        workspace_path=temp_workspace,
    )
    return context


@pytest.fixture
def agent_context(memory_context):
    """设置并返回 agent 上下文（用于需要 get_context 的测试）。"""
    from agents.context import set_context, clear_context

    set_context(memory_context)
    yield memory_context
    clear_context()
