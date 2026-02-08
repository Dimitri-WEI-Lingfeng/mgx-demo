# Agent Team 架构重构变更日志

## 变更日期
2026-02-01

## 变更概述

将单一 agent 架构重构为基于 LangGraph 的多代理团队协作架构，实现了包含 6 个专业角色的分层团队系统。

## 主要变更

### 1. 新增目录结构

```
src/agents/web_app_team/
├── __init__.py
├── state.py                      # 团队共享状态
├── graph.py                      # LangGraph 工作流编排
├── team.py                       # 团队工厂函数
├── agents/                       # 各角色 Agent
│   ├── boss.py
│   ├── product_manager.py
│   ├── architect.py
│   ├── project_manager.py
│   ├── engineer.py
│   └── qa.py
├── tools/                        # 工具集
│   ├── workspace_tools.py        # 文件操作工具
│   └── docker_tools.py           # 容器命令执行工具
├── prompts/                      # 提示词模板
│   ├── boss.py
│   ├── product_manager.py
│   ├── architect.py
│   ├── project_manager.py
│   ├── engineer.py
│   └── qa.py
├── context_compression/          # 上下文压缩（框架，待实现）
│   ├── base.py
│   ├── sliding_window.py
│   ├── key_extraction.py
│   ├── summarization.py
│   └── hybrid.py
└── rag/                          # RAG 模块（框架，待实现）
    ├── vector_store.py
    ├── retriever.py
    └── knowledge_base.py
```

### 2. 核心功能实现

#### 2.1 团队状态管理 (state.py)

- 定义了 `TeamState` TypedDict，包含消息历史、当前阶段、文档、任务等
- 提供 `create_initial_state()` 函数创建初始状态
- 定义了工作流阶段常量（requirement, design, development, testing）

#### 2.2 六个专业 Agent

| Agent | 职责 | 工具 | 默认模型 |
|-------|------|------|----------|
| Boss | 需求提炼 | read_file, write_file, list_files | gpt-4o-mini |
| Product Manager | PRD 编写 | read_file, write_file, list_files | gpt-4o-mini |
| Architect | 架构设计 | workspace tools + RAG | gpt-4o（推荐）|
| Project Manager | 任务拆解 | read_file, write_file, list_files | gpt-4o-mini |
| Engineer | 代码实现 | workspace + docker tools | gpt-4o（推荐）|
| QA | 测试验证 | workspace + docker + test tools | gpt-4o-mini |

#### 2.3 工具集

**Workspace Tools** (`tools/workspace_tools.py`):
- `read_file()`: 读取文件
- `write_file()`: 写入文件
- `list_files()`: 列出目录
- `delete_file()`: 删除文件
- `create_directory()`: 创建目录
- `search_in_files()`: 搜索文件内容

**Docker Tools** (`tools/docker_tools.py`):
- `exec_command()`: 执行 shell 命令
- `get_container_logs()`: 获取容器日志
- `install_package()`: 安装依赖包
- `run_tests()`: 运行测试
- `get_container_status()`: 获取容器状态

**安全特性**:
- 所有文件操作使用 `safe_join()` 防止路径遍历
- Docker 命令执行有危险命令检查
- 容器状态验证

#### 2.4 工作流编排 (graph.py)

使用 LangGraph 的 StateGraph 实现工作流：

```
Boss → Product Manager → Architect → Project Manager → Engineer → QA → END
```

- 支持条件分支（如 Architect 可能要求修改 PRD）
- 支持循环（如 QA 发现问题返回 Engineer）
- 使用 router 函数动态决定下一个节点

#### 2.5 多模型配置

支持为每个 agent 独立配置模型和温度：

```python
# 默认模型
agent_default_model: str = "gpt-4o-mini"
agent_default_temperature: float = 0.7

# 独立配置（可选）
agent_boss_model: str | None = None
agent_architect_model: str | None = None  # 建议 gpt-4o
agent_engineer_model: str | None = None   # 建议 gpt-4o
# ...
```

**成本优化**：
- 默认全部使用 gpt-4o-mini
- 核心角色（Architect、Engineer）可配置使用 gpt-4o
- 预计可节省 60-70% 的模型成本

### 3. 集成到现有系统

#### 3.1 agent_factory.py

新增 `create_team_agent()` 函数：

```python
def create_team_agent(
    workspace_id: str,
    framework: str,
    callbacks: list = None,
) -> CompiledGraph:
    from agents.web_app_team import create_web_app_team
    return create_web_app_team(workspace_id, framework, callbacks)
```

#### 3.2 run_agent.py

新增 `run_team_agent_with_streaming()` 函数，支持：
- 团队模式执行
- 流式事件输出
- Langfuse 集成
- 错误处理和恢复

通过环境变量 `AGENT_MODE` 选择模式：
- `team`: 使用团队模式（默认）
- `single`: 使用单一 agent 模式

### 4. 配置更新

#### 4.1 settings.py

新增配置项：

```python
# Agent Team Configuration
agent_default_model: str = "gpt-4o-mini"
agent_default_temperature: float = 0.7
agent_max_iterations: int = 20

# Individual Agent Models (optional)
agent_boss_model: str | None = None
agent_pm_model: str | None = None
agent_architect_model: str | None = None
agent_pjm_model: str | None = None
agent_engineer_model: str | None = None
agent_qa_model: str | None = None

# Temperature Configuration (optional)
agent_boss_temperature: float | None = None
# ...

# Context Compression (框架已就位，待启用)
context_compression_strategy: str = "sliding_window"
enable_context_compression: bool = False

# RAG Configuration (框架已就位，待启用)
enable_rag: bool = False
vector_store_path: str = "./vector_stores"

# Search Configuration
enable_web_search: bool = False
```

#### 4.2 .env.example

新增环境变量配置示例：

