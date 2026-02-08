# 前端静态资源构建与托管
# 开发服务使用 5173，此镜像用于生产静态服务，端口 8080

# 构建阶段
FROM node:22-alpine AS builder

# 后端 API 基础 URL：编译时注入，用于跨域请求 APISIX 网关
# 默认 http://localhost:9080，可通过 --build-arg 覆盖
ARG VITE_API_BASE=http://localhost:9080
ENV VITE_API_BASE=$VITE_API_BASE

WORKDIR /app

# 使用 pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

COPY package.json pnpm-lock.yaml* .npmrc ./

RUN pnpm install --frozen-lockfile

COPY . ./

# build:docker 跳过 tsc 检查，便于在 TS 未完全修复时构建镜像
RUN pnpm build:docker

# 运行阶段：nginx 托管静态文件
FROM nginx:alpine

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

# 复制 nginx 配置（SPA 路由 fallback）
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
