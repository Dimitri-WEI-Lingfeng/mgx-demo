"""滑动窗口压缩策略。"""

from typing import Any
from agents.web_app_team.context_compression.base import ContextCompressionStrategy


class SlidingWindowStrategy(ContextCompressionStrategy):
    """滑动窗口压缩策略。
    
    保留最近 N 条消息，丢弃旧消息。
    
    适用场景：
    - 快速迭代、短期记忆足够
    - 不需要保留完整历史
    
    优点：
    - 简单高效，无额外成本
    - 实时性好
    
    缺点：
    - 可能丢失重要历史信息
    - 不适合需要长期上下文的任务
    """
    
    def __init__(self, window_size: int = 20):
        """初始化滑动窗口策略。
        
        Args:
            window_size: 窗口大小（保留最近 N 条消息）
        """
        self.window_size = window_size
    
    def compress_messages(
        self, 
        messages: list[dict],
        max_tokens: int = 4000
    ) -> list[dict]:
        """压缩消息历史，只保留最近的消息。
        
        Args:
            messages: 消息列表
            max_tokens: 最大 token 数（本策略不使用此参数）
        
        Returns:
            最近的 N 条消息
        """
        if len(messages) <= self.window_size:
            return messages
        
        return messages[-self.window_size:]
    
    def compress_state(
        self,
        state: dict[str, Any],
        priority_keys: list[str] = None
    ) -> dict[str, Any]:
        """压缩状态数据，保留优先级高的字段。
        
        Args:
            state: 状态字典
            priority_keys: 优先保留的字段列表
        
        Returns:
            压缩后的状态
        """
        # 必须保留的字段
        essential_keys = ['workspace_id', 'framework', 'current_stage']
        
        if not priority_keys:
            priority_keys = []
        
        # 合并必须字段和优先字段
        keys_to_keep = set(essential_keys + priority_keys)
        
        return {k: v for k, v in state.items() if k in keys_to_keep}
