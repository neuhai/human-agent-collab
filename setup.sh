#!/bin/bash

# Human-Agent Collaboration Platform Setup Script
# This script automates the complete setup process for the research platform

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check Python version
check_python_version() {
    if command_exists python3; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        REQUIRED_VERSION="3.10"
        if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" = "$REQUIRED_VERSION" ]; then
            print_success "Python $PYTHON_VERSION found (>= $REQUIRED_VERSION required)"
            return 0
        else
            print_error "Python $PYTHON_VERSION found, but $REQUIRED_VERSION or higher is required"
            return 1
        fi
    else
        print_error "Python 3 not found. Please install Python 3.10 or higher"
        return 1
    fi
}

# Function to check Node.js version
check_node_version() {
    if command_exists node; then
        NODE_VERSION=$(node -v | cut -d'v' -f2)
        REQUIRED_VERSION="20.19.0"
        if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$NODE_VERSION" | sort -V | head -n1)" = "$REQUIRED_VERSION" ]; then
            print_success "Node.js $NODE_VERSION found (>= $REQUIRED_VERSION required)"
            return 0
        else
            print_error "Node.js $NODE_VERSION found, but $REQUIRED_VERSION or higher is required"
            return 1
        fi
    else
        print_error "Node.js not found. Please install Node.js 20.19.0 or higher"
        return 1
    fi
}

# Function to check PostgreSQL
check_postgresql() {
    if command_exists psql; then
        print_success "PostgreSQL found"
        return 0
    else
        print_error "PostgreSQL not found. Please install PostgreSQL 13 or higher"
        print_status "Installation instructions:"
        print_status "  macOS: brew install postgresql"
        print_status "  Ubuntu/Debian: sudo apt install postgresql postgresql-contrib"
        print_status "  Windows: Download from https://www.postgresql.org/download/"
        return 1
    fi
}

# Function to check if PostgreSQL service is running
check_postgresql_running() {
    if command_exists pg_isready; then
        if pg_isready -q; then
            print_success "PostgreSQL service is running"
            return 0
        else
            print_warning "PostgreSQL service is not running"
            print_status "Please start PostgreSQL service:"
            print_status "  macOS: brew services start postgresql"
            print_status "  Ubuntu/Debian: sudo systemctl start postgresql"
            return 1
        fi
    else
        print_warning "Cannot check PostgreSQL status (pg_isready not found)"
        return 0
    fi
}

# Function to load environment variables from backend .env file
load_env_file() {
    if [ -f "backend/.env" ]; then
        print_status "Loading configuration from backend/.env file..."
        source backend/.env
        return 0
    else
        print_error "backend/.env file not found!"
        print_status "Please create backend/.env file first:"
        print_status "1. Copy the template: cp env.template backend/.env"
        print_status "2. Edit backend/.env with your actual values:"
        print_status "   - Set your database username and password"
        print_status "   - Add your OpenAI API key"
        print_status "   - Configure other settings as needed"
        print_status "3. Run this script again"
        return 1
    fi
}

