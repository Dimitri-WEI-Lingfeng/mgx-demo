# 默认知识库

此目录存放 `DefaultKnowledgeBase` 使用的兜底知识内容，按分类拆分为独立的 Markdown 文件。

## 文件说明

- `*.md`：每个文件对应一个知识分类，文件名为分类 ID（如 `architecture_patterns.md`）
- `fallback.md`：当未指定分类或分类不存在时返回的默认内容

## 维护方式

1. **修改现有知识**：直接编辑对应的 `.md` 文件
2. **新增分类**：添加新的 `.md` 文件，并在 `DefaultKnowledgeBase.COLLECTIONS` 中注册
3. **删除分类**：删除对应 `.md` 文件，并从 `COLLECTIONS` 中移除

## 当前分类

| 文件名 | 说明 |
|--------|------|
| architecture_patterns | 架构设计模式 |
| api_design | API 设计最佳实践 |
| react_docs | React 文档 |
| nextjs_docs | Next.js 文档 |
| fastapi_docs | FastAPI 文档 |
| testing_practices | 测试最佳实践 |
| code_examples | 代码示例库 |
