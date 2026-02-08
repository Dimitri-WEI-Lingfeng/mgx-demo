"""上下文压缩策略抽象基类。"""

from abc import ABC, abstractmethod
from typing import Any


class ContextCompressionStrategy(ABC):
    """上下文压缩策略抽象基类。
    
    所有压缩策略都应继承这个基类并实现相应的方法。
    """
    
    @abstractmethod
    def compress_messages(
        self, 
        messages: list[dict],
        max_tokens: int = 4000
    ) -> list[dict]:
        """压缩消息历史。
        
        Args:
            messages: 消息列表，每个消息是 {"role": str, "content": str} 格式
            max_tokens: 最大 token 数限制
        
        Returns:
            压缩后的消息列表
        """
        pass
    
    @abstractmethod
    def compress_state(
        self,
        state: dict[str, Any],
        priority_keys: list[str] = None
    ) -> dict[str, Any]:
        """压缩状态数据。
        
        Args:
            state: 状态字典
            priority_keys: 优先保留的字段列表
        
        Returns:
            压缩后的状态
        """
        pass
    
    def estimate_tokens(self, text: str) -> int:
        """估算文本 token 数。
        
        简单实现：字符数 / 4
        更精确的实现可以使用 tiktoken 库。
        
        Args:
            text: 要估算的文本
        
        Returns:
            估算的 token 数量
        """
        if not text:
            return 0
        return len(text) // 4
    
    def estimate_message_tokens(self, messages: list[dict]) -> int:
        """估算消息列表的总 token 数。
        
        Args:
            messages: 消息列表
        
        Returns:
            总 token 数
        """
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += self.estimate_tokens(content)
        return total
