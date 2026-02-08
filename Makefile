.PHONY: help install dev up down logs clean clean-mgx-dev frontend backend backend-local test build-agent build-mgx test-image

help:
	@echo "MGX Demo - Available Commands"
	@echo ""
	@echo "  make install        - Install Python and frontend dependencies"
	@echo "  make dev            - Start all services (backend + frontend)"
	@echo "  make up             - Start backend services only (docker compose)"
	@echo "  make down           - Stop backend services"
	@echo "  make logs           - Show backend logs"
	@echo "  make frontend       - Start frontend dev server"
	@echo "  make backend        - Rebuild and restart backend services"
	@echo "  make backend-local  - Run MGX API locally (uv run mgx backend main.py)"
	@echo "  make build-agent    - Build MGX unified image (mgx:latest)"
	@echo "  make build-mgx     - Alias for build-agent"
	@echo "  make test-image     - Run health check tests on mgx image"
	@echo "  make clean          - Clean up containers, volumes, and build files"
	@echo "  make clean-mgx-dev  - Stop and remove all containers starting with mgx-dev"
	@echo "  make test           - Run tests"
	@echo ""

install:
	@echo "📦 Installing Python dependencies..."
	pip install -e .
	@echo "📦 Installing frontend dependencies..."
	cd frontend && pnpm install
	@echo "✅ Installation complete"

start: up logs

up:
	@echo "🚀 Starting backend services..."
	docker compose -f infra/docker-compose.yml up -d --build
	@echo "⏳ Waiting for services to be ready..."
	@sleep 5
	@echo "✅ Backend services started"
	@echo ""
	@echo "Check service health:"
	@curl -s http://localhost:9080/health && echo "  ✅ Apisix: OK" || echo "  ❌ Apisix: Failed"
	@curl -s http://localhost:8000/health && echo "  ✅ MGX API: OK" || echo "  ❌ MGX API: Failed"
	@curl -s http://localhost:8001/health && echo "  ✅ OAuth2 Provider: OK" || echo "  ❌ OAuth2 Provider: Failed"

down:
	@echo "🛑 Stopping backend services..."
	docker compose -f infra/docker-compose.yml down
	@echo "✅ Backend services stopped"

logs:
	docker compose -f infra/docker-compose.yml logs -f

frontend:
	@echo "🎨 Starting frontend dev server..."
	cd frontend && pnpm dev

backend:
	@echo "🔄 Rebuilding and restarting backend services..."
	docker compose -f infra/docker-compose.yml up -d --build
	@echo "✅ Backend services restarted"

backend-local:
	@echo "🚀 Starting MGX API locally..."
	uv run src/mgx_api/main.py

build-agent:
	@echo "🏗️  Building MGX unified image..."
	docker build -f infra/Dockerfile.mgx -t mgx:latest .
	@echo "✅ MGX image built: mgx:latest (used by mgx-api, celery-worker, agent)"
	@make test-image

build-mgx: build-agent

test-image:
	@echo "🧪 Running MGX image health checks..."
	@./scripts/test_mgx_image.sh

dev:
	@echo "🚀 Starting MGX Demo in development mode..."
	@echo ""
	@echo "Starting backend services..."
	@make up
	@echo ""
	@echo "✨ Backend started!"
	@echo ""
	@echo "To start frontend, run in a new terminal:"
	@echo "  cd frontend && pnpm dev"
	@echo ""
	@echo "Or run: make frontend"

clean:
	@echo "🧹 Cleaning up..."
	docker compose -f infra/docker-compose.yml down -v
	rm -rf workspaces/*
	make clean-mgx-dev
	make clean-mgx-agents
	@echo "✅ Cleanup complete"

clean-mgx-dev:
	@echo "🧹 Stopping and removing mgx-dev-* containers..."
	@ids=$$(docker ps -a --filter "name=mgx-dev" -q); \
	if [ -n "$$ids" ]; then \
		docker rm -f $$ids; \
		echo "✅ Removed mgx-dev containers"; \
	else \
		echo "ℹ️  No mgx-dev containers found"; \
	fi

clean-mgx-agents:
	@echo "🧹 Stopping and removing mgx-agents-* containers..."
	@ids=$$(docker ps -a --filter "name=mgx-agent" -q); \
	if [ -n "$$ids" ]; then \
		docker rm -f $$ids; \
		echo "✅ Removed mgx-agents containers"; \
	else \
		echo "ℹ️  No mgx-agents containers found"; \
	fi
test:
	@echo "🧪 Running tests..."
	uv run python -m pytest tests/ -v

# Quick commands
restart: clean-mgx-dev clean-mgx-agents build-mgx up logs

status:
	@echo "📊 Service Status:"
	@docker compose -f infra/docker-compose.yml ps

shell-mgx-api:
	docker compose -f infra/docker-compose.yml exec mgx-api /bin/bash

shell-oauth2:
	docker compose -f infra/docker-compose.yml exec oauth2-provider /bin/bash

shell-worker:
	docker compose -f infra/docker-compose.yml exec celery-worker /bin/bash

mongo:
	docker exec -it mgx-mongodb mongosh

redis:
	docker exec -it mgx-redis redis-cli
