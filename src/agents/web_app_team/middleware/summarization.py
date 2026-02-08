"""Summarization middleware for context compression.

When message count or token count exceeds a threshold, older messages are
summarized and replaced with a single summary message plus recent messages.
Follows the same pattern as LangChain's SummarizationMiddleware (before_model
/ abefore_model, trigger/keep, safe cutoff for AI/Tool pairs).
"""

from __future__ import annotations

import traceback
import uuid
from collections.abc import Callable, Iterable
from typing import Any, Literal, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    RemoveMessage,
    ToolMessage,
)
from langchain_core.messages.utils import (
    count_tokens_approximately,
    get_buffer_string,
    trim_messages,
)
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.runtime import Runtime
from typing_extensions import override

from langchain.agents.middleware.types import AgentMiddleware, AgentState
from langchain.chat_models import init_chat_model

TokenCounter = Callable[[Iterable[Any]], int]

DEFAULT_SUMMARY_PROMPT = """请简要总结以下对话的关键信息，保留重要的决策、文档和结论。

用简洁的要点形式总结（每个要点一行）。只输出摘要内容，不要其他说明。

对话记录：
{messages}
"""

ContextFraction = tuple[Literal["fraction"], float]
ContextTokens = tuple[Literal["tokens"], int]
ContextMessages = tuple[Literal["messages"], int]
ContextSize = ContextFraction | ContextTokens | ContextMessages

_DEFAULT_MESSAGES_TO_KEEP = 20
_DEFAULT_TRIM_TOKEN_LIMIT = 4000
_DEFAULT_FALLBACK_MESSAGE_COUNT = 15


def _get_approximate_token_counter(model: BaseChatModel) -> TokenCounter:
    """Tune parameters of approximate token counter based on model type."""
    try:
        llm_type = getattr(model, "_llm_type", "") or ""
    except Exception:
        traceback.print_exc()
        llm_type = ""
    if "anthropic" in llm_type.lower():
        from functools import partial
        return cast(TokenCounter, partial(count_tokens_approximately, chars_per_token=3.3))
    return count_tokens_approximately


