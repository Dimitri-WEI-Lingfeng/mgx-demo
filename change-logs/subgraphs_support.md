# 子图事件捕获支持 (subgraphs=True)

## 修改日期
2026-02-02

## 变更概述

在 `astream` 调用中启用 `subgraphs=True`，支持捕获嵌套 Agent（子图）中的事件。

## 主要变更

### 1. 启用子图支持

```python
async for chunk in team_graph.astream(
    initial_state,
    stream_mode=["updates", "messages"],
    subgraphs=True,  # ✅ 新增：捕获子图事件
):
```

### 2. 处理 Namespace

当 `subgraphs=True` 时，chunk 格式变为：`(namespace, mode, data)`

```python
# 解析 chunk
if len(chunk) == 3:
    namespace, mode, data = chunk  # 有 namespace（来自子图）
else:
    mode, data = chunk
    namespace = ()  # 无 namespace（根节点）
```

### 3. 事件中包含 Namespace

所有事件的 `data` 和 `metadata` 中都包含 namespace 信息：

```python
node_start_event = create_event(
    session_id=session_id,
    event_type=EventType.NODE_START,
    data={
        "node_name": node_name,
        "agent_name": node_name,
        "namespace": list(namespace) if namespace else None,  # ✅ 包含子图路径
    },
    trace_id=trace_id,
    agent_name=node_name,
)
node_start_event.metadata["namespace"] = list(namespace) if namespace else None
```

## Namespace 说明

### 什么是 Namespace？

Namespace 是一个 tuple，表示事件在图层次结构中的路径。

**示例：**

```python
# 根节点事件
namespace = ()

# 一级子图事件
namespace = ("engineer",)

# 二级嵌套子图事件
namespace = ("engineer", "code_writer:task_123")

# 三级嵌套子图事件
namespace = ("engineer", "code_writer:task_123", "file_handler:task_456")
```

### 使用场景

1. **多 Agent 协作**：跟踪每个 Agent 的执行路径
2. **调试**：定位问题发生在哪个子图中
3. **性能分析**：分析不同子图的执行时间
4. **可视化**：构建执行流程的树状结构

## 受影响的事件

所有事件类型都支持 namespace：

- ✅ `NODE_START` - 节点开始
- ✅ `NODE_END` - 节点结束
- ✅ `MESSAGE_COMPLETE` - 消息完成
- ✅ `LLM_STREAM` - LLM token 流
- ✅ `STAGE_CHANGE` - 阶段变更

## 实际应用示例

### 1. 显示事件来源

```python
async for chunk in team_graph.astream(..., subgraphs=True):
    if len(chunk) == 3:
        namespace, mode, data = chunk
        graph_path = " -> ".join(namespace) if namespace else "root"
        print(f"[{graph_path}] 事件: {mode}")
```

**输出示例：**
```
[root] 事件: updates
[engineer] 事件: messages
[engineer -> code_writer:task_123] 事件: messages
```

### 2. 过滤特定子图的事件

```python
async for chunk in team_graph.astream(..., subgraphs=True):
    if len(chunk) == 3:
        namespace, mode, data = chunk
        
        # 只处理来自 "engineer" 子图的事件
        if namespace and namespace[0] == "engineer":
            await process_engineer_event(mode, data)
```

### 3. 构建执行树

```python
execution_tree = {}

async for chunk in team_graph.astream(..., subgraphs=True):
    if len(chunk) == 3:
        namespace, mode, data = chunk
        
        # 构建树状结构
        current = execution_tree
        for node in namespace:
            if node not in current:
                current[node] = {}
            current = current[node]
        
        # 记录事件
        if "events" not in current:
            current["events"] = []
        current["events"].append((mode, data))

# execution_tree 示例：
# {
#     "engineer": {
#         "events": [...],
#         "code_writer:task_123": {
#             "events": [...],
#         }
#     }
# }
```

### 4. 性能分析

```python
import time

performance_stats = {}

async for chunk in team_graph.astream(..., subgraphs=True):
    if len(chunk) == 3:
        namespace, mode, data = chunk
        
        if mode == "updates":
            for node_name, node_state in data.items():
                path = "/".join(namespace) if namespace else "root"
                key = f"{path}/{node_name}"
                
                if key not in performance_stats:
                    performance_stats[key] = {
                        "start_time": time.time(),
                        "end_time": None,
                    }
                else:
                    performance_stats[key]["end_time"] = time.time()

# 计算每个节点的执行时间
for path, stats in performance_stats.items():
    if stats["end_time"]:
        duration = stats["end_time"] - stats["start_time"]
        print(f"{path}: {duration:.2f}s")
```

## 数据库查询示例

### 按 Namespace 查询事件

```python
# 查询根节点事件
root_events = await event_dao.get_events(
    session_id=session_id,
    filters={"metadata.namespace": None}
)

# 查询特定子图的事件
engineer_events = await event_dao.get_events(
    session_id=session_id,
    filters={"metadata.namespace": ["engineer"]}
)

# 查询特定深度的事件（二级子图）
nested_events = await event_dao.get_events(
    session_id=session_id,
    filters={"metadata.namespace": {"$size": 2}}  # MongoDB 语法
)
```

## 前端展示示例

### React 组件

```tsx
function EventViewer({ events }) {
  // 按 namespace 分组
  const groupedEvents = groupBy(events, event => 
    event.metadata.namespace?.join(" -> ") || "root"
  );
  
  return (
    <div>
      {Object.entries(groupedEvents).map(([path, events]) => (
        <div key={path} style={{ marginLeft: path === "root" ? 0 : 20 }}>
          <h3>{path}</h3>
          <EventList events={events} />
        </div>
      ))}
    </div>
  );
}
```

### 树状视图

```tsx
function ExecutionTree({ events }) {
  const tree = buildTreeFromEvents(events);
  
  return (
    <TreeView>
      {renderNode(tree, "root")}
    </TreeView>
  );
}

function renderNode(node, name) {
  return (
    <TreeNode label={name}>
      <EventList events={node.events} />
      {Object.entries(node.children || {}).map(([childName, childNode]) =>
        renderNode(childNode, childName)
      )}
    </TreeNode>
  );
}
```

## 注意事项

1. **性能影响**：`subgraphs=True` 会捕获所有子图事件，数据量可能较大
2. **存储**：确保数据库有足够空间存储 namespace 信息
3. **序列化**：Namespace 是 tuple，存储时需要转换为 list
4. **过滤**：建议在前端或 API 层提供 namespace 过滤功能

## 相关文件

- `/Users/feng/codes/mgx-demo/src/agents/run_agent.py` - 实现文件
- `/Users/feng/codes/mgx-demo/change-logs/astream_migration.md` - 迁移指南
- `/Users/feng/codes/mgx-demo/change-logs/streaming_events_implementation.md` - 事件实现文档
