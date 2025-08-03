#!/bin/bash
echo "🚀 Starting development environment..."

# Load dev environment
if [ -f .env.dev ]; then
  # Read every non-comment, non-empty line
  while IFS='=' read -r key value; do
    [[ $key =~ ^#.* ]] && continue   # skip comments
    [[ -z $key ]] && continue        # skip empty lines
    export "$key=$value"
  done < .env.dev
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
