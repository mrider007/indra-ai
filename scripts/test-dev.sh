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
