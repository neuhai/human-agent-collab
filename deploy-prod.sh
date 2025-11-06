#!/bin/bash

# Production Deployment Script for Human-Agent Collaboration Platform

set -e  # Exit on error

echo "=================================================="
echo "Production Deployment Script"
echo "=================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}[ERROR] Docker is not running. Please start Docker and try again.${NC}"
    exit 1
fi

echo -e "${GREEN}[OK] Docker is running${NC}"

# Check if .env.prod exists
if [ ! -f .env.prod ]; then
    echo -e "${YELLOW}[WARNING] .env.prod not found. Creating from template...${NC}"
    
    if [ -f .env.prod.template ]; then
        cp .env.prod.template .env.prod
        echo -e "${YELLOW}[ACTION REQUIRED] Please edit .env.prod and set your credentials:${NC}"
        echo "  - POSTGRES_PASSWORD"
        echo "  - OPENAI_API_KEY"
        echo "  - JWT_SECRET"
        echo ""
        echo -e "${RED}Deployment cannot continue without proper credentials.${NC}"
        exit 1
    else
        echo -e "${RED}[ERROR] .env.prod.template not found. Cannot create .env.prod${NC}"
        exit 1
    fi
fi

# Validate required environment variables
echo "Validating environment variables..."
source .env.prod

if [ -z "$POSTGRES_PASSWORD" ] || [ "$POSTGRES_PASSWORD" = "CHANGE_THIS_TO_SECURE_PASSWORD" ]; then
    echo -e "${RED}[ERROR] POSTGRES_PASSWORD not set or using default value${NC}"
    exit 1
fi

if [ -z "$OPENAI_API_KEY" ] || [ "$OPENAI_API_KEY" = "sk-your-openai-api-key-here" ]; then
    echo -e "${RED}[ERROR] OPENAI_API_KEY not set or using default value${NC}"
    exit 1
fi

if [ -z "$JWT_SECRET" ] || [ "$JWT_SECRET" = "CHANGE_THIS_TO_RANDOM_SECRET_STRING" ]; then
    echo -e "${RED}[ERROR] JWT_SECRET not set or using default value${NC}"
    exit 1
fi

echo -e "${GREEN}[OK] All required environment variables are set${NC}"

# Parse command line arguments
COMMAND=${1:-deploy}

case $COMMAND in
  deploy)
    echo "Building production images..."
    docker-compose -f docker-compose.prod.yml build --no-cache
    
    echo "Starting services..."
    docker-compose -f docker-compose.prod.yml up -d
    
    echo -e "${GREEN}=================================================="
    echo "Deployment Complete!"
    echo "=================================================="
    echo "Access the application at:"
    echo "  - Frontend: http://localhost:3000"
    echo "  - Backend API: http://localhost:5002"
    echo ""
    echo "View logs with:"
    echo "  docker-compose -f docker-compose.prod.yml logs -f"
    echo ""
    echo "Stop services with:"
    echo "  docker-compose -f docker-compose.prod.yml down"
    echo -e "==================================================${NC}"
    ;;
    
  rebuild)
    echo "Rebuilding all images..."
    docker-compose -f docker-compose.prod.yml build --no-cache
    echo -e "${GREEN}[OK] Rebuild complete${NC}"
    ;;
    
  restart)
    echo "Restarting services..."
    docker-compose -f docker-compose.prod.yml restart
    echo -e "${GREEN}[OK] Services restarted${NC}"
    ;;
    
  stop)
    echo "Stopping services..."
    docker-compose -f docker-compose.prod.yml down
    echo -e "${GREEN}[OK] Services stopped${NC}"
    ;;
    
  logs)
    docker-compose -f docker-compose.prod.yml logs -f
    ;;
    
  status)
    docker-compose -f docker-compose.prod.yml ps
    ;;
    
  clean)
    echo -e "${RED}[WARNING] This will remove all containers, volumes, and data!${NC}"
    read -p "Are you sure? (yes/no): " confirm
    if [ "$confirm" = "yes" ]; then
      docker-compose -f docker-compose.prod.yml down -v
      echo -e "${GREEN}[OK] Cleanup complete${NC}"
    else
      echo "Cleanup cancelled"
    fi
    ;;
    
  *)
    echo "Usage: $0 {deploy|rebuild|restart|stop|logs|status|clean}"
    echo ""
    echo "Commands:"
    echo "  deploy  - Build and start production services"
    echo "  rebuild - Rebuild all images without cache"
    echo "  restart - Restart all services"
    echo "  stop    - Stop all services"
    echo "  logs    - View logs (real-time)"
    echo "  status  - Show service status"
    echo "  clean   - Remove all containers and volumes (WARNING: deletes data)"
    exit 1
    ;;
esac
