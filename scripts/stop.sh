#!/bin/bash

echo "🛑 Stopping IndraAI Platform..."

# Stop all services
docker-compose down

echo "✅ IndraAI Platform stopped successfully!"
