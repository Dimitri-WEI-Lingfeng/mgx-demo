# MGX 开发环境镜像

这个目录包含用于不同开发框架的 Docker 开发环境镜像。这些镜像用于 MGX 平台的 app-dev-container，为 agent 生成的 web 应用提供开发运行环境。

## 镜像列表

### 已支持的框架

| 框架 | 目录 | Node 版本 | 其他特性 |
|------|------|-----------|----------|
| Next.js | `nextjs/` | 22 | npm/pnpm/yarn + 淘宝源 |

### 计划支持的框架

- [ ] FastAPI + React Vite SPA
- [ ] Express.js
- [ ] NestJS
- [ ] Django
- [ ] Flask + React

## 使用方式

### 1. 构建所有镜像

```bash
cd infra/dev_images
make build-all
```

### 2. 构建单个镜像

```bash
# Next.js
cd nextjs
docker build -t mgx-dev-nextjs:latest .
```

### 3. 推送到镜像仓库

```bash
# 标记镜像
docker tag mgx-dev-nextjs:latest your-registry/mgx-dev-nextjs:latest

# 推送
docker push your-registry/mgx-dev-nextjs:latest
```

## 镜像设计原则

1. **最小化**: 使用 slim 或 alpine 基础镜像，减小镜像体积
2. **开发友好**: 预装常用开发工具（git, curl, vim 等）
3. **国内优化**: 配置国内镜像源，加速依赖下载
4. **标准化**: 统一工作目录 `/workspace`
5. **可扩展**: 支持通过环境变量自定义配置

## 镜像命名规范

- 镜像名称: `mgx-dev-{framework}`
- 标签格式: `{version}` 或 `latest`
- 示例: `mgx-dev-nextjs:latest`, `mgx-dev-nextjs:1.0.0`

## 目录结构

```
dev_images/
├── README.md           # 本文件
├── Makefile           # 构建脚本（待添加）
├── nextjs/            # Next.js 开发环境
│   ├── Dockerfile
│   ├── README.md
│   └── .dockerignore
└── fastapi-vite/      # FastAPI + Vite 开发环境（待添加）
    ├── Dockerfile
    ├── README.md
    └── .dockerignore
```

## 在 MGX 平台中使用

这些镜像将在 MGX 平台中用于：

1. **app-dev-container**: Agent 生成代码后，使用对应框架的镜像启动开发容器
2. **本地挂载**: Workspace 目录挂载到容器 `/workspace`
3. **开发服务器**: 在容器中运行应用的开发服务器
4. **实时预览**: 通过 Apisix 网关代理访问开发中的应用

## 环境变量

所有镜像支持的通用环境变量：

- `WORKSPACE_PATH`: workspace 挂载路径（默认 `/workspace`）
- 各框架特定的环境变量请参考各镜像的 README

## 维护说明

### 添加新框架

1. 在 `dev_images/` 下创建新目录
2. 编写 `Dockerfile`、`README.md` 和 `.dockerignore`
3. 更新本 README 的镜像列表
4. 添加到 `Makefile` 的构建目标

### 镜像更新策略

- **Node.js 版本**: 跟随 LTS 版本更新
- **依赖更新**: 每月检查一次
- **安全补丁**: 及时应用安全更新
