# Context compression via SummarizationMiddleware

## Summary

- Implemented **SummarizationMiddleware** (LangChain AgentMiddleware) for context compression: when message count or token count exceeds a threshold, older messages are summarized and replaced with a summary message plus recent messages (AI/Tool pairs preserved).
- Wired optional **middleware** parameter into all six agent factory functions and into **create_web_app_team**; when `enable_context_compression` is True, a shared SummarizationMiddleware is built from settings and passed to every agent.
- Exposed config: **trigger** (via `context_max_tokens`), **keep** (via `context_recent_window`), **agent_summary_model**, **context_trim_tokens_to_summarize**, **context_summary_prompt** (optional).

## Changes

### New

- **`src/agents/web_app_team/middleware/`**
  - `__init__.py`: exports `SummarizationMiddleware`.
  - `summarization.py`: `SummarizationMiddleware` with `before_model` / `abefore_model`, trigger/keep (tokens/messages/fraction), token counter, safe cutoff for AI/Tool pairs, summary prompt and trim; uses `RemoveMessage(id=REMOVE_ALL_MESSAGES)` + summary `HumanMessage` + preserved messages.

### Modified

- **Agent factories** (`boss`, `pm`, `architect`, `pjm`, `engineer`, `qa`): added optional `middleware: Sequence[AgentMiddleware] = ()` and pass `list(middleware)` into `create_agent(..., middleware=...)`.
- **`src/agents/web_app_team/team.py`**: when `settings.enable_context_compression` is True, builds `SummarizationMiddleware` from settings (trigger, keep, model, trim_tokens, optional summary_prompt) and passes the same list to all `create_*_agent(..., middleware=middleware_list)`.
- **`src/shared/config/settings.py`**: added `agent_summary_model`, `context_trim_tokens_to_summarize`, `context_summary_prompt`; documented trigger/keep mapping from existing `context_max_tokens` / `context_recent_window`.

## Configuration

| Setting | Default | Description |
|--------|---------|-------------|
| `enable_context_compression` | `False` | When True, all agents get SummarizationMiddleware. |
| `context_max_tokens` | `4000` | Trigger: run summarization when tokens ≥ this. |
| `context_recent_window` | `15` | Keep: retain this many recent messages after summarization. |
| `agent_summary_model` | `gpt-4o-mini` | Model for generating summaries (e.g. `openai:gpt-4o-mini`). |
| `context_trim_tokens_to_summarize` | `4000` | Max tokens sent to summary LLM; `None` = no trim. |
| `context_summary_prompt` | `None` | Optional custom prompt template with `{messages}`; omit to use built-in. |

## Usage

- Set `ENABLE_CONTEXT_COMPRESSION=true` (and optionally the above env vars) to enable. No code changes required; all agents created via `create_web_app_team` will use the middleware when enabled.
- RAG remains tool-only; no RAG middleware.
