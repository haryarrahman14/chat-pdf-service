#!/bin/bash

# Chat PDF Deployment Script
# This script helps deploy the application to VPS

set -e

echo "🚀 Chat PDF Deployment Script"
echo "=============================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Check if .env file exists
if [ ! -f .env ]; then
    print_error ".env file not found!"
    echo "Please create .env file from .env.example"
    exit 1
fi

print_success "Environment file found"

# Parse command line arguments
COMMAND=${1:-help}

case $COMMAND in
    dev|local)
        echo "🏠 Starting local development environment..."
        docker-compose -f docker-compose.dev.yml down
        docker-compose -f docker-compose.dev.yml build
        docker-compose -f docker-compose.dev.yml up -d
        print_success "Development server started on http://localhost:8000"
        echo ""
        echo "Features:"
        echo "  - Hot reload enabled"
        echo "  - Debug logging"
        echo "  - Code mounted from ./app"
        echo ""
        echo "Commands:"
        echo "  Logs:  docker-compose -f docker-compose.dev.yml logs -f"
        echo "  Shell: docker-compose -f docker-compose.dev.yml exec app bash"
        echo "  Stop:  docker-compose -f docker-compose.dev.yml down"
        ;;

    build)
        MODE=${2:-dev}
        if [ "$MODE" = "prod" ]; then
            echo "🔨 Building production Docker image..."
            docker-compose -f docker-compose.prod.yml build --no-cache
        else
            echo "🔨 Building development Docker image..."
            docker-compose -f docker-compose.dev.yml build --no-cache
        fi
        print_success "Build complete"
        ;;

    start)
        MODE=${2:-dev}
        if [ "$MODE" = "prod" ]; then
            echo "▶️  Starting production application..."
            docker-compose -f docker-compose.prod.yml up -d
        else
            echo "▶️  Starting development application..."
            docker-compose -f docker-compose.dev.yml up -d
        fi
        print_success "Application started"
        docker-compose -f docker-compose.$MODE.yml ps
        ;;

    stop)
        echo "⏹️  Stopping all applications..."
        docker-compose -f docker-compose.dev.yml down 2>/dev/null || true
        docker-compose -f docker-compose.prod.yml down 2>/dev/null || true
        docker-compose down 2>/dev/null || true
        print_success "Application stopped"
        ;;

    restart)
        MODE=${2:-dev}
        echo "🔄 Restarting $MODE application..."
        docker-compose -f docker-compose.$MODE.yml restart
        print_success "Application restarted"
        ;;

    logs)
        MODE=${2:-dev}
        echo "📋 Showing $MODE logs (Ctrl+C to exit)..."
        docker-compose -f docker-compose.$MODE.yml logs -f
        ;;

    shell)
        MODE=${2:-dev}
        echo "🐚 Opening shell in $MODE container..."
        docker-compose -f docker-compose.$MODE.yml exec app bash
        ;;

    status)
        echo "📊 Application status:"
        echo ""
        echo "Development:"
        docker-compose -f docker-compose.dev.yml ps 2>/dev/null || echo "  Not running"
        echo ""
        echo "Production:"
        docker-compose -f docker-compose.prod.yml ps 2>/dev/null || echo "  Not running"
        echo ""
        echo "🏥 Health check:"
        curl -s http://localhost:8000/api/health | jq . || echo "API not responding"
        ;;

    test)
        echo "🧪 Testing deployment..."

        # Check if running
        if ! docker ps | grep -q "chat-pdf"; then
            print_error "Application is not running"
            exit 1
        fi

        # Health check
        echo "Checking health endpoint..."
        HEALTH=$(curl -s http://localhost:8000/api/health)
        if echo "$HEALTH" | grep -q "ok"; then
            print_success "Health check passed"
        else
            print_error "Health check failed"
            exit 1
        fi

        print_success "All tests passed"
        ;;

    clean)
        echo "🧹 Cleaning up Docker resources..."
        docker-compose -f docker-compose.dev.yml down -v 2>/dev/null || true
        docker-compose -f docker-compose.prod.yml down -v 2>/dev/null || true
        docker-compose down -v 2>/dev/null || true
        docker system prune -af
        print_success "Cleanup complete"
        ;;

    backup)
        echo "💾 Creating backup..."
        BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
        mkdir -p "$BACKUP_DIR"

        # Backup environment
        cp .env "$BACKUP_DIR/.env.backup"

        # Backup uploads
        if [ -d "uploads" ]; then
            tar -czf "$BACKUP_DIR/uploads.tar.gz" uploads/
        fi

        print_success "Backup created at $BACKUP_DIR"
        ;;

    ssh-setup)
        echo "🔑 Setting up SSH key for GitHub Actions..."

        # Check if key exists
        if [ -f ~/.ssh/github_actions_key ]; then
            print_warning "SSH key already exists at ~/.ssh/github_actions_key"
            read -p "Overwrite? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 0
            fi
        fi

        # Generate key
        ssh-keygen -t ed25519 -C "github-actions" -f ~/.ssh/github_actions_key -N ""

        print_success "SSH key generated"
        echo ""
        echo "Public key (add to VPS ~/.ssh/authorized_keys):"
        echo "================================================"
        cat ~/.ssh/github_actions_key.pub
        echo ""
        echo "Private key (add to GitHub secret VPS_SSH_KEY):"
        echo "================================================"
        cat ~/.ssh/github_actions_key
        echo ""
        ;;

    vps-deploy)
        echo "🌐 Deploying to VPS..."

        # Check required environment variables
        if [ -z "$VPS_HOST" ] || [ -z "$VPS_USER" ]; then
            print_error "VPS_HOST and VPS_USER environment variables required"
            echo "Usage: VPS_HOST=1.2.3.4 VPS_USER=root ./deploy.sh vps-deploy"
            exit 1
        fi

        echo "Connecting to $VPS_USER@$VPS_HOST..."

        ssh "$VPS_USER@$VPS_HOST" << 'ENDSSH'
            cd /opt/chat-pdf || exit 1
            git pull origin main
            docker-compose -f docker-compose.prod.yml down
            docker-compose -f docker-compose.prod.yml build
            docker-compose -f docker-compose.prod.yml up -d
            docker-compose -f docker-compose.prod.yml ps
            echo "Waiting for health check..."
            sleep 10
            curl -s http://localhost:8000/api/health