```bash
# Agent Team Configuration
AGENT_DEFAULT_MODEL=gpt-4o-mini
AGENT_DEFAULT_TEMPERATURE=0.7

# Individual Agent Models (optional)
# AGENT_ARCHITECT_MODEL=gpt-4o
# AGENT_ENGINEER_MODEL=gpt-4o

# Agent Mode
AGENT_MODE=team  # team or single
```

## 功能特性

### 已实现

1. ✅ 6 个专业 Agent 的完整实现
2. ✅ LangGraph 工作流编排
3. ✅ Workspace 文件操作工具（安全）
4. ✅ Docker 容器命令执行工具（安全）
5. ✅ 多模型配置支持
6. ✅ 独立温度参数配置
7. ✅ 团队模式和单一模式切换
8. ✅ 流式事件输出
9. ✅ Langfuse 集成

### 框架已就位（待启用）

1. 🔄 上下文压缩模块（4种策略）
   - 滑动窗口策略
   - 关键信息提取策略
   - 摘要压缩策略
   - 混合策略

2. 🔄 RAG 模块
   - 向量存储管理
   - 知识检索器
   - 知识库管理

3. 🔄 搜索工具
   - 代码搜索
   - 文档搜索
   - Web 搜索

### 待实现

1. ⏳ RAG 知识库初始化和数据加载
2. ⏳ RAG 工具集成到 Architect、Engineer、QA Agent
3. ⏳ 搜索工具集成
4. ⏳ 上下文压缩实际应用
5. ⏳ 详细的单元测试和集成测试
6. ⏳ 性能优化和监控

## 使用方式

### 启用团队模式

在容器环境变量中设置：

```bash
AGENT_MODE=team
AGENT_DEFAULT_MODEL=gpt-4o-mini
AGENT_ARCHITECT_MODEL=gpt-4o
AGENT_ENGINEER_MODEL=gpt-4o
```

### 成本优化配置

```bash
# 开发环境 - 全部使用便宜模型
AGENT_DEFAULT_MODEL=gpt-4o-mini

# 生产环境 - 关键角色使用强模型
AGENT_DEFAULT_MODEL=gpt-4o-mini
AGENT_ARCHITECT_MODEL=gpt-4o
AGENT_ENGINEER_MODEL=gpt-4o
```

### 切换回单一模式

```bash
AGENT_MODE=single
```

## 技术要点

### 安全性

1. **文件操作安全**：
   - 使用 `safe_join()` 防止目录遍历攻击
   - 所有文件路径在 workspace 内验证

2. **命令执行安全**：
   - 危险命令黑名单检查
   - 容器状态验证
   - 限制可执行命令类型

### 可扩展性

1. **策略模式**：上下文压缩使用策略模式，易于扩展
2. **工厂模式**：Agent 创建使用工厂模式，支持灵活配置
3. **图模式**：工作流使用图模式，易于调整流程

### 性能

1. **模型选择**：核心任务使用强模型，辅助任务使用轻量模型
2. **并行执行**：LangGraph 支持并行节点（待优化）
3. **上下文管理**：上下文压缩框架已就位

## 迁移指南

### 兼容性

- ✅ 完全向后兼容，保留了单一 agent 模式
- ✅ 通过 `AGENT_MODE` 环境变量切换
- ✅ 默认配置使用团队模式

### 建议迁移步骤

1. 在开发环境测试团队模式
2. 验证核心功能正常工作
3. 调整模型配置优化成本
4. 逐步迁移到生产环境

## 已知限制

1. RAG 和搜索工具暂未启用（框架已就位）
2. 上下文压缩暂未启用（框架已就位）
3. 单元测试覆盖待完善
4. 工作流暂不支持人工介入（未来扩展）
5. 团队协作的循环次数未限制（可能无限循环）

## 后续计划

1. 启用并测试 RAG 模块
2. 集成搜索工具到相关 Agent
3. 启用上下文压缩
4. 完善单元测试和集成测试
5. 性能监控和优化
6. 支持人工介入和审批流程
7. 添加工作流可视化
8. 支持自定义团队配置

## 影响范围

### 修改的文件

- `src/agents/agent_factory.py`: 新增 `create_team_agent()` 函数
- `src/agents/run_agent.py`: 新增 `run_team_agent_with_streaming()` 函数，支持模式切换
- `src/shared/config/settings.py`: 新增 Agent Team 配置项
- `.env.example`: 新增环境变量配置示例

### 新增的文件

- `src/agents/web_app_team/` 目录下的所有文件（共 30+ 个文件）
- `change-logs/CHANGELOG-agent-team-refactor.md`: 本变更日志

### 未修改的文件

- 所有 API 端点保持不变
- 数据库 schema 保持不变
- 事件类型保持不变
- Celery task 保持不变

## 测试建议

1. **功能测试**：
   - 测试团队模式基本流程
   - 测试各个 Agent 的工具调用
   - 测试文件操作和命令执行

2. **安全测试**：
   - 测试路径遍历防护
   - 测试危险命令拦截
   - 测试容器隔离

3. **性能测试**：
   - 测试不同模型配置的响应时间
   - 测试 token 消耗
   - 测试并发执行

4. **集成测试**：
   - 端到端测试完整的开发流程
   - 测试 Langfuse 集成
   - 测试事件流输出

## 文档更新

建议更新以下文档：

1. README.md - 添加团队模式说明
2. docs/architecture.md - 更新架构图
3. docs/getting-started.md - 添加团队模式配置指南
4. API 文档 - 说明 AGENT_MODE 参数

## 贡献者

- Agent Team 架构设计和实现
- 多模型配置系统
- 安全工具集实现
- LangGraph 工作流编排

---

**注意**: 这是一个重大架构升级，建议在充分测试后再部署到生产环境。
