# 代码重构指南

## 概览

本项目已按照层级架构进行重构，将代码按职责分层，提高可维护性和可扩展性。

## 新的目录结构

### 1. `src/mgx_api/` - MGX API 模块

```
src/mgx_api/
├── api/                    # API 路由层（Router Layer）
│   ├── __init__.py        # 路由聚合
│   ├── health.py          # 健康检查路由
│   ├── auth.py            # 认证相关路由
│   ├── sessions.py        # Session 管理路由
│   ├── workspaces.py      # Workspace 文件操作路由
│   ├── dev.py             # Dev container 路由
│   ├── prod.py            # Production 路由
│   └── agent.py           # Agent 任务路由
├── services/               # 业务逻辑层（Service Layer）
│   ├── __init__.py
│   ├── session_service.py # Session 业务逻辑
│   ├── workspace_service.py # Workspace 业务逻辑
│   ├── docker_service.py  # Docker 管理业务逻辑
│   └── apisix_service.py  # Apisix 路由管理业务逻辑
├── dao/                    # 数据访问层（Data Access Layer）
│   ├── __init__.py
│   ├── base.py            # 基础 DAO 接口
│   └── session_dao.py     # Session 数据访问
├── dependencies/           # 依赖注入层（Dependency Injection Layer）
│   ├── __init__.py
│   ├── auth.py            # 认证依赖
│   └── database.py        # 数据库依赖
├── schemas/                # API 模型层（Schema Layer）
│   ├── __init__.py
│   ├── session.py         # Session 相关模型
│   ├── workspace.py       # Workspace 相关模型
│   ├── container.py       # Container 相关模型
│   └── agent.py           # Agent 相关模型
├── main.py                 # FastAPI 应用入口
└── cli.py                  # CLI 工具
```

### 2. `src/shared/` - 共享模块

```
src/shared/
├── config/                 # 配置层
│   ├── __init__.py
│   └── settings.py        # 应用配置
├── database/               # 数据库层
│   ├── __init__.py
│   └── mongodb.py         # MongoDB 连接
├── security/               # 安全层
│   ├── __init__.py
│   ├── password.py        # 密码哈希
│   └── jwt.py             # JWT 处理
└── utils/                  # 工具层
    ├── __init__.py
    └── filesystem.py      # 文件系统工具
```

## 层级职责说明

### API 层（`mgx_api/api/`）
- **职责**：定义 HTTP 路由端点，处理请求/响应
- **原则**：薄层，只负责参数验证和调用 Service 层
- **示例**：
  ```python
  from mgx_api.services import SessionService
  
  @router.post("/sessions")
  async def create_session(body: SessionCreate):
      service = SessionService()
      return await service.create_session(body.name, body.framework)
  ```

### Services 层（`mgx_api/services/`）
- **职责**：实现核心业务逻辑
- **原则**：包含业务规则、编排多个 DAO、处理事务逻辑
- **示例**：
  ```python
  class SessionService:
      async def create_session(self, name: str, framework: str):
          # 业务逻辑：创建 workspace、保存到数据库等
          pass
  ```

### DAO 层（`mgx_api/dao/`）
- **职责**：抽象数据库操作接口
- **原则**：只关注数据的 CRUD 操作，不包含业务逻辑
- **示例**：
  ```python
  class SessionDAO(BaseDAO):
      async def find_by_id(self, session_id: str):
          db = get_db()
          return await db["sessions"].find_one({"session_id": session_id})
  ```

### Dependencies 层（`mgx_api/dependencies/`）
- **职责**：FastAPI 依赖注入
- **原则**：提供可重用的依赖，如认证、数据库会话等
- **示例**：
  ```python
  async def get_current_user(token: str = Depends(oauth2_scheme)):
      # 验证 token，返回用户信息
      pass
  ```

### Schemas 层（`mgx_api/schemas/`）
- **职责**：定义 API 请求/响应模型
- **原则**：使用 Pydantic 模型进行数据验证
- **示例**：
  ```python
  class SessionCreate(BaseModel):
      name: str
      framework: str
  ```

## 导入方式

