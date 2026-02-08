#!/bin/bash
# Quick start script for MGX demo

set -e

echo "🚀 Starting MGX Demo..."
echo ""

# Check if docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Start backend services
echo "📦 Starting backend services..."
cd infra
docker compose up -d

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check service health
echo "🔍 Checking service health..."
curl -s http://localhost:9080/health > /dev/null && echo "✅ Apisix: OK" || echo "❌ Apisix: Failed"
curl -s http://localhost:8000/health > /dev/null && echo "✅ MGX API: OK" || echo "❌ MGX API: Failed"
curl -s http://localhost:8001/health > /dev/null && echo "✅ OAuth2 Provider: OK" || echo "❌ OAuth2 Provider: Failed"

cd ..

echo ""
echo "✨ Backend services started!"
echo ""
echo "📝 Next steps:"
echo "  1. cd frontend"
echo "  2. pnpm install"
echo "  3. pnpm dev"
echo "  4. Open http://localhost:5173"
echo "  5. Login with admin/admin123"
echo ""
echo "📚 For more info, see docs/getting-started.md"
