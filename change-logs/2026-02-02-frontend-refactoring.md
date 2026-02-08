# 前端重构 - 两页应用架构

**日期**: 2026-02-02  
**类型**: Feature  
**影响范围**: 前端架构、后端 API

## 概述

将前端从单页应用重构为基于路由的两页应用，提供更好的用户体验和功能组织。新架构包含：
- 首页：Sessions 列表和创建功能
- 详情页：Chat 对话（左侧）+ 资源 Tabs（右侧）

## 后端 API 新增

### 1. Sessions API
- **GET `/api/sessions`** - 获取当前用户的所有 sessions 列表
  - 文件: `src/mgx_api/api/sessions.py`
  - 使用已有的 `SessionService.list_user_sessions()` 方法

### 2. Agent History API
- **GET `/api/apps/{session_id}/agent/history`** - 获取历史消息
  - 文件: `src/mgx_api/api/agent.py`
  - 返回: `{messages: [Message]}`
  - 用途: 进入详情页时初始化加载历史消息
  - 使用 `MessageDAO.get_session_messages()` 方法

### 3. Database Query API
- **GET `/api/apps/{session_id}/database/collections`** - 列出 app 数据库的所有集合
- **POST `/api/apps/{session_id}/database/query`** - 查询集合数据
  - 文件: `src/mgx_api/api/database.py`
  - Service: `src/mgx_api/services/database_service.py`
  - Schemas: `src/mgx_api/schemas/database.py`

### 4. Settings 更新
- 添加 `mongodb_apps_db` 配置项，指定 app 数据库名称（默认: `mgx_apps`）

## 前端类型系统

### 新增类型定义模块 (`frontend/src/types/`)
创建完整的 TypeScript 类型定义，提供类型安全和更好的开发体验：

- `session.ts` - Session 相关类型
- `message.ts` - Message 和 Content Part 类型
- `workspace.ts` - 文件系统相关类型
- `container.ts` - 容器相关类型
- `database.ts` - 数据库查询相关类型
- `agent.ts` - Agent 和事件类型
- `index.ts` - 统一导出

### API Client 更新
- `frontend/src/api/client.ts` 使用新的类型定义
- 所有 API 调用函数都有明确的类型签名

## 前端架构重构

### 路由配置 (`App.tsx`)
使用 `react-router-dom` 实现路由：
- `/login` - 登录页
- `/` - 首页（SessionsListPage）
- `/sessions/:sessionId` - Session 详情页（SessionDetailPage）
- 包含私有路由保护机制

### 页面组件

#### 1. SessionsListPage (`pages/SessionsListPage.tsx`)
首页，包含：
- **Sessions 列表**：展示当前用户的所有 sessions
  - 卡片式展示，包含名称、框架、创建时间
  - 点击跳转到详情页
- **创建新 Session 表单**：
  - 输入 app 名称
  - 选择框架（fastapi-vite / nextjs）
  - 提交后自动跳转到详情页

#### 2. SessionDetailPage (`pages/SessionDetailPage.tsx`)
Session 详情页，左右分栏布局：
- **顶部**: Session 信息和返回按钮
- **左侧面板**: ChatPanel 组件
- **右侧面板**: ResourceTabs 组件

### 核心组件

#### ChatPanel (`components/ChatPanel.tsx`)
左侧 chat 面板，功能包括：
- **初始加载历史消息**: 调用 `/agent/history` API
- **消息列表**: 
  - 显示用户消息和 agent 响应
  - 支持多模态内容（文本、工具调用、工具结果）
  - 自动滚动到最新消息
- **消息输入框**: 发送 prompt 给 agent
- **SSE 流式处理**:
  - 使用 EventSource API 连接 `/agent/generate`
  - 实时接收和显示流式响应
  - 处理不同类型的事件（message_delta, tool_start, finish 等）
  - TODO: 实现断线重连机制

#### ResourceTabs (`components/ResourceTabs.tsx`)
右侧资源 tabs 容器，包含三个 tab：

1. **Tab 1 - File Editor** (`tabs/FileEditorTab.tsx`)
   - 复用现有的 `FileExplorer` 组件
   - 文件树浏览器 + 代码编辑器

