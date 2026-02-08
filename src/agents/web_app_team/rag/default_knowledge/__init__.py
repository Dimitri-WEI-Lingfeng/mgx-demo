"""默认知识库内容，从 Markdown 文件加载。"""

from pathlib import Path


def load_default_knowledge() -> dict[str, str]:
    """从 default_knowledge 目录加载所有 .md 文件，返回 category -> content 映射。"""
    dir_path = Path(__file__).parent
    result: dict[str, str] = {}
    for md_file in sorted(dir_path.glob("*.md")):
        if md_file.name == "fallback.md":
            continue
        category = md_file.stem
        result[category] = md_file.read_text(encoding="utf-8").strip()
    return result


def load_fallback_content() -> str:
    """加载 fallback 内容。"""
    fallback_path = Path(__file__).parent / "fallback.md"
    if fallback_path.exists():
        return fallback_path.read_text(encoding="utf-8").strip()
    return "未找到相关知识，建议使用 search_web 工具搜索网络获取更多信息。"
