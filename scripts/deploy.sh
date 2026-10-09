#!/bin/bash
# ==========================================
# Notion-AI Docker Deployment Script
# ==========================================

set -e  # Exit immediately on error

echo "=========================================="
echo "  Notion-AI Docker Deployment Script"
echo "=========================================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✅ .env file created"
        echo "📝 Please edit .env and fill in your Notion account details"
        echo "   Then run this script again"
        exit 0
    else
        echo "❌ .env.example file not found"
        exit 1
    fi
fi

# Create required directories
echo "📁 Creating data directories..."
mkdir -p data logs

# Build image
echo "🔨 Building Docker image..."
docker-compose build --no-cache

# Start service
echo "🚀 Starting service..."
docker-compose up -d

# Wait for service to start
echo "⏳ Waiting for service to start..."
sleep 5

# Check service status
echo ""
echo "📊 Service status:"
docker-compose ps

# Health check
echo ""
echo "🏥 Health check:"
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ Service is running!"
    echo ""
    echo "🌐 Access URLs:"
    echo "   - Web UI: http://localhost:8000"
    echo "   - API docs: http://localhost:8000/docs"
    echo "   - Health check: http://localhost:8000/health"
    echo ""
    echo "📝 View logs:"
    echo "   docker-compose logs -f"
    echo ""
    echo "🛑 Stop service:"
    echo "   docker-compose down"
else
    echo "❌ Service failed to start. Check the logs:"
    echo "   docker-compose logs"
fi

echo ""
echo "=========================================="
echo "  Deployment complete!"
echo "=========================================="
