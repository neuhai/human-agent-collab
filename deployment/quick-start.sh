#!/bin/bash

# ==============================================================================
# Quick Start Script for the Human-Agent Collaboration Platform
#
# This script automates the setup of the necessary configuration files
# for running the application using pre-built Docker images from GHCR.
# ==============================================================================

# --- Helper Functions ---
# Checks if a command exists.
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# --- Main Execution ---

# Step 1: Check for dependencies
echo "Step 1: Checking for dependencies (Docker and Docker Compose)..."
if ! command_exists docker; then
    echo "Error: Docker is not installed."
    echo "Please install Docker Desktop for your system: https://www.docker.com/products/docker-desktop/"
    exit 1
fi
if ! command_exists docker-compose; then
    echo "Warning: 'docker-compose' command not found. Trying 'docker compose' (V2 syntax)..."
    if ! docker compose version >/dev/null 2>&1; then
        echo "Error: Docker Compose (both V1 'docker-compose' and V2 'docker compose') is not available."
        echo "Please ensure Docker Desktop is installed and running correctly."
        exit 1
    fi
fi
echo "✅ Dependencies found."

# Step 2: Set up the application directory
echo -e "\nStep 2: Setting up the application directory..."
APP_DIR="human-agent-collab-app"
if [ -d "$APP_DIR" ]; then
    echo "Directory '$APP_DIR' already exists."
    read -p "Do you want to overwrite existing configuration files within it? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted. Please move or rename the existing directory and run the script again."
        exit 1
    fi
else
    mkdir -p "$APP_DIR"
fi
cd "$APP_DIR"
echo "✅ Created and entered '$APP_DIR' directory."

# Step 3: Generate configuration files
echo -e "\nStep 3: Generating configuration files..."

# Generate docker-compose.yml
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  postgres:
    image: postgres:18-alpine
    container_name: human-agent-postgres-prod
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: shape_factory_research
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - app-network
    restart: always

  backend:
    image: ghcr.io/neuhai/human-agent-collab-backend:latest
    container_name: human-agent-backend-prod
    environment:
      DATABASE_URL: postgresql://postgres:${POSTGRES_PASSWORD}@postgres:5432/shape_factory_research
      JWT_SECRET: ${JWT_SECRET}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      FLASK_ENV: production
      PYTHONUNBUFFERED: 1
      AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID}
      AWS_SECRET_ACCESS_KEY: ${AWS_SECRET_ACCESS_KEY}
      MTURK_REGION_NAME: ${MTURK_REGION_NAME}
      MTURK_ENVIRONMENT: ${MTURK_ENVIRONMENT}
    depends_on:
      postgres:
        condition: service_healthy
    networks:
      - app-network
    restart: always

  frontend:
    image: ghcr.io/neuhai/human-agent-collab-frontend:latest
    container_name: human-agent-frontend-prod
    ports:
      - "80:80"
    depends_on:
      - backend
    networks:
      - app-network
    restart: always

networks:
  app-network:
    driver: bridge

volumes:
  postgres_data:
    driver: local
EOF
echo "-> docker-compose.yml created."

# Generate .env
cat > .env << 'EOF'
# --- Human-Agent Collaboration Platform Environment ---
# Please fill in the following values before starting the application.

# A secure password for the database
POSTGRES_PASSWORD=CHANGE_ME_TO_A_SECURE_PASSWORD

# Your OpenAI API key
OPENAI_API_KEY=CHANGE_ME_sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# A secure random string for JWT. You can generate one with: openssl rand -base64 32
JWT_SECRET=CHANGE_ME_TO_A_RANDOM_SECRET_STRING

# --- AWS Configuration (for mTurk Integration) ---
# Optional: Fill these in if you plan to use the mTurk integration.
AWS_ACCESS_KEY_ID=CHANGE_ME_YOUR_AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY=CHANGE_ME_YOUR_AWS_SECRET_ACCESS_KEY
MTURK_REGION_NAME=us-east-1
MTURK_ENVIRONMENT=sandbox # Use 'sandbox' for testing, 'production' for live HITs
EOF
echo "-> .env created."
echo "✅ Configuration files generated successfully."

# Step 4: Final Instructions
echo -e "\n======================== SETUP COMPLETE ========================"
echo "Your configuration files are ready in the '$APP_DIR' directory."
echo ""
echo "🔴 NEXT STEPS:"
echo "1. Open the '.env' file in a text editor."
echo "2. Replace the 'CHANGE_ME' placeholders with your actual secrets."
echo "3. Once you have saved your changes, run the following command to start the application:"
echo ""
echo "   docker-compose up -d"
echo ""
echo "The application will then be available at http://localhost"
echo "=================================================================="
