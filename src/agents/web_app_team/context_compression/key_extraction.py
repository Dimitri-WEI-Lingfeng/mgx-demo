"""关键信息提取压缩策略。"""

import re
from typing import Any
from agents.web_app_team.context_compression.base import ContextCompressionStrategy


class KeyExtractionStrategy(ContextCompressionStrategy):
    """关键信息提取策略。
    
    基于规则提取关键信息（决策、文档路径、错误等）。
    
    适用场景：
    - 结构化信息为主
    - 需要保留关键决策和文档
    
    优点：
    - 精确保留重要信息
    - 不依赖 LLM，成本低
    
    缺点：
    - 需要预定义规则
    - 可能遗漏未定义的重要信息
    """
    
    def __init__(self, key_patterns: list[str] = None, min_recent: int = 10):
        """初始化关键信息提取策略。
        
        Args:
            key_patterns: 关键信息的正则表达式模式列表
            min_recent: 至少保留的最近消息数量
        """
        self.key_patterns = key_patterns or [
            r'PRD:.*',
            r'设计文档:.*',
            r'错误:.*',
            r'错误输出:.*',
            r'决策:.*',
            r'文件路径:.*',
            r'requirements\.md',
            r'prd\.md',
            r'design\.md',
            r'tasks\.md',
            r'成功：已写入',
            r'退出码:',
        ]
        self.min_recent = min_recent
    
    def _contains_key_info(self, content: str) -> bool:
        """检查内容是否包含关键信息。
        
        Args:
            content: 消息内容
        
        Returns:
            是否包含关键信息
        """
        if not content:
            return False
        
        for pattern in self.key_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False
    
    def compress_messages(
        self, 
        messages: list[dict],
        max_tokens: int = 4000
    ) -> list[dict]:
        """压缩消息历史，提取关键信息。
        
        Args:
            messages: 消息列表
            max_tokens: 最大 token 数
        
        Returns:
            包含关键信息的消息
        """
        if len(messages) <= self.min_recent:
            return messages
        
        # 提取包含关键信息的消息
        key_messages = []
        for msg in messages[:-self.min_recent]:  # 不包括最近的消息
            content = msg.get("content", "")
            if self._contains_key_info(content):
                key_messages.append(msg)
        
        # 始终保留最近的消息
        recent_messages = messages[-self.min_recent:]
        
        # 合并关键消息和最近消息
        compressed = key_messages + recent_messages
        
        # 如果还是超过限制，只保留最近的
        current_tokens = self.estimate_message_tokens(compressed)
        if current_tokens > max_tokens:
            return recent_messages
        
        return compressed
    
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
        # 关键状态字段
        essential_keys = [
            'workspace_id', 
            'framework', 
            'current_stage',
            'prd_document',
            'design_document',
            'tasks',
        ]
        
        if priority_keys:
            essential_keys.extend(priority_keys)
        
        keys_to_keep = set(essential_keys)
        
        return {k: v for k, v in state.items() if k in keys_to_keep}