class SummarizationMiddleware(AgentMiddleware[AgentState[Any], Any]):
    """Summarizes conversation history when token or message limits are approached.

    Uses before_model / abefore_model to replace old messages with a summary
    plus recent messages, preserving AI/Tool message pairs.
    """

    tools: tuple = ()  # type: ignore[assignment]

    def __init__(
        self,
        model: str | BaseChatModel,
        *,
        trigger: ContextSize | list[ContextSize] | None = None,
        keep: ContextSize = ("messages", _DEFAULT_MESSAGES_TO_KEEP),
        token_counter: TokenCounter | None = None,
        summary_prompt: str = DEFAULT_SUMMARY_PROMPT,
        trim_tokens_to_summarize: int | None = _DEFAULT_TRIM_TOKEN_LIMIT,
    ) -> None:
        """Initialize summarization middleware.

        Args:
            model: Language model for generating summaries (e.g. gpt-4o-mini).
            trigger: When to run summarization. E.g. ("messages", 50) or ("tokens", 4000).
            keep: How much history to keep after summarization. E.g. ("messages", 20).
            token_counter: Function to count tokens; default from count_tokens_approximately.
            summary_prompt: Template with {messages} placeholder.
            trim_tokens_to_summarize: Max tokens to send to summary LLM; None to skip trim.
        """
        super().__init__()
        if isinstance(model, str):
            model = init_chat_model(model)
        self.model = model
        if trigger is None:
            self._trigger_conditions: list[ContextSize] = []
        elif isinstance(trigger, list):
            self._trigger_conditions = [self._validate_context_size(c, "trigger") for c in trigger]
        else:
            self._trigger_conditions = [self._validate_context_size(trigger, "trigger")]
        self.keep = self._validate_context_size(keep, "keep")
        self.token_counter = token_counter or _get_approximate_token_counter(self.model)
        self.summary_prompt = summary_prompt
        self.trim_tokens_to_summarize = trim_tokens_to_summarize

    @staticmethod
    def _validate_context_size(context: ContextSize, parameter_name: str) -> ContextSize:
        kind, value = context
        if kind == "fraction":
            if not (0 < value <= 1):
                raise ValueError(f"Fractional {parameter_name} must be in (0, 1], got {value}.")
        elif kind in ("tokens", "messages"):
            if value <= 0:
                raise ValueError(f"{parameter_name} must be > 0, got {value}.")
        else:
            raise ValueError(f"Unsupported context size type {kind} for {parameter_name}.")
        return context

    def _get_profile_limits(self) -> int | None:
        try:
            profile = getattr(self.model, "profile", None)
        except Exception:
            traceback.print_exc()
            return None
        if not isinstance(profile, dict):
            return None
        max_input = profile.get("max_input_tokens")
        return int(max_input) if isinstance(max_input, (int, float)) else None

    def _should_summarize(self, messages: list[AnyMessage], total_tokens: int) -> bool:
        if not self._trigger_conditions:
            return False
        for kind, value in self._trigger_conditions:
            if kind == "messages" and len(messages) >= value:
                return True
            if kind == "tokens" and total_tokens >= value:
                return True
            if kind == "fraction":
                max_tokens = self._get_profile_limits()
                if max_tokens is None:
                    continue
                threshold = max(1, int(max_tokens * value))
                if total_tokens >= threshold:
                    return True
        return False

    def _determine_cutoff_index(self, messages: list[AnyMessage]) -> int:
        kind, value = self.keep
        if kind in ("tokens", "fraction"):
            cutoff = self._find_token_based_cutoff(messages)
            if cutoff is not None:
                return cutoff
            return self._find_safe_cutoff(messages, _DEFAULT_MESSAGES_TO_KEEP)
        return self._find_safe_cutoff(messages, cast(int, value))

    def _find_token_based_cutoff(self, messages: list[AnyMessage]) -> int | None:
        if not messages:
            return 0
        kind, value = self.keep
        if kind == "fraction":
            max_tokens = self._get_profile_limits()
            if max_tokens is None:
                return None
            target = max(1, int(max_tokens * value))
        else:
            target = max(1, int(value))
        if self.token_counter(messages) <= target:
            return 0
        left, right = 0, len(messages)
        cutoff_candidate = len(messages)
        for _ in range(len(messages).bit_length() + 1):
            if left >= right:
                break
            mid = (left + right) // 2
            if self.token_counter(messages[mid:]) <= target:
                cutoff_candidate = mid
                right = mid
            else:
                left = mid + 1
        if cutoff_candidate >= len(messages):
            cutoff_candidate = max(0, len(messages) - 1)
        return self._find_safe_cutoff_point(messages, cutoff_candidate)

    def _find_safe_cutoff(self, messages: list[AnyMessage], messages_to_keep: int) -> int:
        if len(messages) <= messages_to_keep:
            return 0
        target = len(messages) - messages_to_keep
        return self._find_safe_cutoff_point(messages, target)

    @staticmethod
    def _find_safe_cutoff_point(messages: list[AnyMessage], cutoff_index: int) -> int:
        """Ensure cutoff does not split AI/Tool message pairs."""
        if cutoff_index >= len(messages):
            return cutoff_index
        if not isinstance(messages[cutoff_index], ToolMessage):
            return cutoff_index
        tool_call_ids: set[str] = set()
        idx = cutoff_index
        while idx < len(messages) and isinstance(messages[idx], ToolMessage):
            tm = cast(ToolMessage, messages[idx])
            if tm.tool_call_id:
                tool_call_ids.add(tm.tool_call_id)
            idx += 1
        for i in range(cutoff_index - 1, -1, -1):
            msg = messages[i]
            if isinstance(msg, AIMessage) and msg.tool_calls:
                ai_ids = {tc.get("id") for tc in msg.tool_calls if tc.get("id")}
                if tool_call_ids & ai_ids:
                    return i
        return idx

    @staticmethod
    def _ensure_message_ids(messages: list[AnyMessage]) -> None:
        """确保每条消息都有 id。LangChain 使用 id，部分代码可能期望 message_id。"""
        for msg in messages:
            msg_id = getattr(msg, "id", None) or getattr(msg, "message_id", None)
            if msg_id is None:
                msg_id = str(uuid.uuid4())
                msg.id = msg_id  # type: ignore[attr-defined]
            # 为兼容期望 message_id 的代码，设置 message_id 为 id 的别名
            if not hasattr(msg, "message_id"):
                msg.message_id = msg_id  # type: ignore[attr-defined]

    def _create_summary(self, messages_to_summarize: list[AnyMessage]) -> str:
        if not messages_to_summarize:
            return "No previous conversation history."
        trimmed = self._trim_messages_for_summary(messages_to_summarize)
        if not trimmed:
            return "Previous conversation was too long to summarize."
        formatted = get_buffer_string(trimmed)
        try:
            response = self.model.invoke(
                self.summary_prompt.format(messages=formatted).rstrip(),
                config={"metadata": {"lc_source": "summarization"}},
            )
            content = response.content if hasattr(response, "content") else str(response)
            return content.strip() if isinstance(content, str) else str(content).strip()
        except Exception as e:
            traceback.print_exc()
            return f"Error generating summary: {e!s}"

    async def _acreate_summary(self, messages_to_summarize: list[AnyMessage]) -> str:
        if not messages_to_summarize:
            return "No previous conversation history."
        trimmed = self._trim_messages_for_summary(messages_to_summarize)
        if not trimmed:
            return "Previous conversation was too long to summarize."
        formatted = get_buffer_string(trimmed)
        try:
            response = await self.model.ainvoke(
                self.summary_prompt.format(messages=formatted).rstrip(),
                config={"metadata": {"lc_source": "summarization"}},
            )
            content = response.content if hasattr(response, "content") else str(response)
            return content.strip() if isinstance(content, str) else str(content).strip()
        except Exception as e:
            traceback.print_exc()
            return f"Error generating summary: {e!s}"

    def _trim_messages_for_summary(self, messages: list[AnyMessage]) -> list[AnyMessage]:
        if self.trim_tokens_to_summarize is None:
            return messages
        try:
            result = trim_messages(
                messages,
                max_tokens=self.trim_tokens_to_summarize,
                token_counter=self.token_counter,
                start_on="human",
                strategy="last",
                allow_partial=True,
                include_system=True,
            )
            return cast(list[AnyMessage], result)
        except Exception:
            traceback.print_exc()
            return messages[-_DEFAULT_FALLBACK_MESSAGE_COUNT:]

    @staticmethod
    def _build_new_messages(summary: str) -> list[HumanMessage]:
        return [
            HumanMessage(
                content=f"Here is a summary of the conversation to date:\n\n{summary}",
                additional_kwargs={"lc_source": "summarization"},
            )
        ]

    @override
    def before_model(
        self, state: AgentState[Any], runtime: Runtime[Any]
    ) -> dict[str, Any] | None:
        messages = state["messages"]
        self._ensure_message_ids(messages)
        total_tokens = self.token_counter(messages)
        if not self._should_summarize(messages, total_tokens):
            return None
        cutoff_index = self._determine_cutoff_index(messages)
        if cutoff_index <= 0:
            return None
        to_summarize = messages[:cutoff_index]
        preserved = messages[cutoff_index:]
        summary = self._create_summary(to_summarize)
        new_messages = self._build_new_messages(summary)
        return {
            "messages": [
                RemoveMessage(id=REMOVE_ALL_MESSAGES),
                *new_messages,
                *preserved,
            ]
        }

    @override
    async def abefore_model(
        self, state: AgentState[Any], runtime: Runtime[Any]
    ) -> dict[str, Any] | None:
        messages = state["messages"]
        self._ensure_message_ids(messages)
        total_tokens = self.token_counter(messages)
        if not self._should_summarize(messages, total_tokens):
            return None
        cutoff_index = self._determine_cutoff_index(messages)
        if cutoff_index <= 0:
            return None
        to_summarize = messages[:cutoff_index]
        preserved = messages[cutoff_index:]
        summary = await self._acreate_summary(to_summarize)
        new_messages = self._build_new_messages(summary)
        return {
            "messages": [
                RemoveMessage(id=REMOVE_ALL_MESSAGES),
                *new_messages,
                *preserved,
            ]
        }