### 新代码推荐导入方式

```python
# 从具体模块导入（推荐）
from mgx_api.schemas import SessionCreate, SessionResponse
from mgx_api.services import SessionService
from mgx_api.dao import SessionDAO
from mgx_api.dependencies import get_current_user

from shared.config import settings
from shared.database import get_db
from shared.security import hash_password, create_access_token
from shared.utils import safe_join
```

### 向后兼容导入（旧代码仍可使用）

为了保持向后兼容，以下导入方式仍然有效：

```python
# 这些导入仍然工作（通过 __init__.py 重新导出）
from shared.settings import settings  # ✓ 仍可用
from shared.db import get_db          # ✓ 仍可用
from shared.security import hash_password  # ✓ 仍可用
from shared.utils import safe_join    # ✓ 仍可用
```

## 迁移指南

如果你有使用旧结构的代码，可以按以下步骤迁移：

### 1. 更新 shared 模块导入

```python
# 旧方式
from shared.settings import settings
from shared.db import get_db
from shared.security import hash_password

# 新方式（推荐）
from shared.config import settings
from shared.database import get_db
from shared.security import hash_password
```

### 2. 更新 mgx_api 模块导入

```python
# 旧方式
from mgx_api.schemas import SessionCreate
from mgx_api.workspace import create_session
from mgx_api.auth import get_current_user

# 新方式
from mgx_api.schemas import SessionCreate
from mgx_api.services import SessionService
from mgx_api.dependencies import get_current_user
```

## 添加新功能指南

### 添加新的 API 端点

1. 在 `schemas/` 中定义请求/响应模型
2. 在 `dao/` 中添加数据访问方法（如果需要）
3. 在 `services/` 中实现业务逻辑
4. 在 `api/` 中添加路由端点
5. 在 `api/__init__.py` 中注册新路由

示例：添加一个新的用户管理功能

```python
# 1. schemas/user.py
class UserCreate(BaseModel):
    username: str
    email: str

# 2. dao/user_dao.py
class UserDAO(BaseDAO):
    async def find_by_email(self, email: str):
        pass

# 3. services/user_service.py
class UserService:
    async def create_user(self, username: str, email: str):
        pass

# 4. api/users.py
@router.post("/users")
async def create_user(body: UserCreate):
    service = UserService()
    return await service.create_user(body.username, body.email)

# 5. api/__init__.py
from . import users
router.include_router(users.router, prefix="/api", tags=["Users"])
```

## 最佳实践

1. **分层清晰**：每层只关注自己的职责，不跨层调用
2. **依赖注入**：使用 FastAPI 的依赖注入，而不是全局变量
3. **类型提示**：所有函数都应该有完整的类型提示
4. **异步优先**：使用 async/await 处理 I/O 操作
5. **错误处理**：在 Service 层处理业务异常，在 API 层转换为 HTTP 响应

## 测试指南

### 单元测试结构

```
tests/
├── unit/
│   ├── test_services/
│   ├── test_dao/
│   └── test_schemas/
└── integration/
    └── test_api/
```

### Mock 依赖

```python
# 测试 Service 时 mock DAO
@pytest.fixture
def mock_session_dao():
    return Mock(spec=SessionDAO)

def test_create_session(mock_session_dao):
    service = SessionService()
    service.dao = mock_session_dao
    # 测试逻辑...
```

## 常见问题

### Q: 为什么要分这么多层？
A: 分层架构使代码职责清晰，易于测试和维护。每层可以独立演化，降低耦合度。

### Q: Service 层和 DAO 层的区别是什么？
A: DAO 层只负责数据库的 CRUD 操作，Service 层包含业务逻辑和业务规则。

### Q: 旧代码会不会出问题？
A: 不会，我们在 `__init__.py` 中保持了向后兼容的导出。

### Q: 何时应该创建新的 Service？
A: 当有新的业务领域或功能模块时，应该创建对应的 Service。

## 下一步

- [ ] 为每个层级添加单元测试
- [ ] 添加 API 文档生成
- [ ] 实现日志记录中间件
- [ ] 添加性能监控
