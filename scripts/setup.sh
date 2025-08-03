#!/bin/bash

set -e

echo "🚀 Setting up IndraAI Platform..."

# Colors for output
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

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    print_success "Prerequisites check completed"
}

# Setup directories
setup_directories() {
    print_status "Setting up directories..."
    
    mkdir -p {data,logs,models}
    mkdir -p monitoring/grafana/provisioning/{dashboards,datasources}
    
    # Set permissions
    chmod 755 data logs models
    chmod -R 755 monitoring/
    
    print_success "Directories created"
}

# Setup environment
setup_environment() {
    print_status "Setting up environment..."
    
    if [ ! -f .env ]; then
        print_warning ".env file not found. Please create one based on the template."
        print_status "Required environment variables:"
        echo "  - SUPABASE_URL"
        echo "  - SUPABASE_ANON_KEY"
        echo "  - SUPABASE_SERVICE_ROLE_KEY"
        echo "  - REDIS_PASSWORD"
        echo "  - GRAFANA_ADMIN_PASSWORD"
        return 1
    fi
    
    print_success "Environment configuration found"
}

# Build services
build_services() {
    print_status "Building Docker services..."
    
    docker-compose build --parallel
    
    print_success "Services built successfully"
}

# Start services
start_services() {
    print_status "Starting services..."
    
    # Start core services first
    docker-compose up -d redis
    
    # Wait for Redis
    sleep 10
    
    # Start application services
    docker-compose up -d data-collection data-processing model-training api orchestration
    
    # Start monitoring
    docker-compose up -d prometheus grafana
    
    print_success "Services started successfully"
}

# Health check
health_check() {
    print_status "Running health checks..."
    
    sleep 30  # Wait for services to start
    
    # Check API health
    if curl -f http://localhost:8000/health > /dev/null 2>&1; then
        print_success "API is healthy"
    else
        print_warning "API health check failed"
    fi
    
    # Check Prometheus
    if curl -f http://localhost:9090/-/healthy > /dev/null 2>&1; then
        print_success "Prometheus is healthy"
    else
        print_warning "Prometheus health check failed"
    fi
    
    # Check Grafana
    if curl -f http://localhost:3001/api/health > /dev/null 2>&1; then
        print_success "Grafana is healthy"
    else
        print_warning "Grafana health check failed"
    fi
}

# Display access information
show_access_info() {
    print_success "IndraAI Platform setup completed!"
    echo ""
    echo "📊 Access URLs:"
    echo "  API:         http://localhost:8000"
    echo "  API Docs:    http://localhost:8000/docs"
    echo "  Prometheus:  http://localhost:9090"
    echo "  Grafana:     http://localhost:3001 (admin/admin123)"
    echo ""
    echo "📝 Management:"
    echo "  View logs:   docker-compose logs -f [service-name]"
    echo "  Stop:        ./scripts/stop.sh"
    echo "  Restart:     docker-compose restart [service-name]"
    echo ""
    echo "🔑 API Keys:"
    echo "  Free tier:   No authentication required for /chat/free"
    echo "  Pro tier:    Requires Supabase authentication"
    echo ""
    echo "📚 Documentation:"
    echo "  API Docs:    http://localhost:8000/docs"
    echo "  README:      ./README.md"
}

# Main setup function
main() {
    print_status "Starting IndraAI Platform Setup..."
    
    check_prerequisites
    setup_directories
    
    if ! setup_environment; then
        exit 1
    fi
    
    build_services
    start_services
    health_check
    show_access_info
}

main "$@"
