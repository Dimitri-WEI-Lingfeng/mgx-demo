.PHONY: help build-all build-nextjs clean

help:
	@echo "MGX 开发环境镜像构建工具"
	@echo ""
	@echo "使用方法:"
	@echo "  make build-all       - 构建所有镜像"
	@echo "  make build-nextjs    - 构建 Next.js 镜像"
	@echo "  make clean           - 清理未使用的镜像"
	@echo ""

build-all: build-nextjs
	@echo "所有镜像构建完成"

build-nextjs:
	@echo "构建 Next.js 开发环境镜像..."
	cd nextjs && docker build -t mgx-dev-nextjs:latest .
	@echo "✓ Next.js 镜像构建完成"

clean:
	@echo "清理未使用的 Docker 镜像..."
	docker image prune -f
	@echo "✓ 清理完成"
