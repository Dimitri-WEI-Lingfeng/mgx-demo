# Apisix 自动路由配置

**日期**: 2026-02-02  
**类型**: 功能增强

## 改动概述

在 Docker 容器创建和停止时自动配置和清理 Apisix 网关路由，实现容器与网关的自动化集成。

## 改动详情

### 1. DockerService 增强

**文件**: `src/mgx_api/services/docker_service.py`

#### 1.1 导入 ApisixService

```python
from .apisix_service import ApisixService
```

#### 1.2 start_dev_container 方法

- 容器创建成功后，自动创建 Apisix 路由
- 路由配置：`/apps/{app_name}/dev/*` → 容器端口
- 使用容器名作为 upstream_host（Docker 网络内部通信）
- 使用框架默认端口作为 upstream_port
- 失败时只记录警告，不影响容器创建流程

#### 1.3 stop_dev_container 方法

- 增加 `app_name` 可选参数
- 停止容器时自动删除对应的 Apisix 路由
- 失败时只记录警告，不影响容器停止流程

#### 1.4 start_prod_container 方法

- 生产容器创建成功后，自动创建 Apisix 路由
- 路由配置：`/apps/{app_name}/prod/*` → 容器端口
- 自动检测容器端口（3000 或 8000）
- 失败时只记录警告，不影响容器创建流程

#### 1.5 stop_prod_container 方法

- 增加 `app_name` 可选参数
- 停止容器时自动删除对应的 Apisix 路由
- 失败时只记录警告，不影响容器停止流程

## 技术细节

### 网络配置

- **upstream_host**: 使用容器名（如 `mgx-dev-{workspace_id}`）
  - Docker 容器间通过容器名直接通信
  - Apisix 容器和应用容器在同一个 Docker 网络中
  
- **upstream_port**: 使用框架的容器内端口
  - Next.js: 3000
  - FastAPI-Vite: 8000
  - 不使用主机映射端口

### 路由配置

路由由 ApisixService 管理，包含：
- URI 匹配：`/apps/{app_name}/{dev|prod}/*`
- 方法：支持所有 HTTP 方法
- 重写规则：去除路由前缀（`proxy-rewrite` 插件）
- 负载均衡：roundrobin 类型

## 影响范围

### API 变更

- `DockerService.stop_dev_container()` 增加可选参数 `app_name`
- `DockerService.stop_prod_container()` 增加可选参数 `app_name`

### 向后兼容性

- 新增参数为可选，不影响现有调用
- 建议更新调用处传入 `app_name` 以启用路由自动清理

## 测试建议

1. **开发容器测试**
   ```bash
   # 创建容器，验证路由自动创建
   # 访问 http://localhost:9080/apps/{app_name}/dev/
   # 停止容器，验证路由自动删除
   ```

2. **生产容器测试**
   ```bash
   # 创建生产容器，验证路由自动创建
   # 访问 http://localhost:9080/apps/{app_name}/prod/
   # 停止容器，验证路由自动删除
   ```

3. **错误处理测试**
   - Apisix 服务不可用时，容器仍能正常创建/停止
   - 检查日志中的警告信息

## 后续优化建议

1. 考虑在容器重启时自动恢复路由
2. 添加路由健康检查
3. 支持自定义路由配置（如超时、重试等）
4. 添加路由管理的管理界面
