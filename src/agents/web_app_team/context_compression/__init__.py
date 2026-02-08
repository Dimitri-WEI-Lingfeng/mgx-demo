"""上下文压缩策略。"""

from agents.web_app_team.context_compression.base import ContextCompressionStrategy
from agents.web_app_team.context_compression.sliding_window import SlidingWindowStrategy
from agents.web_app_team.context_compression.key_extraction import KeyExtractionStrategy
from agents.web_app_team.context_compression.summarization import SummarizationStrategy
from agents.web_app_team.context_compression.hybrid import HybridStrategy

__all__ = [
    "ContextCompressionStrategy",
    "SlidingWindowStrategy",
    "KeyExtractionStrategy",
    "SummarizationStrategy",
    "HybridStrategy",
]
