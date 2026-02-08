# API 设计最佳实践（默认知识库）

- RESTful 原则：资源导向、HTTP 方法语义化（GET 查询、POST 创建、PUT 更新、DELETE 删除）
- 错误处理：返回统一的错误响应格式，包含 error_code、message 和 details
- 认证：使用 JWT 或 OAuth2，在 Header 中传递 Authorization: Bearer <token>
- 版本控制：推荐 URL 版本 /api/v1/ 或 Header 版本
