#!/bin/bash

set -e

echo "🏭 Setting up Indra LLM Production Environment..."

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

# Generate secure passwords
generate_password() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-25
}

# Create production environment
create_prod_env() {
    print_status "Creating production environment file..."
    
    if [ -f .env.prod ]; then
        print_warning ".env.prod already exists. Backing up..."
        cp .env.prod .env.prod.backup
    fi
    
    # Generate secure passwords
    DB_PASSWORD=$(generate_password)
    REDIS_PASSWORD=$(generate_password)
    GRAFANA_PASSWORD=$(generate_password)
    
    cat > .env.prod << EOF
# Production Environment Configuration
ENVIRONMENT=production

# Database
POSTGRES_DB=indra_prod
POSTGRES_USER=indra_prod
POSTGRES_PASSWORD=${DB_PASSWORD}

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=${REDIS_PASSWORD}

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Model Configuration
MODEL_NAME=microsoft/DialoGPT-medium
BATCH_SIZE=4
LEARNING_RATE=5e-5
TRAINING_EPOCHS=3

# Scraping Configuration
MAX_PAGES_PER_SOURCE=100
SCRAPING_DELAY=1

# Frontend
REACT_APP_API_URL=https://your-domain.com/api
REACT_APP_WS_URL=wss://your-domain.com/ws

# Monitoring
GRAFANA_ADMIN_PASSWORD=${GRAFANA_PASSWORD}

# Security
JWT_SECRET_KEY=$(generate_password)
ENCRYPTION_KEY=$(generate_password)
EOF
    
    print_success "Production environment file created"
    print_warning "Please update REACT_APP_API_URL and REACT_APP_WS_URL with your actual domain"
}

# Setup SSL certificates
setup_ssl() {
    print_status "Setting up SSL certificates..."
    
    mkdir -p nginx/ssl
    
    # Create self-signed certificate for development
    if [ ! -f nginx/ssl/cert.pem ]; then
        openssl req -x509 -newkey rsa:4096 -keyout nginx/ssl/key.pem -out nginx/ssl/cert.pem -days 365 -nodes -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost"
        print_success "Self-signed SSL certificate created"
        print_warning "For production, replace with proper SSL certificates"
    fi
}

# Create nginx configuration
create_nginx_config() {
    print_status "Creating nginx configuration..."
    
    cat > nginx/nginx.conf << 'EOF'
events {
    worker_connections 1024;
}

http {
    upstream api {
        server api:8000;
    }
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    
    server {
        listen 80;
        server_name localhost;
        return 301 https://$server_name$request_uri;
    }
    
    server {
        listen 443 ssl http2;
        server_name localhost;
        
        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        
        # Security headers
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";
        
        # Frontend
        location / {
            root /usr/share/nginx/html;
            index index.html index.htm;
            try_files $uri $uri/ /index.html;
        }
        
        # API
        location /api/ {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://api/;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
        
        # WebSocket
        location /ws/ {
            proxy_pass http://api/ws/;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_set_header Host $host;
        }
    }
}
EOF
    
    print_success "Nginx configuration created"
}

# Create backup script
create_backup_script() {
    print_status "Creating backup script..."
    
    cat > scripts/backup-prod.sh << 'EOF'
#!/bin/bash

BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "📦 Creating production backup..."

# Database backup
docker-compose -f docker-compose.prod.yml exec -T postgres pg_dump -U $POSTGRES_USER $POSTGRES_DB > "$BACKUP_DIR/database.sql"

# Redis backup
docker-compose -f docker-compose.prod.yml exec -T redis redis-cli --rdb - > "$BACKUP_DIR/redis.rdb"

# Models backup
cp -r models "$BACKUP_DIR/"

# Configuration backup
cp .env.prod "$BACKUP_DIR/"

echo "✅ Backup created in $BACKUP_DIR"
EOF

    chmod +x scripts/backup-prod.sh
    print_success "Backup script created"
}

# Create production scripts
create_prod_scripts() {
    print_status "Creating production scripts..."
    
    # Deploy script
    cat > scripts/deploy-prod.sh << 'EOF'
#!/bin/bash
echo "🚀 Deploying to production..."

# Load production environment
export $(cat .env.prod | xargs)

# Create backup before deployment
./scripts/backup-prod.sh

# Pull latest images
docker-compose -f docker-compose.prod.yml pull

# Build and deploy
docker-compose -f docker-compose.prod.yml up --build -d

# Wait for services
echo "⏳ Waiting for services to start..."
sleep 30

# Health check
./scripts/health-check.sh

echo "✅ Production deployment completed!"
EOF

    # Health check script
    cat > scripts/health-check.sh << 'EOF'
#!/bin/bash
echo "🏥 Running health checks..."

services=("postgres" "redis" "api" "frontend")
failed=0

for service in "${services[@]}"; do
    if docker-compose -f docker-compose.prod.yml ps $service | grep -q "Up"; then
        echo "✅ $service is healthy"
    else
        echo "❌ $service is not healthy"
        failed=1
    fi
done

# API health check
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ API health endpoint is responding"
else
    echo "❌ API health endpoint is not responding"
    failed=1
fi

if [ $failed -eq 0 ]; then
    echo "🎉 All health checks passed!"
    exit 0
else
    echo "💥 Some health checks failed!"
    exit 1
fi
EOF

    # Stop production script
    cat > scripts/stop-prod.sh << 'EOF'
#!/bin/bash
echo "🛑 Stopping production environment..."

# Create backup before stopping
./scripts/backup-prod.sh

# Stop services
docker-compose -f docker-compose.prod.yml down

echo "✅ Production environment stopped"
EOF

    chmod +x scripts/*.sh
    print_success "Production scripts created"
}

# Setup monitoring
setup_monitoring() {
    print_status "Setting up production monitoring..."
    
    # Create Prometheus config for production
    cat > monitoring/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "alert_rules.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'api'
    static_configs:
      - targets: ['api:8000']
    metrics_path: /metrics
    scrape_interval: 15s

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres:5432']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
EOF

    print_success "Production monitoring configured"
}

# Main setup function
main() {
    print_status "Starting Indra LLM Production Setup..."
    
    create_prod_env
    setup_ssl
    create_nginx_config
    create_backup_script
    create_prod_scripts
    setup_monitoring
    
    print_success "Production environment setup completed!"
    print_status "Next steps:"
    echo "  1. Update .env.prod with your domain and settings"
    echo "  2. Replace SSL certificates in nginx/ssl/ for production"
    echo "  3. Run: ./scripts/deploy-prod.sh"
    echo "  4. Monitor: http://localhost:3001 (Grafana)"
    echo "  5. Backup: ./scripts/backup-prod.sh"
}

main "$@"