2. **Tab 2 - Dev Server** (`tabs/DevServerTab.tsx`)
   - 显示 dev server 状态
   - 使用 iframe 嵌入 dev server 页面
   - Dev URL: `/apps/{app_name}/dev/`
   - 自动轮询状态（每 5 秒）

3. **Tab 3 - Database** (`tabs/DatabaseTab.tsx`)
   - 列出 app 数据库的所有集合
   - 提供 MongoDB 查询界面
   - 支持 JSON filter 查询
   - 显示查询结果和文档数量

## 文件清单

### 后端新增/修改文件
```
src/mgx_api/api/
├── sessions.py (修改 - 添加 list_sessions)
├── agent.py (修改 - 添加 get_history)
├── database.py (新增)
└── __init__.py (修改 - 注册 database router)

src/mgx_api/services/
├── database_service.py (新增)
└── __init__.py (修改)

src/mgx_api/schemas/
├── database.py (新增)
└── __init__.py (修改)

src/shared/config/
└── settings.py (修改 - 添加 mongodb_apps_db)
```

### 前端新增/修改文件
```
frontend/src/
├── App.tsx (重构 - 路由配置)
├── api/client.ts (修改 - 添加新 API + 类型)
├── types/ (新增目录)
│   ├── session.ts
│   ├── message.ts
│   ├── workspace.ts
│   ├── container.ts
│   ├── database.ts
│   ├── agent.ts
│   └── index.ts
├── pages/ (新增目录)
│   ├── SessionsListPage.tsx
│   └── SessionDetailPage.tsx
└── components/
    ├── ChatPanel.tsx (新增)
    ├── ResourceTabs.tsx (新增)
    └── tabs/ (新增目录)
        ├── FileEditorTab.tsx
        ├── DevServerTab.tsx
        └── DatabaseTab.tsx
```

## API 端点变化总结

### 新增端点
```
GET  /api/sessions                                      # 列出 sessions
GET  /api/apps/{session_id}/agent/history               # 获取历史消息
GET  /api/apps/{session_id}/database/collections        # 列出集合
POST /api/apps/{session_id}/database/query              # 查询数据库
```

### 已有端点
```
POST /api/sessions                                      # 创建 session
GET  /api/sessions/{session_id}                         # 获取单个 session
POST /api/apps/{session_id}/agent/generate              # 启动 agent 并 SSE 流式返回
GET  /api/apps/{session_id}/agent/stream-continue       # 断线重连
GET  /api/apps/{session_id}/dev/status                  # Dev server 状态
GET  /api/workspaces/{workspace_id}/entries             # 列出目录
GET  /api/workspaces/{workspace_id}/files               # 读取文件
PUT  /api/workspaces/{workspace_id}/files               # 写入文件
```

## 技术亮点

1. **完整的类型系统**: TypeScript 类型定义覆盖所有 API 接口
2. **组件化设计**: 清晰的组件层次和职责划分
3. **SSE 流式处理**: 实时接收和显示 agent 响应
4. **路由管理**: 使用 react-router-dom 实现 SPA 路由
5. **代码复用**: FileExplorer 组件在新架构中被复用
6. **响应式布局**: 左右分栏自适应布局

## 待优化项

1. **断线重连**: ChatPanel 需要实现完整的断线重连机制
2. **错误处理**: 可以添加更友好的错误提示和重试机制
3. **加载状态**: 可以添加骨架屏提升用户体验
4. **MongoDB 查询**: 数据库 tab 可以支持更复杂的查询操作
5. **UI 库**: 考虑引入 UI 库（如 Ant Design）改善整体视觉效果
6. **性能优化**: 可以添加虚拟滚动、分页等优化

## 兼容性说明

- 保留了所有原有的 API 端点，向后兼容
- 原有的 `FileExplorer` 组件被复用，无需修改
- 不影响已有的 Agent、Docker、Workspace 等功能

## 测试建议

1. 测试 sessions 列表加载和创建
2. 测试进入详情页后历史消息的加载
3. 测试发送消息和 SSE 流式接收
4. 测试三个资源 tab 的切换和功能
5. 测试 dev server iframe 的显示
6. 测试数据库查询功能
7. 测试路由导航和返回功能
