#!/bin/bash
# ==========================================
# Notion-AI Service Management Script
# ==========================================

case "$1" in
    start)
        echo "🚀 Starting service..."
        docker-compose up -d
        ;;
    stop)
        echo "🛑 Stopping service..."
        docker-compose down
        ;;
    restart)
        echo "🔄 Restarting service..."
        docker-compose restart
        ;;
    status)
        echo "📊 Service status:"
        docker-compose ps
        echo ""
        echo "🏥 Health check:"
        curl -s http://localhost:8000/health | jq . 2>/dev/null || curl -s http://localhost:8000/health
        ;;
    logs)
        echo "📝 Viewing logs (Ctrl+C to exit):"
        docker-compose logs -f
        ;;
    build)
        echo "🔨 Rebuilding image..."
        docker-compose build --no-cache
        ;;
    update)
        echo "🔄 Updating and restarting service..."
        docker-compose down
        docker-compose build --no-cache
        docker-compose up -d
        ;;
    clean)
        echo "🧹 Cleaning containers and images..."
        docker-compose down -v
        docker system prune -f
        ;;
    backup)
        echo "💾 Backing up database..."
        BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$BACKUP_DIR"
        cp data/conversations.db "$BACKUP_DIR/"
        echo "✅ Backup complete: $BACKUP_DIR"
        ;;
    restore)
        if [ -z "$2" ]; then
            echo "❌ Please specify a backup directory, e.g.: ./manage.sh restore backups/20240306_120000"
            exit 1
        fi
        echo "📥 Restoring database..."
        cp "$2/conversations.db" data/
        echo "✅ Restore complete. Please restart the service: ./manage.sh restart"
        ;;
    shell)
        echo "🐚 Entering container shell..."
        docker-compose exec notion-opus /bin/bash
        ;;
    test)
        echo "🧪 Testing API..."
        echo "Sending test request..."
        curl -X POST http://localhost:8000/v1/chat/completions \
            -H "Content-Type: application/json" \
            -d '{
                "model": "claude-sonnet-4-6",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": false
            }'
        ;;
    *)
        echo "=========================================="
        echo "  Notion-AI Service Management Script"
        echo "=========================================="
        echo "Usage: ./manage.sh {command}"
        echo ""
        echo "Commands:"
        echo "  start     - Start service"
        echo "  stop      - Stop service"
        echo "  restart   - Restart service"
        echo "  status    - View status"
        echo "  logs      - View logs"
        echo "  build     - Rebuild image"
        echo "  update    - Update and restart service"
        echo "  clean     - Clean containers and images"
        echo "  backup    - Backup database"
        echo "  restore   - Restore database (specify backup directory)"
        echo "  shell     - Enter container shell"
        echo "  test      - Test API"
        echo ""
        echo "Examples:"
        echo "  ./manage.sh start"
        echo "  ./manage.sh logs"
        echo "  ./manage.sh backup"
        echo "  ./manage.sh restore backups/20240306_120000"
        echo "=========================================="
        exit 1
        ;;
esac
