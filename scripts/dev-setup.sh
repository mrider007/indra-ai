#!/bin/bash

set -e

echo "🔧 Setting up IndraAI Development Environment..."

# Create development environment file
create_dev_env() {
    echo "Creating development environment..."
    
    cat > .env.dev << 'EOF'
# Development Environment
ENVIRONMENT=development
DEBUG=true

# Supabase (use your project credentials)
SUPABASE_URL=your-supabase-url
SUPABASE_ANON_KEY=your-supabase-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key

# Redis
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=dev_redis_password

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=1
CORS_ORIGINS=["http://localhost:3000", "http://localhost:3001"]

# Model Configuration (lightweight for dev)
MODEL_NAME=microsoft/DialoGPT-small
BATCH_SIZE=1
LEARNING_RATE=5e-5
TRAINING_EPOCHS=1

# Scraping (limited for dev)
MAX_PAGES_PER_SOURCE=5
SCRAPING_DELAY=2
AUTO_TRAIN_THRESHOLD=100

# Monitoring
PROMETHEUS_PORT=9090
GRAFANA_PORT=3001
GRAFANA_ADMIN_PASSWORD=dev123

# Pro Features (disabled in dev)
ENABLE_PRO_FEATURES=false
FREE_REQUESTS_PER_HOUR=1000
PRO_REQUESTS_PER_HOUR=10000
FREE_TOKENS_PER_DAY=100000
PRO_TOKENS_PER_DAY=1000000
EOF

    echo "✅ Development environment file created (.env.dev)"
}

# Create development docker-compose
create_dev_compose() {
    echo "Creating development docker-compose..."
    
    cat > docker-compose.dev.yml << 'EOF'
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD}
    ports:
      - "6379:6379"
    volumes:
      - redis_dev_data:/data

  api:
    build: ./model-serving
    environment:
      - API_HOST=${API_HOST}
      - API_PORT=${API_PORT}
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_ANON_KEY=${SUPABASE_ANON_KEY}
      - SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY}
      - REDIS_URL=${REDIS_URL}
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - DEBUG=${DEBUG}
      - ENVIRONMENT=${ENVIRONMENT}
    ports:
      - "8000:8000"
    volumes:
      - ./models:/app/models
      - ./logs:/app/logs
      - ./model-serving:/app
    depends_on:
      - redis
    command: uvicorn app:app --host 0.0.0.0 --port 8000 --reload

  data-collection:
    build: ./data-collection
    environment:
      - REDIS_URL=${REDIS_URL}
      - REDIS_PASSWORD=${REDIS_PASSWORD}
      - SUPABASE_URL=${SUPABASE_URL}
      - SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY}
      - RUN_AS_WORKER=true
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./data-collection:/app
    depends_on:
      - redis

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}
    volumes:
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning

volumes:
  redis_dev_data:
EOF

    echo "✅ Development docker-compose file created"
}

# Create development scripts
create_dev_scripts() {
    echo "Creating development scripts..."
    
    # Start dev script
    cat > scripts/start-dev.sh << 'EOF'
#!/bin/bash
echo "🚀 Starting development environment..."

# Load dev environment
if [ -f .env.dev ]; then
    export $(cat .env.dev | xargs)
fi

# Start services
docker-compose -f docker-compose.dev.yml up -d

echo "✅ Development environment started!"
echo ""
echo "📊 Access URLs:"
echo "  API:         http://localhost:8000"
echo "  API Docs:    http://localhost:8000/docs"
echo "  Prometheus:  http://localhost:9090"
echo "  Grafana:     http://localhost:3001"
EOF

    # Stop dev script
    cat > scripts/stop-dev.sh << 'EOF'
#!/bin/bash
echo "🛑 Stopping development environment..."
docker-compose -f docker-compose.dev.yml down
echo "✅ Development environment stopped"
EOF

    # Test script
    cat > scripts/test-dev.sh << 'EOF'
#!/bin/bash
echo "🧪 Running development tests..."

# Test API health
echo "Testing API health..."
curl -f http://localhost:8000/health

# Test free chat endpoint
echo "Testing free chat..."
curl -X POST http://localhost:8000/chat/free \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, IndraAI!"}'

echo "✅ Tests completed"
EOF

    chmod +x scripts/start-dev.sh scripts/stop-dev.sh scripts/test-dev.sh
    echo "✅ Development scripts created"
}

# Main function
main() {
    create_dev_env
    create_dev_compose
    create_dev_scripts
    
    echo ""
    echo "🎉 Development environment setup completed!"
    echo ""
    echo "Next steps:"
    echo "1. Update .env.dev with your Supabase credentials"
    echo "2. Run: ./scripts/start-dev.sh"
    echo "3. Test: ./scripts/test-dev.sh"
    echo "4. Develop with hot reload enabled"
}

main "$@"
