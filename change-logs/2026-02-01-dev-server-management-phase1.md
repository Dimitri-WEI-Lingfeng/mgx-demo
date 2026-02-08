# Change Log - 2026-02-01

## 开发服务器管理功能 - 第一阶段

### 变更类型
功能新增 (Feature)

### 变更概述
为 Agent 添加了启动和管理开发服务器的能力，包括后台执行、日志重定向和状态查询功能。同时在 API 层提供了相应的接口供前端调用。

### 背景
之前 Agent 只能通过 `exec_command` 执行同步命令，无法启动长时间运行的开发服务器（如 `npm run dev`）并持续监控其输出。这限制了 Agent 进行实时测试和调试的能力。

### 解决方案
实现了基于文件的进程管理方案：
- 使用 `nohup` 在后台启动 dev server
- 将日志重定向到 `/workspace/.dev-server.log`
- 将进程 PID 保存到 `/workspace/.dev-server.pid`
- 提供状态查询和日志读取工具

### 详细变更

#### 1. Agent 工具层 (src/agents/web_app_team/tools/docker_tools.py)

**新增工具函数：**

- `start_dev_server(command, working_dir, port)`
  - 后台启动开发服务器
  - 自动检测重复启动
  - 启动后验证进程状态
  - 返回最近的日志输出

- `get_dev_server_status()`
  - 检查进程是否运行
  - 显示 PID、启动命令
  - 尝试检测监听端口
  - 显示最近的日志

- `get_dev_server_logs(tail, follow)`
  - 读取日志文件
  - 支持 tail 参数
  - 为未来流式日志预留接口

- `stop_dev_server()`
  - 优雅停止（SIGTERM）
  - 超时后强制停止（SIGKILL）
  - 自动清理 PID 文件

**技术细节：**
```bash
# 启动命令模板
nohup {command} > /workspace/.dev-server.log 2>&1 & echo $! > /workspace/.dev-server.pid
```

#### 2. Engineer Agent 增强

**文件：** `src/agents/web_app_team/prompts/engineer.py`

**变更内容：**
- 更新工作流程，添加开发服务器相关步骤
- 新增"开发服务器管理"工具说明
- 添加详细的使用建议和不同框架的示例

**文件：** `src/agents/web_app_team/agents/engineer.py`

**变更内容：**
- 引入四个新工具
- 工具按类别组织

#### 3. QA Agent 增强

**文件：** `src/agents/web_app_team/agents/qa.py`

**变更内容：**
- 添加 `get_dev_server_status` 工具
- 添加 `get_dev_server_logs` 工具
- QA 可以查看开发服务器状态和日志进行测试验证

#### 4. API 层支持

**文件：** `src/mgx_api/api/dev.py`

**新增接口：**

- `GET /apps/{session_id}/dev/server/status`
  - 查询 dev server 运行状态
  - 返回 PID、命令等信息

- `GET /apps/{session_id}/dev/server/logs?tail=100`
  - 获取 dev server 日志
  - 支持 tail 参数（0-1000）

**文件：** `src/mgx_api/services/docker_service.py`

**新增方法：**

- `get_dev_server_status(workspace_id)`
  - 通过 docker exec 检查容器内进程状态

- `get_dev_server_logs(workspace_id, tail)`
  - 通过 docker exec 读取日志文件

#### 5. 文档和测试

**新增文件：**
- `docs/dev_server_management_phase1.md` - 完整的功能文档
- `scripts/test_dev_server_tools.py` - 测试示例脚本

### 影响范围

#### 受影响的文件
```
src/agents/web_app_team/
├── tools/docker_tools.py          (修改，+280 行)
├── prompts/engineer.py            (修改，+20 行)
└── agents/
    ├── engineer.py                (修改，+5 行)
    └── qa.py                      (修改，+3 行)

src/mgx_api/
├── api/dev.py                     (修改，+50 行)
└── services/docker_service.py     (修改，+90 行)

docs/
└── dev_server_management_phase1.md (新增)

scripts/
└── test_dev_server_tools.py       (新增)

change-logs/
└── 2026-02-01-dev-server-management-phase1.md (新增)
```

#### 向后兼容性
✅ 完全向后兼容
- 新增功能，不影响现有代码
- 不修改现有工具的行为
- 现有 Agent 可选择性使用新工具

### 使用示例

#### Agent 代码示例
```python
from agents.web_app_team.tools.docker_tools import (
    start_dev_server,
    get_dev_server_status,
    get_dev_server_logs,
    stop_dev_server,
)

# 启动开发服务器
result = start_dev_server.invoke({
    "command": "npm run dev",
    "port": 3000
})

# 检查状态
status = get_dev_server_status.invoke({})

# 查看日志
logs = get_dev_server_logs.invoke({"tail": 50})

# 停止服务器
stop_dev_server.invoke({})
```

#### API 调用示例
```bash
# 查询状态
curl -X GET "http://localhost:8000/apps/abc123/dev/server/status" \
  -H "Authorization: Bearer token"

# 获取日志
curl -X GET "http://localhost:8000/apps/abc123/dev/server/logs?tail=100" \
  -H "Authorization: Bearer token"
```

### 测试

#### 单元测试
```bash
# 运行测试脚本
python scripts/test_dev_server_tools.py

# 测试重启场景
python scripts/test_dev_server_tools.py restart
```

#### 集成测试
需要测试的场景：
1. ✅ 启动 dev server 并验证进程运行
2. ✅ 查询状态和日志
3. ✅ 停止 dev server
4. ✅ 重复启动检测
5. ✅ API 接口调用

### 已知限制

1. **单 dev server 模式**
   - 同一时间只支持一个开发服务器
   - 如需前后端分离，需要扩展支持多进程

2. **日志管理**
   - 日志文件会持续增长
   - 建议定期清理或实现日志轮转

3. **容器生命周期**
   - 容器重启后需要重新启动 dev server
   - PID 文件不会自动清理

4. **流式日志**
   - 当前版本不支持实时日志流
   - 需要轮询 `get_dev_server_logs` 获取最新日志

### 后续计划

#### 第二阶段
- [ ] 实时日志流（Server-Sent Events）
- [ ] 支持多个 dev server
- [ ] 日志文件自动轮转

#### 第三阶段
- [ ] WebSocket terminal
- [ ] 前端 UI 集成
- [ ] 性能监控

### 验收标准

- [x] Agent 可以启动 dev server 并在后台运行
- [x] Agent 可以读取 dev server 的 stdout/stderr
- [x] API 层提供接口获取 terminal log
- [x] 无 breaking changes
- [x] 添加完整文档
- [x] 提供测试示例

### 审查者

请重点关注：
1. 安全性：后台进程管理是否安全
2. 资源管理：进程清理是否完善
3. 错误处理：异常情况是否妥善处理
4. 用户体验：工具使用是否直观

### 相关 Issue/PR

- 需求来源：用户提出赋予 agent 启动 dev server 的能力
- 设计文档：`docs/dev_server_management_phase1.md`

### 作者
AI Assistant

### 审查状态
- [ ] Code Review
- [ ] 功能测试
- [ ] 文档审查
- [ ] 安全审查