# Function to validate backend .env file has required fields
validate_env_file() {
    print_status "Validating backend/.env configuration..."
    
    local missing_fields=()
    
    # Check required fields
    [ -z "$DATABASE_USER" ] && missing_fields+=("DATABASE_USER")
    [ -z "$DATABASE_PASSWORD" ] && missing_fields+=("DATABASE_PASSWORD")
    [ -z "$DATABASE_NAME" ] && missing_fields+=("DATABASE_NAME")
    [ -z "$OPENAI_API_KEY" ] && missing_fields+=("OPENAI_API_KEY")
    
    if [ ${#missing_fields[@]} -ne 0 ]; then
        print_error "Missing required fields in backend/.env file:"
        for field in "${missing_fields[@]}"; do
            print_error "  - $field"
        done
        print_status "Please update your backend/.env file with the missing values and run this script again"
        return 1
    fi
    
    # Check if OpenAI API key is still placeholder
    if [ "$OPENAI_API_KEY" = "your_openai_api_key_here" ]; then
        print_error "Please update OPENAI_API_KEY in your backend/.env file with your actual OpenAI API key"
        return 1
    fi
    
    print_success "backend/.env file validation passed"
    return 0
}

# Function to validate frontend .env file
validate_frontend_env_file() {
    print_status "Validating frontend/.env configuration..."
    
    if [ ! -f "vue-app/.env" ]; then
        print_error "vue-app/.env file not found!"
        print_status "Please create vue-app/.env file with:"
        print_status "VITE_BACKEND_URL=http://localhost:5002"
        return 1
    fi
    
    # Check if VITE_BACKEND_URL is set
    if ! grep -q "VITE_BACKEND_URL=" vue-app/.env; then
        print_error "VITE_BACKEND_URL not found in vue-app/.env file"
        print_status "Please add VITE_BACKEND_URL=http://localhost:5002 to vue-app/.env"
        return 1
    fi
    
    print_success "vue-app/.env file validation passed"
    return 0
}

# Function to create database and user
setup_database() {
    print_status "Setting up database using configuration from .env file..."
    
    # Determine the correct superuser for PostgreSQL
    local PG_SUPERUSER=""
    if psql -U postgres -d postgres -c "SELECT 1;" >/dev/null 2>&1; then
        PG_SUPERUSER="postgres"
    elif psql -U $(whoami) -d postgres -c "SELECT 1;" >/dev/null 2>&1; then
        PG_SUPERUSER=$(whoami)
    else
        print_error "Cannot connect to PostgreSQL. Please ensure PostgreSQL is running and accessible."
        print_status "Try starting PostgreSQL with: brew services start postgresql"
        return 1
    fi
    
    print_status "Using PostgreSQL superuser: $PG_SUPERUSER"
    
    # Check if database already exists
    if psql -U $PG_SUPERUSER -d postgres -lqt | cut -d \| -f 1 | grep -qw "$DATABASE_NAME"; then
        print_warning "Database '$DATABASE_NAME' already exists"
        read -p "Do you want to recreate it? This will delete all existing data! (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_status "Dropping existing database..."
            psql -U $PG_SUPERUSER -d postgres -c "DROP DATABASE IF EXISTS $DATABASE_NAME;"
        else
            print_status "Using existing database"
            return 0
        fi
    fi
    
    # Create database
    print_status "Creating database '$DATABASE_NAME'..."
    psql -U $PG_SUPERUSER -d postgres -c "CREATE DATABASE $DATABASE_NAME;"
    
    # Create user if it doesn't exist
    if ! psql -U $PG_SUPERUSER -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DATABASE_USER'" | grep -q 1; then
        print_status "Creating database user '$DATABASE_USER'..."
        psql -U $PG_SUPERUSER -d postgres -c "CREATE USER $DATABASE_USER WITH PASSWORD '$DATABASE_PASSWORD';"
    else
        print_warning "Database user '$DATABASE_USER' already exists"
        print_status "Updating password for existing user..."
        psql -U $PG_SUPERUSER -d postgres -c "ALTER USER $DATABASE_USER WITH PASSWORD '$DATABASE_PASSWORD';"
    fi
    
    # Grant privileges
    psql -U $PG_SUPERUSER -d postgres -c "GRANT ALL PRIVILEGES ON DATABASE $DATABASE_NAME TO $DATABASE_USER;"
    
    print_success "Database setup completed using your .env configuration"
}

# Function to initialize database schema
init_database_schema() {
    print_status "Initializing database schema..."
    
    if [ -f "backend/database/schema.sql" ]; then
        # Use the database user to initialize schema
        psql -U $DATABASE_USER -d $DATABASE_NAME -f backend/database/schema.sql
        print_success "Database schema initialized"
    else
        print_error "Schema file not found: backend/database/schema.sql"
        return 1
    fi
}

# Function to create virtual environment
setup_python_venv() {
    print_status "Setting up Python virtual environment..."
    
    # Check if uv is available (preferred)
    if command_exists uv; then
        print_status "Using uv for Python package management..."
        uv sync
        print_success "Python dependencies installed with uv"
    else
        print_status "Using pip for Python package management..."
        
        # Create virtual environment
        if [ ! -d "venv" ]; then
            python3 -m venv venv
            print_success "Virtual environment created"
        else
            print_warning "Virtual environment already exists"
        fi
        
        # Activate virtual environment
        source venv/bin/activate
        
        # Upgrade pip
        pip install --upgrade pip
        
        # Install dependencies
        pip install -r backend/requirements.txt
        print_success "Python dependencies installed"
    fi
}

# Function to setup frontend dependencies
setup_frontend() {
    print_status "Setting up frontend dependencies..."
    
    cd vue-app
    
    # Check if package-lock.json exists (prefer npm)
    if [ -f "package-lock.json" ]; then
        print_status "Using npm to install dependencies..."
        npm install
    elif [ -f "yarn.lock" ]; then
        print_status "Using yarn to install dependencies..."
        yarn install
    else
        print_status "Using npm to install dependencies..."
        npm install
    fi
    
    cd ..
    print_success "Frontend dependencies installed"
}

# Function to generate JWT secret if not provided
generate_jwt_secret() {
    if [ -z "$JWT_SECRET" ] || [ "$JWT_SECRET" = "your-super-secret-jwt-key-change-in-production" ]; then
        print_status "Generating secure JWT secret..."
        JWT_SECRET=$(openssl rand -hex 32)
        # Update backend/.env file with generated secret
        if command_exists sed; then
            sed -i.bak "s/JWT_SECRET=.*/JWT_SECRET=$JWT_SECRET/" backend/.env
            rm backend/.env.bak 2>/dev/null || true
        else
            print_warning "Could not automatically update JWT_SECRET in backend/.env file"
            print_status "Please manually set JWT_SECRET=$JWT_SECRET in your backend/.env file"
        fi
        print_success "JWT secret generated and updated"
    else
        print_success "Using existing JWT secret from backend/.env file"
    fi
}

# Function to create frontend .env file
create_frontend_env_file() {
    print_status "Creating frontend .env file..."
    
    if [ -f "vue-app/.env" ]; then
        print_warning "vue-app/.env file already exists"
        read -p "Do you want to overwrite it? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_status "Keeping existing vue-app/.env file"
            return 0
        fi
    fi
    
    # Create frontend .env file
    cat > vue-app/.env << EOF
VITE_BACKEND_URL=http://localhost:5002
EOF
    
    print_success "Frontend .env file created with default backend URL"
    print_status "You can modify VITE_BACKEND_URL in vue-app/.env if needed"
}

# Function to build frontend
build_frontend() {
    print_status "Building frontend for production..."
    
    cd vue-app
    if [ -f "package-lock.json" ]; then
        npm run build
    else
        yarn build
    fi
    cd ..
    
    print_success "Frontend built successfully"
}

# Main setup function
main() {
    echo -e "${BLUE}"
    echo "=========================================="
    echo "Human-Agent Collaboration Platform Setup"
    echo "=========================================="
    echo -e "${NC}"
    
    # Check prerequisites
    print_status "Checking prerequisites..."
    
    if ! check_python_version; then
        exit 1
    fi
    
    if ! check_node_version; then
        exit 1
    fi
    
    if ! check_postgresql; then
        exit 1
    fi
    
    if ! check_postgresql_running; then
        print_warning "Please start PostgreSQL service and run this script again"
        exit 1
    fi
    
    print_success "All prerequisites satisfied"
    
    # Load and validate backend .env file
    print_status "Loading configuration from backend/.env file..."
    if ! load_env_file; then
        exit 1
    fi
    
    if ! validate_env_file; then
        exit 1
    fi
    
    # Validate frontend .env file
    if ! validate_frontend_env_file; then
        print_status "Creating frontend .env file automatically..."
        create_frontend_env_file
    fi
    
    # Generate JWT secret if needed
    generate_jwt_secret
    
    # Setup database using .env configuration
    print_status "Setting up database using your configuration..."
    
    # Ensure PostgreSQL is running
    if ! pg_isready -q; then
        print_warning "PostgreSQL is not running. Attempting to start it..."
        if command_exists brew; then
            brew services start postgresql
            sleep 3
            if ! pg_isready -q; then
                print_error "Failed to start PostgreSQL. Please start it manually: brew services start postgresql"
                exit 1
            fi
        else
            print_error "PostgreSQL is not running. Please start it manually."
            exit 1
        fi
    fi
    
    setup_database
    init_database_schema
    
    # Setup Python environment
    print_status "Setting up Python environment..."
    setup_python_venv
    
    # Setup frontend
    print_status "Setting up frontend..."
    setup_frontend
    
    # Build frontend
    build_frontend
    
    # Final instructions
    echo -e "${GREEN}"
    echo "=========================================="
    echo "Setup completed successfully!"
    echo "=========================================="
    echo -e "${NC}"
    
    print_status "Next steps:"
    echo "1. Start the backend server:"
    echo "   cd backend && python app.py"
    echo "2. Start the frontend development server (in a new terminal):"
    echo "   cd vue-app && npm run dev"
    echo ""
    print_status "Access points:"
    echo "- Participant Interface: http://localhost:3000"
    echo "- Researcher Dashboard: http://localhost:3000/researcher"
    echo "- API Endpoints: http://localhost:5002/api/*"
    echo ""
    print_success "Your .env files are properly configured and ready to use!"
    print_status "Backend configuration: backend/.env"
    print_status "Frontend configuration: vue-app/.env"
}

# Run main function
main "$@"
