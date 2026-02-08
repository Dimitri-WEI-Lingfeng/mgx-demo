"""上下文抽象基类。"""

from abc import ABC, abstractmethod
from typing import Any
from pathlib import Path
from shared.schemas import Event, Message


class EventStore(ABC):
    """事件存储抽象接口。"""
    
    @abstractmethod
    async def create_event(self, event: "Event") -> Any:
        """创建事件。
        
        Args:
            event: Event 实例
        
        Returns:
            事件对象或ID
        """
        pass


class MessageStore(ABC):
    """消息存储抽象接口。"""
    
    @abstractmethod
    async def create_message(self, message: "Message") -> Any:
        """创建消息。
        
        Args:
            message: Message 实例
        
        Returns:
            消息对象或ID
        """
        pass


class AgentContext(ABC):
    """Agent 上下文抽象基类。
    
    提供统一的接口来管理 session、workspace 和存储。
    """
    
    def __init__(self, session_id: str, workspace_id: str):
        """初始化上下文。
        
        Args:
            session_id: Session ID
            workspace_id: Workspace ID
        """
        self.session_id = session_id
        self.workspace_id = workspace_id
    
    @property
    @abstractmethod
    def event_store(self) -> EventStore:
        """获取事件存储。"""
        pass
    
    @property
    @abstractmethod
    def message_store(self) -> MessageStore:
        """获取消息存储。"""
        pass
    
    @abstractmethod
    def get_workspace_path(self, relative_path: str = "") -> Path:
        """获取 workspace 中文件的完整路径。
        
        Args:
            relative_path: 相对路径
        
        Returns:
            绝对路径
        """
        pass
    
    @abstractmethod
    def get_container_name(self) -> str:
        """获取 Docker 容器名称。
        
        Returns:
            容器名称
        """
        pass
