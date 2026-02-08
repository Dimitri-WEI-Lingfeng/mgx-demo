"""摘要压缩策略。"""

import traceback
from typing import Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from agents.web_app_team.context_compression.base import ContextCompressionStrategy


class SummarizationStrategy(ContextCompressionStrategy):
    """使用 LLM 摘要压缩上下文。
    
    使用 LLM 对历史消息进行摘要，保留关键信息。
    
    适用场景：
    - 长对话、多轮迭代
    - 需要保留语义信息
    
    优点：
    - 信息损失少
    - 语义连贯
    
    缺点：
    - 需要额外 LLM 调用，有成本
    - 增加延迟
    """
    
    def __init__(
        self, 
        llm: ChatOpenAI = None,
        summary_model: str = "gpt-4o-mini",
        recent_window: int = 10
    ):
        """初始化摘要压缩策略。
        
        Args:
            llm: 用于摘要的 LLM（如果不提供则创建新的）
            summary_model: 摘要使用的模型
            recent_window: 保留最近消息的数量
        """
        if llm is None:
            self.llm = ChatOpenAI(model=summary_model, temperature=0)
        else:
            self.llm = llm
        
        self.recent_window = recent_window
    
    def _summarize_messages(self, messages: list[dict]) -> str:
        """调用 LLM 生成消息摘要。
        
        Args:
            messages: 要摘要的消息列表
        
        Returns:
            摘要文本
        """
        if not messages:
            return ""
        
        # 构建摘要提示词
        messages_text = "\n\n".join([
            f"[{msg.get('role', 'unknown')}]: {msg.get('content', '')}"
            for msg in messages
        ])
        
        prompt = f"""请简要总结以下对话的关键信息，保留重要的决策、文档和结论：

{messages_text}

请用简洁的要点形式总结（每个要点一行）："""
        
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            return response.content
        except Exception as e:
            traceback.print_exc()
            # 如果摘要失败，返回简化的文本
            return f"历史对话包含 {len(messages)} 条消息（摘要失败：{str(e)}）"
    
    def compress_messages(
        self, 
        messages: list[dict],
        max_tokens: int = 4000
    ) -> list[dict]:
        """压缩消息历史，使用 LLM 摘要。
        
        Args:
            messages: 消息列表
            max_tokens: 最大 token 数
        
        Returns:
            压缩后的消息列表
        """
        # 计算当前 token 数
        current_tokens = self.estimate_message_tokens(messages)
        
        # 如果未超过限制，直接返回
        if current_tokens <= max_tokens:
            return messages
        
        # 保留最近的消息
        recent_messages = messages[-self.recent_window:]
        old_messages = messages[:-self.recent_window]
        
        if not old_messages:
            # 如果没有旧消息，只能返回最近的
            return recent_messages
        
        # 对旧消息进行摘要
        summary = self._summarize_messages(old_messages)
        
        # 将摘要作为系统消息添加到开头
        compressed = [
            {"role": "system", "content": f"历史对话摘要：\n{summary}"},
            *recent_messages
        ]
        
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
        # 摘要策略主要压缩消息，状态保持不变
        return state
