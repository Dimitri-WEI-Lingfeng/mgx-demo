"""MessageDAO 单测，重点测试 get_session_messages_paginated。"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture(autouse=True)
def add_src_to_path():
    """确保 src 在 Python 路径中。"""
    import sys
    from pathlib import Path

    src = Path(__file__).parent.parent / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def _make_msg(session_id: str, message_id: str, role: str, content: str, timestamp: float):
    """构造消息文档。"""
    return {
        "message_id": message_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "timestamp": timestamp,
        "tool_calls": None,
        "tool_call_id": None,
        "parent_id": None,
        "agent_name": None,
        "cause_by": None,
        "sent_from": None,
        "send_to": [],
        "trace_id": None,
        "metadata": {},
    }


@pytest.mark.asyncio
class TestGetSessionMessagesPaginated:
    """测试 MessageDAO.get_session_messages_paginated。"""

    async def test_last_message_id_none_returns_recent_n(self):
        """last_message_id 为 None 时，返回最近的 n 条消息（按时间正序）。"""
        from mgx_api.dao import MessageDAO

        session_id = "sess-1"
        # DAO 内部 sort(timestamp, -1) 返回从新到旧，reversed 后变正序
        msgs_desc = [
            _make_msg(session_id, "msg-3", "user", "bye", 102.0),
            _make_msg(session_id, "msg-2", "assistant", "hello", 101.0),
            _make_msg(session_id, "msg-1", "user", "hi", 100.0),
        ]

        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.limit = MagicMock(return_value=mock_cursor)
        mock_cursor.to_list = AsyncMock(return_value=msgs_desc)

        mock_collection = MagicMock()
        mock_collection.find = MagicMock(return_value=mock_cursor)

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        with patch("mgx_api.dao.message_dao.get_db", return_value=mock_db):
            dao = MessageDAO()
            result = await dao.get_session_messages_paginated(
                session_id=session_id,
                limit=3,
                last_message_id=None,
            )

        assert len(result) == 3
        assert result[0].message_id == "msg-1"
        assert result[1].message_id == "msg-2"
        assert result[2].message_id == "msg-3"
        mock_collection.find.assert_called_once_with({"session_id": session_id})
        mock_cursor.sort.assert_called_once_with("timestamp", -1)
        mock_cursor.limit.assert_called_once_with(3)

    async def test_last_message_id_valid_returns_from_that_point(self):
        """last_message_id 有效时，返回从该消息开始的 n 条。"""
        from mgx_api.dao import MessageDAO

        session_id = "sess-1"
        find_one_result = _make_msg(session_id, "msg-2", "assistant", "hello", 101.0)
        msgs_from_cursor = [
            _make_msg(session_id, "msg-2", "assistant", "hello", 101.0),
            _make_msg(session_id, "msg-3", "user", "bye", 102.0),
        ]

        mock_find_one = AsyncMock(return_value=find_one_result)

        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.limit = MagicMock(return_value=mock_cursor)
        mock_cursor.to_list = AsyncMock(return_value=msgs_from_cursor)

        mock_collection = MagicMock()
        mock_collection.find_one = mock_find_one
        mock_collection.find = MagicMock(return_value=mock_cursor)

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        with patch("mgx_api.dao.message_dao.get_db", return_value=mock_db):
            dao = MessageDAO()
            result = await dao.get_session_messages_paginated(
                session_id=session_id,
                limit=5,
                last_message_id="msg-2",
            )

        assert len(result) == 2
        assert result[0].message_id == "msg-2"
        assert result[1].message_id == "msg-3"
        mock_find_one.assert_called_once_with(
            {"session_id": session_id, "message_id": "msg-2"}
        )
        mock_collection.find.assert_called_once_with(
            {"session_id": session_id, "timestamp": {"$gte": 101.0}}
        )
        mock_cursor.sort.assert_called_once_with("timestamp", 1)

    async def test_last_message_id_not_found_fallback_to_recent_n(self):
        """last_message_id 对应消息不存在时，fallback 到最近 n 条。"""
        from mgx_api.dao import MessageDAO

        session_id = "sess-1"
        # fallback 同样用 sort -1，to_list 返回从新到旧
        msgs_desc = [
            _make_msg(session_id, "msg-2", "assistant", "hello", 101.0),
            _make_msg(session_id, "msg-1", "user", "hi", 100.0),
        ]

        mock_find_one = AsyncMock(return_value=None)

        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.limit = MagicMock(return_value=mock_cursor)
        mock_cursor.to_list = AsyncMock(return_value=msgs_desc)

        mock_collection = MagicMock()
        mock_collection.find_one = mock_find_one
        mock_collection.find = MagicMock(return_value=mock_cursor)

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        with patch("mgx_api.dao.message_dao.get_db", return_value=mock_db):
            dao = MessageDAO()
            result = await dao.get_session_messages_paginated(
                session_id=session_id,
                limit=5,
                last_message_id="msg-nonexistent",
            )

        assert len(result) == 2
        assert result[0].message_id == "msg-1"
        assert result[1].message_id == "msg-2"
        mock_find_one.assert_called_once_with(
            {"session_id": session_id, "message_id": "msg-nonexistent"}
        )
        mock_collection.find.assert_called_once_with({"session_id": session_id})
        mock_cursor.sort.assert_called_once_with("timestamp", -1)

    async def test_empty_session_returns_empty_list(self):
        """会话无消息时返回空列表。"""
        from mgx_api.dao import MessageDAO

        session_id = "sess-empty"

        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.limit = MagicMock(return_value=mock_cursor)
        mock_cursor.to_list = AsyncMock(return_value=[])

        mock_collection = MagicMock()
        mock_collection.find = MagicMock(return_value=mock_cursor)

        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)

        with patch("mgx_api.dao.message_dao.get_db", return_value=mock_db):
            dao = MessageDAO()
            result = await dao.get_session_messages_paginated(
                session_id=session_id,
                limit=10,
                last_message_id=None,
            )

        assert result == []
