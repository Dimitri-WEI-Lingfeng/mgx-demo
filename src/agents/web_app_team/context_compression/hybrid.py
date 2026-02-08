"""混合压缩策略。"""

from typing import Any
from langchain_openai import ChatOpenAI
from agents.web_app_team.context_compression.base import ContextCompressionStrategy
from agents.web_app_team.context_compression.sliding_window import SlidingWindowStrategy
from agents.web_app_team.context_compression.key_extraction import KeyExtractionStrategy
from agents.web_app_team.context_compression.summarization import SummarizationStrategy


class HybridStrategy(ContextCompressionStrategy):
    """混合压缩策略。
    
    结合多种策略的优点：
    1. 保留最近 N 条消息（滑动窗口）
    2. 提取旧消息中的关键信息（关键提取）
    3. 对剩余消息进行摘要（摘要）
    
    适用场景：
    - 长时间协作任务
    - 需要平衡信息保留和成本
    
    优点：
    - 信息保留较完整
    - 平衡效果和成本
    
    缺点：
    - 实现较复杂
    - 仍需 LLM 调用成本
    """
    
    def __init__(
        self,
        llm: ChatOpenAI = None,
        recent_window: int = 15,
        key_patterns: list[str] = None,
        summary_model: str = "gpt-4o-mini"
    ):
        """初始化混合压缩策略。
        
        Args:
            llm: 用于摘要的 LLM
            recent_window: 保留最近消息的数量
            key_patterns: 关键信息模式列表
            summary_model: 摘要模型
        """
        self.recent_window = recent_window
        self.key_extractor = KeyExtractionStrategy(key_patterns, min_recent=0)
        self.summarizer = SummarizationStrategy(llm, summary_model, recent_window=0)
        self.window_strategy = SlidingWindowStrategy(recent_window)
    
    def compress_messages(
        self, 
        messages: list[dict],
        max_tokens: int = 4000
    ) -> list[dict]:
        """使用混合策略压缩消息。
        
        Strategy:
        1. 如果消息数量在窗口内，直接返回
        2. 保留最近的消息
        3. 从旧消息中提取关键信息
        4. 如果仍然超过限制，对关键信息进行摘要
        
        Args:
            messages: 消息列表
            max_tokens: 最大 token 数
        
        Returns:
            压缩后的消息列表
        """
        # 如果在窗口内，直接返回
        if len(messages) <= self.recent_window:
            return messages
        
        # 1. 分离最近消息和旧消息
        recent = messages[-self.recent_window:]
        old = messages[:-self.recent_window]
        
        # 2. 从旧消息中提取关键信息
        key_messages = []
        for msg in old:
            if self.key_extractor._contains_key_info(msg.get("content", "")):
                key_messages.append(msg)
        
        # 3. 合并关键消息和最近消息
        combined = key_messages + recent
        
        # 4. 检查 token 数
        current_tokens = self.estimate_message_tokens(combined)
        
        if current_tokens <= max_tokens:
            return combined
        
        # 5. 如果还是太长，对关键消息进行摘要
        if key_messages:
            summary = self.summarizer._summarize_messages(key_messages)
            return [
                {"role": "system", "content": f"历史关键信息摘要：\n{summary}"},
                *recent
            ]
        else:
            # 没有关键消息，只返回最近的
            return recent
    
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
        # 使用关键提取策略的状态压缩
        return self.key_extractor.compress_state(state, priority_keys)
