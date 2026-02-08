# Dev Server 管理功能 - 第一阶段完成

## 概述

第一阶段为 Agent 提供了启动和管理开发服务器的能力，包括后台执行、日志重定向和状态查询功能。

## 完成的功能

### 1. Agent 工具 (docker_tools.py)

添加了四个新的开发服务器管理工具：

#### `start_dev_server(command, working_dir, port)`
- **功能**：在 dev container 中启动开发服务器（后台运行）
- **特性**：
  - 使用 `nohup` 后台运行，避免阻塞 agent
  - 日志重定向到 `/workspace/.dev-server.log`
  - 进程 PID 保存到 `/workspace/.dev-server.pid`
  - 启动命令保存到 `/workspace/.dev-server.cmd`
  - 自动检测是否已有 dev server 在运行
  - 启动后自动验证进程状态
- **示例**：
  ```python
  start_dev_server("npm run dev", port=3000)
  start_dev_server("pnpm dev", port=3000)
  start_dev_server("yarn dev --port 3001", port=3001)
  ```

#### `get_dev_server_status()`
- **功能**：获取开发服务器的运行状态
- **返回信息**：
  - 运行状态（运行中/已停止/未启动）
  - 进程 PID
  - 启动命令
  - 监听端口（如果可检测）
  - 最近的日志输出
- **示例**：
  ```python
  get_dev_server_status()
  ```

#### `get_dev_server_logs(tail, follow)`
- **功能**：获取开发服务器的日志输出
- **参数**：
  - `tail`: 返回最后 N 行日志（默认 50，设置为 0 获取全部）
  - `follow`: 是否持续跟踪（保留参数，暂未实现流式）
- **示例**：
  ```python
  get_dev_server_logs(tail=100)
  get_dev_server_logs(tail=0)  # 获取全部日志
  ```

#### `stop_dev_server()`
- **功能**：停止开发服务器
- **特性**：
  - 优先使用 SIGTERM 优雅停止
  - 等待最多 5 秒
  - 超时后使用 SIGKILL 强制停止
  - 自动清理 PID 文件
- **示例**：
  ```python
  stop_dev_server()
  ```

### 2. Engineer Agent 增强

#### Prompts 更新 (engineer.py)
- 更新工作流程，添加了开发服务器相关步骤
- 新增"开发服务器管理"工具说明
- 添加详细的使用建议和示例
- 包含不同框架的启动命令示例

#### Agent 配置更新 (agents/engineer.py)
- 引入四个新工具到 Engineer Agent
- 工具按类别组织（Workspace、Docker、Dev Server、搜索、RAG）

### 3. QA Agent 增强

为 QA Agent 添加了只读的开发服务器监控工具：
- `get_dev_server_status`：检查服务器运行状态
- `get_dev_server_logs`：查看服务器日志

这样 QA 可以：
- 验证应用是否正常运行
- 查看错误日志进行问题排查
- 确认修复后的运行状态

### 4. API 层支持

#### 新增接口 (mgx_api/api/dev.py)

##### `GET /apps/{session_id}/dev/server/status`
- 获取 dev server 运行状态
- 返回格式：
  ```json
  {
    "status": "success",
    "data": "Status: Running\nPID: 12345\nCommand: npm run dev"
  }
  ```

##### `GET /apps/{session_id}/dev/server/logs?tail=100`
- 获取 dev server 日志
- 支持 `tail` 参数（0-1000 行）
- 返回格式：
  ```json
  {
    "status": "success",
    "logs": "... log content ...",
    "tail": 100
  }
  ```

#### Service 层实现 (mgx_api/services/docker_service.py)

添加了两个新方法：
- `get_dev_server_status(workspace_id)`: 通过 docker exec 检查状态
- `get_dev_server_logs(workspace_id, tail)`: 通过 docker exec 读取日志

## 技术实现细节

### 1. 后台进程管理
```bash
# 启动命令模板
cd /workspace && \
echo 'npm run dev' > /workspace/.dev-server.cmd && \
nohup npm run dev > /workspace/.dev-server.log 2>&1 & \
echo $! > /workspace/.dev-server.pid
```

