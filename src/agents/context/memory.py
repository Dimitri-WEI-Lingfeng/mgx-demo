"""内存模式上下文实现 - 用于本地开发和测试。"""

import traceback
from pathlib import Path
from typing import Any
from datetime import datetime
import uuid
import asyncio

from shared.config.docker_images import get_framework_docker_image

from .base import AgentContext, EventStore, MessageStore
from shared.config import settings
from shared.utils import safe_join
import loguru
from shared.schemas import Event, Message


class InMemoryEventStore(EventStore):
    """内存事件存储。"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.events: list[dict] = []
    
    async def create_event(self, event: Event) -> dict:
        """创建事件（存储在内存中）。"""
        event_dict = event.model_dump()
        self.events.append(event_dict)
        
        # 打印事件日志便于调试
        event_type = event.event_type.value if hasattr(event.event_type, 'value') else event.event_type
        data = event.data
        print(f"[EVENT] {event_type}: {data.get('status', '')} {data.get('prompt', '')[:50] if data.get('prompt') else ''}")
        
        return event_dict
    
    def get_events(self) -> list[dict]:
        """获取所有事件。"""
        return self.events.copy()


class InMemoryMessageStore(MessageStore):
    """内存消息存储。"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.messages: list[dict] = []
    
    async def create_message(self, message: Message) -> dict:
        """创建消息（存储在内存中）。"""
        message_dict = message.model_dump()
        self.messages.append(message_dict)
        
        # 打印消息日志便于调试
        content = message.content
        content_preview = content[:100] + "..." if len(content) > 100 else content
        print(f"[MESSAGE] {message.role}: {content_preview}")
        
        return message_dict
    
    def get_messages(self) -> list[dict]:
        """获取所有消息。"""
        return self.messages.copy()


class InMemoryContext(AgentContext):
    """内存模式上下文 - 用于本地开发。
    
    特点：
    - 不需要数据库连接
    - 事件和消息存储在内存中
    - Workspace 路径可以指向本地目录
    - 适合快速开发和测试
    - 支持临时 Docker container 的自动创建和销毁
    """
    
    def __init__(
        self,
        session_id: str | None = None,
        workspace_id: str | None = None,
        workspace_path: str | Path | None = None,
        auto_create_container: bool = False,
        framework: str = 'nextjs'
    ):
        """初始化内存上下文。
        
        Args:
            session_id: Session ID（如果不提供则自动生成）
            workspace_id: Workspace ID（如果不提供则自动生成）
            workspace_path: Workspace 路径（如果不提供则使用默认路径）
            auto_create_container: 是否自动创建临时 Docker container
        """
        # 生成默认 ID
        if session_id is None:
            session_id = f"local-session-{uuid.uuid4().hex[:8]}"
        if workspace_id is None:
            workspace_id = f"local-workspace-{uuid.uuid4().hex[:8]}"
        
        super().__init__(session_id, workspace_id)
        self._framework_docker_image = get_framework_docker_image(framework)
        # 初始化存储
        self._event_store = InMemoryEventStore(session_id)
        self._message_store = InMemoryMessageStore(session_id)
        
        # 设置 workspace 路径
        if workspace_path:
            self._workspace_root = Path(workspace_path)
        else:
            self._workspace_root = Path(settings.workspaces_root) / workspace_id
        
        # 确保 workspace 目录存在
        self._workspace_root.mkdir(parents=True, exist_ok=True)
        
        # Container 管理
        self._auto_create_container = auto_create_container
        self._container_created = False
        self._container_name = f"mgx-dev-{self.workspace_id}"
        
        print(f"\n=== 内存模式上下文已初始化 ===")
        print(f"Session ID: {self.session_id}")
        print(f"Workspace ID: {self.workspace_id}")
        print(f"Workspace Path: {self._workspace_root}")
        print(f"Auto Create Container: {self._auto_create_container}")
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
        """获取 workspace 中文件的完整路径。"""
        return safe_join(self._workspace_root, relative_path)
    
    def get_container_name(self) -> str:
        """获取 Docker 容器名称。"""
        return self._container_name
    
    async def _create_container(self) -> None:
        """创建临时 Docker container。"""
        if self._container_created:
            return
        
        container_name = self._container_name
        loguru.logger.info(f"\n[Container] 创建临时容器: {container_name}")
        
        try:
            # 检查容器是否已存在
            check_cmd = f"docker ps -a --filter name={container_name} --format '{{{{.Names}}}}'"
            result = await asyncio.create_subprocess_shell(
                check_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()
            
            if stdout.decode().strip():
                loguru.logger.info(f"[Container] 容器 {container_name} 已存在，先删除...")
                await self._destroy_container()
            
            # 创建并启动容器
            # 这里使用一个基础镜像，实际项目中可能需要自定义镜像
            create_cmd = f"""docker run -d \
                --name {container_name} \
                --rm \
                -v {self._workspace_root}:/workspace \
                -w /workspace \
                {self._framework_docker_image} \
                tail -f /dev/null"""
            
            result = await asyncio.create_subprocess_shell(
                create_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                error_msg = stderr.decode() if stderr else "未知错误"
                loguru.logger.error(f"[Container] 创建容器失败: {error_msg}")
                raise RuntimeError(f"创建容器失败: {error_msg}")
            
            self._container_created = True
            loguru.logger.info(f"[Container] 容器 {container_name} 创建成功 ✓")
            
        except Exception as e:
            loguru.logger.error(f"[Container] 创建容器时出错: {e}")
            traceback.print_exc()
            raise
    
    async def _destroy_container(self) -> None:
        """销毁临时 Docker container。"""
        if not self._container_created and not self._auto_create_container:
            return
        
        container_name = self._container_name
        print(f"\n[Container] 销毁容器: {container_name}")
        
        try:
            # 停止并删除容器
            stop_cmd = f"docker stop {container_name}"
            result = await asyncio.create_subprocess_shell(
                stop_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await result.communicate()
            
            # 如果使用了 --rm，容器会自动删除；否则需要手动删除
            remove_cmd = f"docker rm -f {container_name}"
            result = await asyncio.create_subprocess_shell(
                remove_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await result.communicate()
            
            self._container_created = False
            print(f"[Container] 容器 {container_name} 已销毁 ✓")
            
        except Exception as e:
            print(f"[Container] 销毁容器时出错: {e}")
            traceback.print_exc()
            # 不抛出异常，因为这是清理操作
    
    async def __aenter__(self):
        """进入异步上下文管理器时创建 container。"""
        if self._auto_create_container:
            await self._create_container()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出异步上下文管理器时销毁 container。"""
        if self._auto_create_container:
            await self._destroy_container()
        return False
    
    def get_events(self) -> list[dict]:
        """获取所有事件（便于调试和测试）。"""
        if isinstance(self._event_store, InMemoryEventStore):
            return self._event_store.get_events()
        return []
    
    def get_messages(self) -> list[dict]:
        """获取所有消息（便于调试和测试）。"""
        if isinstance(self._message_store, InMemoryMessageStore):
            return self._message_store.get_messages()
        return []
