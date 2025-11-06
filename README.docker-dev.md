# Docker Setup Guide

This guide explains how to run the Human-Agent Collaboration Platform using Docker.

## Prerequisites

- **Docker Desktop** (Windows/Mac) or **Docker Engine** (Linux)
- **Docker Compose** v2.0+
- Git

## Quick Start

### 1. Clone and Configure

```bash
# Navigate to project directory
cd human-agent-collab

# Copy the Docker environment template
cp .env.dev.template .env
```
Edit .env and add your credentials
- Set POSTGRES_PASSWORD (e.g., "mySecurePassword123")
- Set OPENAI_API_KEY (required for AI features)

### 2. Build and Start Services

```bash
# Build and start all services
docker-compose up --build

# Or run in detached mode (background)
docker-compose up -d --build
```

### 3. Access the Application

Once all services are running:

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:5002
- **PostgreSQL**: localhost:5432

## Services Overview

| Service | Container Name | Port | Description |
|---------|---------------|------|-------------|
| postgres | human-agent-postgres | 5432 | PostgreSQL 18 Database |
| backend | human-agent-backend | 5002 | Flask API Server |
| frontend | human-agent-frontend | 3000 | Vue.js Development Server |

## Common Commands

### Start Services
```bash
# Start all services
docker-compose up

# Start in background
docker-compose up -d

# Start specific service
docker-compose up backend
```

### Stop Services
```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: deletes database data)
docker-compose down -v
```

### View Logs
```bash
# View all logs
docker-compose logs

# Follow logs in real-time
docker-compose logs -f

# View logs for specific service
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f postgres
```

### Rebuild Services
```bash
# Rebuild all services
docker-compose build

# Rebuild specific service
docker-compose build backend

# Rebuild and restart
docker-compose up --build
```

### Execute Commands in Containers
```bash
# Access backend shell
docker-compose exec backend bash

# Access PostgreSQL CLI
docker-compose exec postgres psql -U postgres -d shape_factory_research

# Run Python script in backend
docker-compose exec backend python migrate.py
```

## Database Management

### Initial Setup

The database schema is automatically initialized on first startup from `backend/database/schema.sql`.

### Manual Database Operations

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U postgres

# Inside PostgreSQL shell:
\c shape_factory_research  # Connect to database
\dt                         # List tables
\q                          # Quit
```

### Reset Database

```bash
# Stop services and remove volumes
docker-compose down -v

# Start again (will reinitialize database)
docker-compose up
```

### Backup Database

```bash
# Create backup
docker-compose exec postgres pg_dump -U postgres shape_factory_research > backup.sql

# Restore from backup
docker-compose exec -T postgres psql -U postgres shape_factory_research < backup.sql
```

## Development Workflow

### Hot Reload

Both frontend and backend support hot reload:

- **Backend**: Changes to Python files automatically restart the Flask server
- **Frontend**: Changes to Vue files automatically reload in browser

### Install New Dependencies

**Backend:**
```bash
# Add package to requirements.txt, then:
docker-compose exec backend pip install -r requirements.txt

# Or install directly:
docker-compose exec backend pip install package-name
```

**Frontend:**
```bash
# Add package to package.json, then:
docker-compose exec frontend npm install

# Or install directly:
docker-compose exec frontend npm install package-name
```

## Troubleshooting

### Services Won't Start

1. **Check if ports are in use:**
   ```bash
   # Windows
   netstat -ano | findstr :5432
   netstat -ano | findstr :5002
   netstat -ano | findstr :3000
   
   # Mac/Linux
   lsof -i :5432
   lsof -i :5002
   lsof -i :3000
   ```

2. **Check Docker logs:**
   ```bash
   docker-compose logs
   ```

3. **Restart Docker Desktop:**
   - Close Docker Desktop completely
   - Start it again
   - Run `docker-compose up --build`

### Database Connection Errors

```bash
# Check if PostgreSQL is healthy
docker-compose ps

# View PostgreSQL logs
docker-compose logs postgres

# Manually test connection
docker-compose exec postgres psql -U postgres -c "SELECT 1"
```

### Backend Can't Connect to Database

1. Ensure `.env` file has correct `POSTGRES_PASSWORD`
2. Check if postgres service is healthy:
   ```bash
   docker-compose ps postgres
   ```
3. Restart backend:
   ```bash
   docker-compose restart backend
   ```

### Frontend Can't Connect to Backend

1. Check `vue-app/.env` has `VITE_BACKEND_URL=http://localhost:5002`
2. Verify backend is running:
   ```bash
   curl http://localhost:5002/api/health
   ```
3. Restart frontend:
   ```bash
   docker-compose restart frontend
   ```

### Permission Errors (Linux)

```bash
# Fix permissions for volumes
sudo chown -R $USER:$USER .
```

## Production Deployment

For production deployment, you should:

1. **Use production Dockerfiles** with multi-stage builds
2. **Set proper environment variables:**
   ```env
   FLASK_ENV=production
   FLASK_DEBUG=False
   ```
3. **Use secrets management** (Docker Secrets, AWS Secrets Manager)
4. **Set up reverse proxy** (Nginx, Traefik)
5. **Enable SSL/TLS**
6. **Configure volume backups**
7. **Set resource limits** in docker-compose.yml

Example production additions:
```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
```

## Clean Up

### Remove All Containers and Images

```bash
# Stop and remove containers, networks
docker-compose down

# Remove volumes (WARNING: deletes all data)
docker-compose down -v

# Remove images
docker-compose down --rmi all

# Complete cleanup
docker-compose down -v --rmi all --remove-orphans
```

### Free Up Disk Space

```bash
# Remove unused containers, networks, images
docker system prune

# Remove everything including volumes
docker system prune -a --volumes
```

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| POSTGRES_PASSWORD | Yes | changeme | PostgreSQL password |
| OPENAI_API_KEY | Yes | - | OpenAI API key for AI features |
| JWT_SECRET | No | Auto-generated | JWT signing secret |
| FLASK_ENV | No | development | Flask environment |
| FLASK_DEBUG | No | True | Flask debug mode |
| DATABASE_NAME | No | shape_factory_research | Database name |
| WS_PORT | No | 8001 | WebSocket port |
| AGENT_LLM_MODE | No | function | Agent LLM mode |

## Support

For issues or questions:
1. Check logs: `docker-compose logs -f`
2. Verify all services are healthy: `docker-compose ps`
3. Consult main README.md
4. Check Docker Desktop status
