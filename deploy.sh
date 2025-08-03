#!/bin/bash

set -e

echo "🚀 IndraAI Platform Deployment Script"
echo "====================================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# Check system requirements
check_requirements() {
    print_status "Checking system requirements..."
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker not found. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose not found. Please install Docker Compose first."
        exit 1
    fi
    
    # Check available memory
    available_memory=$(free -m | awk 'NR==2{printf "%.0f", $7}')
    if [ "$available_memory" -lt 4000 ]; then
        print_warning "Available memory is less than 4GB. Performance may be affected."
    fi
    
    # Check disk space
    available_disk=$(df -BG . | awk 'NR==2{print $4}' | sed 's/G//')
    if [ "$available_disk" -lt 20 ]; then
        print_warning "Available disk space is less than 20GB. Consider freeing up space."
    fi
    
    print_success "System requirements check completed"
}

# Setup environment
setup_environment() {
    print_status "Setting up environment..."
    
    if [ ! -f .env ]; then
        print_error ".env file not found. Please create one based on the template."
        print_status "Required environment variables:"
        echo "  - SUPABASE_URL"
        echo "  - SUPABASE_ANON_KEY"
        echo "  - SUPABASE_SERVICE_ROLE_KEY"
        echo "  - REDIS_PASSWORD"
        echo "  - GRAFANA_ADMIN_PASSWORD"
        exit 1
    fi
    
    # Load environment variables
    source .env
    
    # Validate required variables
    required_vars=("SUPABASE_URL" "SUPABASE_ANON_KEY" "SUPABASE_SERVICE_ROLE_KEY" "REDIS_PASSWORD")
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            print_error "Required environment variable $var is not set"
            exit 1
        fi
    done
    
    print_success "Environment setup completed"
}

# Create directories
create_directories() {
    print_status "Creating necessary directories..."
    
    mkdir -p {data,logs,models}
    mkdir -p monitoring/grafana/provisioning/{dashboards,datasources}
    
    # Set permissions
    chmod 755 data logs models
    chmod -R 755 monitoring/
    
    print_success "Directories created"
}

# Deploy based on environment
deploy() {
    local env_type=$1
    
    case $env_type in
        "dev")
            print_status "Deploying development environment..."
            
            # Use development configuration
            if [ -f .env.dev ]; then
                source .env.dev
            fi
            
            # Start development services
            docker-compose -f docker-compose.dev.yml up --build -d
            
            print_success "Development environment deployed"
            print_status "Access URLs:"
            echo "  API:         http://localhost:8000"
            echo "  API Docs:    http://localhost:8000/docs"
            echo "  Prometheus:  http://localhost:9090"
            echo "  Grafana:     http://localhost:3001"
            ;;
            
        "prod")
            print_status "Deploying production environment..."
            
            # Build and start production services
            docker-compose up --build -d
            
            # Wait for services to be ready
            print_status "Waiting for services to be ready..."
            sleep 60
            
            # Run health checks
            health_check
            
            print_success "Production environment deployed"
            print_status "Access URLs:"
            echo "  API:         http://localhost:8000"
            echo "  API Docs:    http://localhost:8000/docs"
            echo "  Prometheus:  http://localhost:9090"
            echo "  Grafana:     http://localhost:3001"
            ;;
            
        "vercel")
            print_status "Deploying to Vercel..."
            
            # Check if Vercel CLI is installed
            if ! command -v vercel &> /dev/null; then
                print_status "Installing Vercel CLI..."
                npm install -g vercel
            fi
            
            # Deploy to Vercel
            cd api
            vercel --prod
            cd ..
            
            print_success "Vercel deployment completed"
            ;;
            
        *)
            print_error "Invalid deployment type. Use: dev, prod, or vercel"
            exit 1
            ;;
    esac
}

# Health check
health_check() {
    print_status "Running health checks..."
    
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f http://localhost:8000/health > /dev/null 2>&1; then
            print_success "API is healthy"
            break
        else
            print_status "Waiting for API to be ready... (attempt $attempt/$max_attempts)"
            sleep 10
            ((attempt++))
        fi
    done
    
    if [ $attempt -gt $max_attempts ]; then
        print_error "API health check failed after $max_attempts attempts"
        print_status "Checking logs..."
        docker-compose logs api
        exit 1
    fi
    
    # Check other services
    services=("prometheus" "grafana")
    for service in "${services[@]}"; do
        if docker-compose ps $service | grep -q "Up"; then
            print_success "$service is running"
        else
            print_warning "$service is not running properly"
        fi
    done
}

# Cleanup function
cleanup() {
    print_status "Cleaning up old containers and images..."
    
    # Remove stopped containers
    docker container prune -f
    
    # Remove unused images
    docker image prune -f
    
    # Remove unused volumes
    docker volume prune -f
    
    print_success "Cleanup completed"
}

# Main deployment function
main() {
    local deployment_type=${1:-"prod"}
    
    print_status "Starting IndraAI Platform deployment (${deployment_type})..."
    
    check_requirements
    setup_environment
    create_directories
    
    # Optional cleanup
    if [ "$2" = "--clean" ]; then
        cleanup
    fi
    
    deploy $deployment_type
    
    print_success "Deployment completed successfully!"
    
    # Show management commands
    echo ""
    print_status "Management commands:"
    echo "  View logs:   docker-compose logs -f [service-name]"
    echo "  Stop:        docker-compose down"
    echo "  Restart:     docker-compose restart [service-name]"
    echo "  Update:      docker-compose pull && docker-compose up -d"
    echo ""
    
    # Show running containers
    print_status "Running containers:"
    docker-compose ps
}

# Show usage if no arguments
if [ $# -eq 0 ]; then
    echo "Usage: $0 [dev|prod|vercel] [--clean]"
    echo ""
    echo "Deployment types:"
    echo "  dev     - Development environment with hot reload"
    echo "  prod    - Production environment with full features"
    echo "  vercel  - Deploy API to Vercel serverless"
    echo ""
    echo "Options:"
    echo "  --clean - Clean up old containers and images before deployment"
    echo ""
    echo "Examples:"
    echo "  $0 dev              # Deploy development environment"
    echo "  $0 prod --clean     # Deploy production with cleanup"
    echo "  $0 vercel           # Deploy to Vercel"
    exit 1
fi

# Run main function with arguments
main "$@"
