# ==============================================================================
# Quick Start Script for the Human-Agent Collaboration Platform (PowerShell)
#
# This script automates the setup of the necessary configuration files
# for running the application using pre-built Docker images from GHCR.
# ==============================================================================

# --- Helper Functions ---
function Command-Exists {
    param ($command)
    return (Get-Command $command -ErrorAction SilentlyContinue)
}

# --- Main Execution ---

# Step 1: Check for dependencies
Write-Host "Step 1: Checking for dependencies (Docker and Docker Compose)..."
if (-not (Command-Exists docker)) {
    Write-Error "Error: Docker is not installed."
    Write-Host "Please install Docker Desktop for your system: https://www.docker.com/products/docker-desktop/"
    exit 1
}
try {
    docker compose version > $null
} catch {
    Write-Error "Error: Docker Compose (V2 'docker compose') is not available."
    Write-Host "Please ensure Docker Desktop is installed and running correctly."
    exit 1
}
Write-Host "✅ Dependencies found."

# Step 2: Set up the application directory
Write-Host "`nStep 2: Setting up the application directory..."
$AppDir = "human-agent-collab-app"
if (Test-Path -Path $AppDir) {
    Write-Host "Directory '$AppDir' already exists."
    $choice = Read-Host "Do you want to overwrite existing configuration files within it? (y/N)"
    if ($choice -ne 'y') {
        Write-Host "Aborted. Please move or rename the existing directory and run the script again."
        exit 1
    }
} else {
    New-Item -ItemType Directory -Path $AppDir | Out-Null
}
Set-Location -Path $AppDir
Write-Host "✅ Created and entered '$AppDir' directory."

# Step 3: Generate configuration files
Write-Host "`nStep 3: Generating configuration files..."

# Generate docker-compose.yml
$dockerComposeContent = @"
version: '3.8'

services:
  postgres:
    image: postgres:18-alpine
    container_name: human-agent-postgres-prod
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: `${POSTGRES_PASSWORD}`
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
      DATABASE_URL: postgresql://postgres:`${POSTGRES_PASSWORD}`@postgres:5432/shape_factory_research
      JWT_SECRET: `${JWT_SECRET}`
      OPENAI_API_KEY: `${OPENAI_API_KEY}`
      FLASK_ENV: production
      PYTHONUNBUFFERED: 1
      AWS_ACCESS_KEY_ID: `${AWS_ACCESS_KEY_ID}`
      AWS_SECRET_ACCESS_KEY: `${AWS_SECRET_ACCESS_KEY}`
      MTURK_REGION_NAME: `${MTURK_REGION_NAME}`
      MTURK_ENVIRONMENT: `${MTURK_ENVIRONMENT}`
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
"@
$dockerComposeContent | Out-File -FilePath "docker-compose.yml" -Encoding utf8
Write-Host "-> docker-compose.yml created."

# Generate .env
$envContent = @"
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
"@
$envContent | Out-File -FilePath ".env" -Encoding utf8
Write-Host "-> .env created."
Write-Host "✅ Configuration files generated successfully."

# Step 4: Final Instructions
Write-Host "`n======================== SETUP COMPLETE ========================"
Write-Host "Your configuration files are ready in the '$AppDir' directory."
Write-Host ""
Write-Host "🔴 NEXT STEPS:"
Write-Host "1. Open the '.env' file in a text editor."
Write-Host "2. Replace the 'CHANGE_ME' placeholders with your actual secrets."
Write-Host "3. Once you have saved your changes, run the following command to start the application:"
Write-Host ""
Write-Host "   docker compose up -d"
Write-Host ""
Write-Host "The application will then be available at http://localhost"
Write-Host "=================================================================="
