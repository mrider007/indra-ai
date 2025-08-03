#!/bin/bash

echo "🚀 Starting IndraAI Platform..."

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | xargs)
fi

# Start services in order
echo "Starting Redis..."
docker-compose up -d redis

echo "Waiting for Redis to be ready..."
sleep 10

echo "Starting core services..."
docker-compose up -d data-collection data-processing model-training api orchestration

echo "Starting monitoring..."
docker-compose up -d prometheus grafana

echo "✅ IndraAI Platform started successfully!"
echo ""
echo "📊 Access URLs:"
echo "  API:         http://localhost:8000"
echo "  API Docs:    http://localhost:8000/docs"
echo "  Prometheus:  http://localhost:9090"
echo "  Grafana:     http://localhost:3001"
echo ""
echo "📝 View logs: docker-compose logs -f [service-name]"