### 2. 状态检查
```bash
# 检查进程是否运行
[ -f /workspace/.dev-server.pid ] && \
kill -0 $(cat /workspace/.dev-server.pid) 2>/dev/null
```

### 3. 日志读取
```bash
# 读取最后 N 行日志
tail -n 100 /workspace/.dev-server.log
```

### 4. 优雅停止
```bash
# SIGTERM 优雅停止
kill $PID

# 等待 5 秒后 SIGKILL 强制停止
kill -9 $PID
```

## 文件结构

开发服务器相关文件位于容器内 `/workspace` 目录：

```
/workspace/
├── .dev-server.pid    # 进程 PID
├── .dev-server.cmd    # 启动命令
└── .dev-server.log    # 日志输出
```

## 使用流程示例

### Agent 使用流程

1. **启动开发服务器**
   ```python
   start_dev_server("npm run dev", port=3000)
   ```

2. **检查状态**
   ```python
   get_dev_server_status()
   ```

3. **查看日志**
   ```python
   get_dev_server_logs(tail=50)
   ```

4. **修复错误后重启**
   ```python
   stop_dev_server()
   start_dev_server("npm run dev", port=3000)
   ```

### API 调用流程

1. **前端获取状态**
   ```bash
   GET /apps/{session_id}/dev/server/status
   ```

2. **前端获取日志**
   ```bash
   GET /apps/{session_id}/dev/server/logs?tail=100
   ```

## 支持的框架

目前支持所有使用标准命令的框架：

| 框架 | 启动命令 | 默认端口 |
|------|---------|----------|
| Next.js | `npm run dev` | 3000 |
| Vite | `npm run dev` | 5173 |
| Nuxt.js | `npm run dev` | 3000 |
| 使用 pnpm | `pnpm dev` | 根据配置 |
| 使用 yarn | `yarn dev` | 根据配置 |

## 优势

1. **非阻塞**：后台运行，不阻塞 agent 执行其他任务
2. **可观测**：完整的日志记录和状态查询
3. **易调试**：实时查看错误和输出
4. **统一接口**：Agent 和 API 层都可以访问
5. **安全**：继承现有的安全检查机制

## 限制

1. 单 dev server 模式：同一时间只支持一个开发服务器
2. 日志大小：日志文件会持续增长，需要定期清理
3. 容器重启：容器重启后需要重新启动 dev server

## 下一步（后续阶段）

### 第二阶段计划
- 实时日志流（Server-Sent Events）
- 支持多个 dev server（前端+后端）
- 日志文件自动轮转

### 第三阶段计划
- WebSocket terminal（完整交互式终端）
- 前端 UI 集成（实时日志查看器）
- 性能监控（CPU、内存使用）

### 第四阶段计划（可选）
- 远程调试支持
- 热重载配置管理
- 环境变量动态配置

## 测试建议

### Agent 层测试
```python
# 1. 测试启动
result = start_dev_server("npm run dev", port=3000)
assert "✓ Dev server 启动成功" in result

# 2. 测试状态查询
status = get_dev_server_status()
assert "运行中" in status

# 3. 测试日志读取
logs = get_dev_server_logs(tail=10)
assert "ready" in logs or "compiled" in logs.lower()

# 4. 测试停止
result = stop_dev_server()
assert "已停止" in result
```

### API 层测试
```bash
# 测试状态接口
curl -X GET http://localhost:8000/apps/{session_id}/dev/server/status \
  -H "Authorization: Bearer {token}"

# 测试日志接口
curl -X GET "http://localhost:8000/apps/{session_id}/dev/server/logs?tail=50" \
  -H "Authorization: Bearer {token}"
```

## 总结

第一阶段成功实现了基础的开发服务器管理功能，为 Agent 提供了：
- ✅ 启动 dev server 的能力
- ✅ 读取 dev server stdout/stderr 的能力
- ✅ API 层通过接口获取 terminal log 的能力

这为后续的增强功能奠定了坚实的基础。
