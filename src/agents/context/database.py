"""数据库模式上下文实现 - 用于生产环境。"""

from pathlib import Path
from typing import Any

from .base import AgentContext, EventStore, MessageStore
from shared.config import settings
from shared.utils import safe_join
from shared.schemas import Event, Message


class DatabaseEventStore(EventStore):
    """数据库事件存储（包装 EventDAO）。"""
    
    def __init__(self, session_id: str):
        from mgx_api.dao import EventDAO
        self.session_id = session_id
        self.dao = EventDAO()
    
    async def create_event(self, event: Any) -> Any:
        """创建事件（写入数据库）。"""
        return await self.dao.create_event(event)


class DatabaseMessageStore(MessageStore):
    """数据库消息存储（包装 MessageDAO）。"""
    
    def __init__(self, session_id: str):
        from mgx_api.dao import MessageDAO
        self.session_id = session_id
        self.dao = MessageDAO()
    
    async def create_message(self, message: Any) -> Any:
        """创建消息（写入数据库）。"""
        return await self.dao.create_message(message)

    async def get_session_messages_paginated(
        self,
        session_id: str,
        limit: int = 100,
        last_message_id: str | None = None,
        before_message_id: str | None = None,
    ) -> list[Message]:
        """分页获取会话消息（委托给 DAO）。"""
        return await self.dao.get_session_messages_paginated(
            session_id=session_id,
            limit=limit,
            last_message_id=last_message_id,
            before_message_id=before_message_id,
        )


class DatabaseContext(AgentContext):
    """数据库模式上下文 - 用于生产环境。
    
    特点：
    - 使用数据库存储事件和消息
    - 包装现有的 DAO 层
    - Workspace 路径使用配置的根目录
    - 适合生产部署
    """
    
    def __init__(self, session_id: str, workspace_id: str):
        """初始化数据库上下文。
        
        Args:
            session_id: Session ID
            workspace_id: Workspace ID
        """
        super().__init__(session_id, workspace_id)
        
        # 初始化存储
        self._event_store = DatabaseEventStore(session_id)
        self._message_store = DatabaseMessageStore(session_id)
        
        print(f"\n=== 数据库模式上下文已初始化 ===")
        print(f"Session ID: {self.session_id}")
        print(f"Workspace ID: {self.workspace_id}")
        print(f"================================\n")
    
    @property
    def event_store(self) -> EventStore:
        """获取事件存储。"""
        return self._event_store
    
    @property
    def message_store(self) -> MessageStore:
        """获取消息存储。"""
        return self._message_store
    
    def get_workspace_path(self, relative_path: str = "") -> Path:
        """获取 workspace 中文件的完整路径（Agent 容器内路径）。"""
        workspace_root = Path(settings.agent_workspace_root_in_container)
        return safe_join(workspace_root, relative_path)
    
    def get_container_name(self) -> str:
        """获取 Docker 容器名称。"""
        return f"mgx-dev-{self.workspace_id}"
