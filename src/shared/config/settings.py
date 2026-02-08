"""Shared settings and configuration."""
import pprint
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    # MongoDB
    mongodb_url: str = "mongodb://mongodb:27017"
    mongodb_db: str = "mgx"
    mongodb_apps_db: str = "mgx_apps"  # Database for app data
    
    # JWT / OAuth2
    jwt_secret_key: str = "dev-secret-please-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours
    jwt_issuer: str = "mgx-oauth2"
    jwt_audience: str = "mgx"
    
    # OAuth2 Provider
    oauth2_provider_url: str = "http://oauth2-provider:8001"
    jwks_cache_seconds: int = 300
    
    # Workspaces
    workspaces_root: str = "/workspaces"
    # Host path for mounting volumes from mgx-api to dev containers
    # Should be set to absolute path on host machine in docker-compose.yml
    host_workspaces_root: str = "./workspaces"
    
    # Redis / Celery
    redis_url: str = "redis://redis:6379/0"
    
    # Apisix
    apisix_external_host: str = "http://localhost:9080"
    apisix_admin_url: str = "http://apisix:9180"
    # Dev 容器直连（前端/浏览器访问 dev server 的 base，不含端口）
    dev_external_host: str = "http://localhost"
    apisix_admin_key: str = "edd1c9f034335f136f87ad84b625c8f1"
    apisix_yaml_path: str = "/app/apisix.yaml"  # 基础路由配置，ensure_base_routes 同步到 etcd
    
    # Default admin user
    default_admin_username: str = "admin"
    default_admin_password: str = "admin123"
    
    # Langfuse Configuration
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    langfuse_enabled: bool = False  # Set to True to enable langfuse tracing
    
    # Agent / MCP - mgx-api 调用配置（Agent 容器通过 MCP 调用 mgx-api 的 Docker 操作）
    mgx_agent_api_key: str = ""  # 可选，MCP 兼容/测试用；生产环境主用 session_id 鉴权
    mgx_api_url: str = "http://mgx-api:8000"  # Agent 容器内访问 mgx-api 的 base URL
    mgx_network: str = "infra_mgx-network"  # Agent 容器需加入的网络名
    mgx_mcp_path: str = "/mcp"  # MCP 服务挂载路径

    # Agent Container Configuration
    agent_workspace_root_in_container: str = "/workspace"  # Agent 容器内 workspace 根路径
    agent_container_image: str = "mgx:latest"
    agent_container_memory_limit: str = "2g"  # 内存限制
    agent_container_cpu_quota: int = 100000  # CPU quota (100000 = 1 CPU)
    agent_task_timeout_seconds: int = 1800  # Agent 任务超时时间（秒）默认 30 分钟
    
    # Agent Team Configuration - Default Model
    agent_default_model: str = "qwen3-coder-plus"
    agent_default_temperature: float = 0.7
    agent_max_iterations: int = 20
    
    # Individual Agent Model Configuration (optional, defaults to agent_default_model)
    agent_boss_model: str | None = None           # 需求提炼
    agent_pm_model: str | None = None             # PRD 编写
    agent_architect_model: str | None = None      # 架构设计，建议使用 gpt-4o
    agent_pjm_model: str | None = None            # 任务拆解
    agent_engineer_model: str | None = None       # 代码实现，建议使用 gpt-4o
    agent_qa_model: str | None = None             # 测试编写
    
    # Model Temperature Configuration (optional)
    agent_boss_temperature: float | None = None
    agent_pm_temperature: float | None = None
    agent_architect_temperature: float | None = None
    agent_pjm_temperature: float | None = None
    agent_engineer_temperature: float | None = None
    agent_qa_temperature: float | None = None
    
    # Context Compression (Summarization Middleware) Configuration
    context_compression_strategy: str = "sliding_window"  # sliding_window, summarization, key_extraction, hybrid
    context_max_tokens: int = 4000
    context_recent_window: int = 15
    enable_context_compression: bool = False  # 启用时在 agent 上挂载 SummarizationMiddleware
    # Summarization middleware: trigger=("tokens", context_max_tokens), keep=("messages", context_recent_window)
    agent_summary_model: str = "gpt-4o-mini"  # 摘要用模型（字符串传 init_chat_model，如 "openai:gpt-4o-mini"）
    context_trim_tokens_to_summarize: int | None = 4000  # 送给摘要 LLM 的最大 token 数，None 表示不裁剪
    context_summary_prompt: str | None = None  # 可选；为 None 时使用 middleware 默认摘要 prompt
    
    # RAG Configuration
    enable_rag: bool = False  # 暂时禁用，待实现
    vector_store_path: str = "./vector_stores"
    rag_top_k: int = 5
    enable_rag_compression: bool = True
    
    # LLM API Configuration (OpenAI-compatible: OpenAI, DashScope, OpenRouter, etc.)
    # Agent 容器内 ChatOpenAI 需要这些环境变量；创建 agent 容器时由 scheduler 注入
    openai_api_key: str = ""  # 必填，用于 LLM 调用（如 qwen3-coder-flash 需配合 DashScope 等）
    openai_base_url: str | None = None  # 可选，自定义 API 端点（如 DashScope、OpenRouter 的 base URL）

    # Search Configuration
    enable_web_search: bool = False
    tavily_api_key: str = ""
    
    # Other Configuration
    enable_code_review: bool = True
    
    model_config = SettingsConfigDict(
        env_file=[".env", ".env.local"],
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