ENDSSH

        print_success "Deployment complete"
        ;;

    init-vps)
        echo "🏗️  Initializing VPS..."

        if [ -z "$VPS_HOST" ] || [ -z "$VPS_USER" ]; then
            print_error "VPS_HOST and VPS_USER environment variables required"
            exit 1
        fi

        echo "Setting up $VPS_USER@$VPS_HOST..."

        ssh "$VPS_USER@$VPS_HOST" << 'ENDSSH'
            # Update system
            apt update && apt upgrade -y

            # Install Docker
            curl -fsSL https://get.docker.com -o get-docker.sh
            sh get-docker.sh
            rm get-docker.sh

            # Install Docker Compose
            apt install -y docker-compose

            # Create app directory
            mkdir -p /opt/chat-pdf

            echo "✓ VPS initialized successfully"
ENDSSH

        print_success "VPS initialization complete"
        echo ""
        echo "Next steps:"
        echo "1. Copy your repository to VPS"
        echo "2. Create .env file on VPS"
        echo "3. Run: ./deploy.sh vps-deploy"
        ;;

    help|*)
        echo "Chat PDF Deployment Script"
        echo ""
        echo "Usage: ./deploy.sh [command] [mode]"
        echo ""
        echo "Commands:"
        echo "  dev|local      - Start local development environment (hot reload)"
        echo "  build [mode]   - Build Docker image (dev/prod)"
        echo "  start [mode]   - Start application (dev/prod)"
        echo "  stop           - Stop all applications"
        echo "  restart [mode] - Restart application (dev/prod)"
        echo "  logs [mode]    - Show application logs (dev/prod)"
        echo "  shell [mode]   - Open bash shell in container (dev/prod)"
        echo "  status         - Show application status"
        echo "  test           - Test deployment"
        echo "  clean          - Clean up Docker resources"
        echo "  backup         - Create backup of environment and uploads"
        echo "  ssh-setup      - Generate SSH key for GitHub Actions"
        echo "  init-vps       - Initialize VPS (requires VPS_HOST and VPS_USER)"
        echo "  vps-deploy     - Deploy to VPS (requires VPS_HOST and VPS_USER)"
        echo "  help           - Show this help message"
        echo ""
        echo "Examples:"
        echo "  ./deploy.sh dev                   # Start development"
        echo "  ./deploy.sh build prod            # Build production"
        echo "  ./deploy.sh start prod            # Start production"
        echo "  ./deploy.sh logs dev              # View dev logs"
        echo "  ./deploy.sh shell dev             # Open dev shell"
        echo "  ./deploy.sh status                # Check status"
        echo "  VPS_HOST=1.2.3.4 VPS_USER=root ./deploy.sh init-vps"
        echo "  VPS_HOST=1.2.3.4 VPS_USER=root ./deploy.sh vps-deploy"
        ;;
esac
