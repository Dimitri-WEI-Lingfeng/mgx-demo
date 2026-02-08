# Quick Start Guide - Agent SSE Streaming

## 快速开始

这个指南将帮助你快速上手使用 MGX Agent SSE Streaming 系统。

## 1. 安装依赖

```bash
cd /Users/feng/codes/mgx-demo

# 使用 uv 安装依赖
uv pip install -e .

# 或使用 pip
pip install -e .
```

## 2. 配置环境变量

复制并编辑 `.env` 文件：

```bash
cp .env.example .env
```

最小配置：

```bash
# MongoDB
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB=mgx

# Redis
REDIS_URL=redis://localhost:6379/0

# Langfuse (可选)
LANGFUSE_ENABLED=false
```

## 3. 启动依赖服务

```bash
# 使用 Docker Compose 启动 MongoDB 和 Redis
docker-compose up -d mongodb redis
```

## 4. 初始化数据库

```bash
# 创建数据库索引
python -m src.shared.database.init_db
```

输出应该显示：

```
Creating database indexes...
✓ Event indexes created
✓ Message indexes created
Database initialization complete!
```

## 5. 启动服务

### 启动 FastAPI 服务器

```bash
# 终端 1
python -m mgx_api.cli
# 或
uvicorn mgx_api.main:app --reload --host 0.0.0.0 --port 8000
```

### 启动 Celery Worker

```bash
# 终端 2
uv run agent-worker
# 或
celery -A scheduler.tasks worker --loglevel=info
```

## 6. 测试 SSE Streaming

### 使用测试脚本

```bash
# 终端 3
python scripts/test_sse_stream.py
```

### 使用 curl

```bash
# 注意：需要先创建 session 和获取认证 token
curl -N -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Create a simple hello world API"}' \
  http://localhost:8000/api/apps/SESSION_ID/agent/generate
```

### 使用 JavaScript (浏览器)

```html
<!DOCTYPE html>
<html>
<head>
  <title>SSE Stream Test</title>
</head>
<body>
  <h1>Agent Streaming Test</h1>
  <div id="output"></div>
  
  <script>
    const sessionId = 'your_session_id';
    const token = 'your_token';
    
    // 注意：EventSource 不支持 POST，需要使用 fetch
    fetch(`http://localhost:8000/api/apps/${sessionId}/agent/generate`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        prompt: 'Create a simple hello world API'
      })
    }).then(response => {
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      
      function read() {
        reader.read().then(({done, value}) => {
          if (done) {
            console.log('Stream complete');
            return;
          }
          
          const text = decoder.decode(value);
          document.getElementById('output').innerText += text;
          read();
        });
      }
      
      read();
    });
  </script>
</body>
</html>
```

## 7. 配置 Langfuse (可选)

如果你想启用 Langfuse 追踪：

### 7.1 获取 API Keys

1. 访问 https://cloud.langfuse.com
2. 创建账户并登录
3. 创建新项目
4. 在 Settings → API Keys 生成 keys

### 7.2 配置环境变量

在 `.env` 文件中添加：

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_ENABLED=true
```

### 7.3 重启服务

```bash
# 重启 Celery worker 以使配置生效
# Ctrl+C 停止，然后重新启动
uv run agent-worker
```

### 7.4 查看 Traces

1. 运行 agent task
2. 从 SSE 事件中获取 `trace_id`
3. 访问 `https://cloud.langfuse.com/trace/{trace_id}`

## 8. 验证安装

### 检查服务状态

```bash
# 检查 FastAPI
curl http://localhost:8000/health

# 检查 MongoDB
mongosh --eval "db.adminCommand('ping')"

# 检查 Redis
redis-cli ping
```

### 检查数据库索引

```bash
python -m src.shared.database.init_db
```

应该看到已存在的索引信息。

## 9. 下一步

- 📖 阅读 [SSE Streaming Guide](./sse_streaming_guide.md) 了解 API 详情
- 🚀 查看 [Performance Optimization](./performance_optimization.md) 优化性能
- 📊 阅读 [Implementation Summary](./agent_streaming_implementation.md) 了解架构

## 常见问题

### Q: 启动 Celery worker 报错

**A:** 确保：
1. Redis 正在运行：`redis-cli ping`
2. Python path 正确：`export PYTHONPATH=/Users/feng/codes/mgx-demo/src`
3. 依赖已安装：`pip list | grep celery`

### Q: SSE 连接超时

**A:** 检查：
1. MongoDB 正在运行并可访问
2. 数据库索引已创建
3. Celery worker 正在运行并处理任务

### Q: 没有收到事件

**A:** 调试步骤：
1. 检查 Celery worker 日志
2. 查询数据库确认事件已写入：
   ```bash
   mongosh mgx --eval "db.events.find().sort({timestamp:-1}).limit(5)"
   ```
3. 检查 FastAPI 日志

### Q: Langfuse 不工作

**A:** 确认：
1. `LANGFUSE_ENABLED=true`
2. API keys 正确
3. 网络可以访问 langfuse.com
4. Celery worker 已重启

## 故障排查

### 查看日志

```bash
# FastAPI 日志
# 在 uvicorn 输出中查看

# Celery 日志
# 在 celery worker 输出中查看

# MongoDB 日志
docker logs mgx-mongodb

# Redis 日志
docker logs mgx-redis
```

### 清理并重启

```bash
# 停止所有服务
# Ctrl+C 停止 FastAPI 和 Celery

# 清理 Redis
redis-cli FLUSHALL

# 清理 MongoDB (可选，会删除所有数据)
mongosh mgx --eval "db.events.deleteMany({})"
mongosh mgx --eval "db.messages.deleteMany({})"

# 重新初始化
python -m src.shared.database.init_db

# 重启服务
python -m mgx_api.cli
uv run agent-worker
```

## 开发工作流

1. **修改代码** → 2. **重启服务** → 3. **测试**

FastAPI 支持热重载：
```bash
uvicorn mgx_api.main:app --reload
```

Celery worker 需要手动重启：
```bash
# Ctrl+C 停止
uv run agent-worker
```

## 性能测试

```bash
# TODO: 添加负载测试脚本
# python scripts/load_test_sse.py --clients 100 --duration 60
```

## 生产部署

参考 `docs/deployment.md` (待添加) 了解：
- Docker 容器化
- Kubernetes 部署
- 负载均衡配置
- 监控和告警设置

## 获取帮助

- 📚 查看 `docs/` 目录下的完整文档
- 🐛 报告问题：在 GitHub Issues 中创建 issue
- 💬 讨论：在项目 Discussions 中提问

## 成功标志

如果你看到以下输出，说明系统运行正常：

✅ FastAPI 服务器启动并监听 8000 端口  
✅ Celery worker 显示 "ready"  
✅ 数据库索引创建成功  
✅ SSE 测试脚本能接收到事件  
✅ (可选) Langfuse 显示 traces  

恭喜！你已经成功设置了 MGX Agent SSE Streaming 系统！🎉
