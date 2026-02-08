# Docker 镜像合并与 uv 构建

## 变更概述

将 `Dockerfile.agent-runner`、`Dockerfile.agent`、`Dockerfile.mgx-api` 合并为统一镜像 `infra/Dockerfile.mgx`，使用 `uv sync` 安装依赖（清华源），通过不同 entrypoint 区分 mgx-api、celery-worker、agent 三种用途。

## 主要变更

### 1. 新增

- **`infra/Dockerfile.mgx`**：统一镜像
  - 基于 python:3.12-slim + uv
  - 系统依赖：git、docker.io、curl
  - `uv sync --locked` 安装依赖（pyproject.toml 已配置清华源）
  - 默认 CMD：`python /app/src/agents/run_agent.py`

- **`scripts/test_mgx_image.sh`**：镜像健康检查脚本
  - docker run 测试 Agent、MGX API、Celery 三种 entrypoint
  - docker exec 测试 API 健康端点
  - `make test-image` 调用

- **`.dockerignore`**：减少构建上下文

### 2. 修改

- **`infra/docker-compose.yml`**
  - mgx-api、celery-worker 均使用 `infra/Dockerfile.mgx`
  - celery-worker 命令：`celery -A scheduler.tasks worker`（修正模块名）

- **`Makefile`**
  - `build-agent`：构建 `mgx:latest`
  - 新增 `build-mgx`、`test-image`

- **`src/shared/config/settings.py`**：`agent_container_image` 默认值改为 `mgx:latest`

- **`.env.example`**：`AGENT_CONTAINER_IMAGE=mgx:latest`

- **文档**：agent-container-guide.md、architecture.md、QUICKSTART.md

### 3. 删除

- `infra/Dockerfile.agent-runner`
- `infra/Dockerfile.agent`
- `infra/Dockerfile.mgx-api`

## 使用方式

```bash
# 构建
make build-agent
# 或 make build-mgx

# 健康检查
make test-image

# 启动服务（docker-compose 会使用同一镜像）
make up
```

## 镜像标签

- 统一使用 `mgx:latest`
- 可通过 `AGENT_CONTAINER_IMAGE` 环境变量覆盖
