# 🧠 IndraAI Platform

A complete, production-ready AI platform with automated training, serving, and monitoring capabilities. Features both free and pro tiers with Supabase integration.

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Supabase account
- 8GB+ RAM recommended
- 20GB+ free disk space

### Development Setup

\`\`\`bash
# Clone the repository
git clone <your-repo-url>
cd indra-ai

# Setup development environment
chmod +x scripts/dev-setup.sh
./scripts/dev-setup.sh

# Update .env.dev with your Supabase credentials
nano .env.dev

# Start development environment
./scripts/start-dev.sh
\`\`\`

### Production Setup

\`\`\`bash
# Setup production environment
chmod +x scripts/setup.sh
./scripts/setup.sh

# Update .env with your production credentials
nano .env

# Start production environment
./scripts/start.sh
\`\`\`

### Vercel Deployment (Serverless API)

\`\`\`bash
# Deploy API to Vercel
chmod +x scripts/deploy-vercel.sh
./scripts/deploy-vercel.sh
\`\`\`

## 📋 Features

### 🔄 Data Pipeline
- **Web Scraping**: Multi-source scraping with configurable sources
- **Data Processing**: NLP pipeline with quality scoring and filtering
- **Content Deduplication**: Hash-based duplicate detection
- **Automated Workflows**: Redis-based job scheduling and orchestration

### 🤖 Model Training
- **Automated Training**: Trigger-based training when data threshold is reached
- **LoRA Fine-tuning**: Efficient parameter-efficient training
- **Multiple Base Models**: Support for DialoGPT, GPT-2, and custom models
- **Training Monitoring**: Real-time metrics and experiment tracking

### 🌐 API & Serving
- **FastAPI Backend**: High-performance async API with OpenAPI docs
- **Dual Tier System**: Free and Pro tiers with different capabilities
- **Real-time Chat**: WebSocket support for Pro users
- **Authentication**: Supabase-based user management and JWT auth
- **Rate Limiting**: Configurable rate limits per tier

### 📊 Monitoring & Analytics
- **Prometheus Metrics**: Custom metrics for all services
- **Grafana Dashboards**: Pre-configured monitoring dashboards
- **Usage Analytics**: Token usage and API call tracking
- **Health Checks**: Automated service health monitoring

## 🏗️ Architecture

\`\`\`
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Data          │    │   Data          │    │   Model         │
│   Collection    │───▶│   Processing    │───▶│   Training      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Supabase      │    │   Redis Queue   │    │   Model         │
│   Database      │    │   & Cache       │    │   Serving       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 ▼
                    ┌─────────────────┐
                    │   Frontend      │
                    │   Integration   │
                    └─────────────────┘
\`\`\`

## 🔧 Configuration

### Environment Variables

\`\`\`bash
# Supabase Configuration
SUPABASE_URL=your-supabase-url
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# Redis Configuration
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=secure-password

# Model Configuration
MODEL_NAME=microsoft/DialoGPT-medium
BATCH_SIZE=4
TRAINING_EPOCHS=3
AUTO_TRAIN_THRESHOLD=1000

# Pro Features
ENABLE_PRO_FEATURES=true
PRO_API_KEY=your-pro-api-key
STRIPE_SECRET_KEY=your-stripe-key
\`\`\`

### Scraping Sources

Edit `data-collection/config/sources.yaml`:

\`\`\`yaml
sources:
  - name: "tech_news"
    base_url: "https://techcrunch.com"
    selectors:
      title: "h1.article__title"
      content: ".article-content p"
    max_pages: 50
    delay: 2.0
    enabled: true
\`\`\`

### Training Configuration

Edit `model-training/config/training.yaml`:

\`\`\`yaml
model_name: "microsoft/DialoGPT-medium"
batch_size: 4
learning_rate: 5e-5
num_epochs: 3
use_lora: true
min_quality_score: 0.6
\`\`\`

## 📊 Database Schema

### Core Tables

- `user_profiles` - User information and subscription tiers
- `scraped_content` - Raw scraped data with deduplication
- `processed_content` - Cleaned and processed training data
- `training_jobs` - Model training job tracking
- `chat_sessions` - User chat sessions
- `chat_messages` - Individual chat messages with metrics
- `api_usage` - API usage analytics and quota tracking

### Supabase Setup

1. Create a new Supabase project
2. Apply migrations: `supabase db push`
3. Enable Row Level Security policies
4. Configure authentication providers

## 🔒 Security & Authentication

### Free Tier
- No authentication required
- Rate limited to 10 requests/hour
- Limited response length (100 tokens)
- Basic functionality only

### Pro Tier
- Supabase JWT authentication required
- Higher rate limits (10,000 requests/hour)
- Full response length (500 tokens)
- WebSocket access
- Priority support

### Security Features
- Row Level Security (RLS) policies
- JWT token validation
- Rate limiting per user/IP
- Input validation and sanitization
- CORS configuration
- SQL injection prevention

## 📝 API Documentation

### Authentication

Include JWT token in Authorization header:
\`\`\`bash
Authorization: Bearer YOUR_JWT_TOKEN
\`\`\`

### Endpoints

#### Free Tier
- `POST /chat/free` - Free chat (no auth required)
- `GET /health` - Health check
- `GET /model/info` - Model information

#### Pro Tier (Requires Auth)
- `POST /chat` - Full chat functionality
- `WS /ws/{session_id}` - WebSocket chat
- `GET /chat/history/{session_id}` - Chat history
- `GET /user/stats` - User statistics and quota

#### Admin
- `POST /model/update` - Update loaded model
- `GET /metrics` - Prometheus metrics

### Example Usage

\`\`\`bash
# Free tier chat
curl -X POST http://localhost:8000/chat/free \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, IndraAI!", "max_length": 100}'

# Pro tier chat (with auth)
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Explain quantum computing",
    "max_length": 300,
    "temperature": 0.7
  }'

# WebSocket connection (Pro only)
const ws = new WebSocket('ws://localhost:8000/ws/session_123');
ws.send(JSON.stringify({
  token: 'YOUR_JWT_TOKEN',
  message: 'Hello!',
  max_length: 200
}));
\`\`\`

## 🚀 Deployment Options

### 1. Local Development
\`\`\`bash
./scripts/start-dev.sh
\`\`\`

### 2. Production Server
\`\`\`bash
./scripts/setup.sh
./scripts/start.sh
\`\`\`

### 3. Vercel Serverless
\`\`\`bash
./scripts/deploy-vercel.sh
\`\`\`

### 4. Docker Swarm
\`\`\`bash
docker stack deploy -c docker-compose.yml indra-ai
\`\`\`

### 5. Kubernetes
\`\`\`bash
# Convert docker-compose to k8s manifests
kompose convert -f docker-compose.yml
kubectl apply -f .
\`\`\`

## 📊 Monitoring

### Metrics Available
- **API Performance**: Request latency, throughput, error rates
- **Model Inference**: Inference time, token usage by tier
- **Data Pipeline**: Scraping rates, processing success rates
- **Training**: Job status, model performance metrics
- **User Analytics**: Usage patterns, tier distribution

### Grafana Dashboards
- **System Overview**: High-level platform health
- **API Performance**: Request metrics and response times
- **User Analytics**: Usage patterns and tier metrics
- **Training Pipeline**: Model training progress and results
- **Data Pipeline**: Scraping and processing statistics

### Alerts
- High error rates (>5%)
- Slow response times (>2s)
- Training job failures
- Quota exceeded events
- Service health issues

## 🧪 Testing

### Development Testing
\`\`\`bash
# Start dev environment
./scripts/start-dev.sh

# Run tests
./scripts/test-dev.sh

# Test specific endpoints
curl http://localhost:8000/health
curl -X POST http://localhost:8000/chat/free \
  -H "Content-Type: application/json" \
  -d '{"message": "Test message"}'
\`\`\`

### Load Testing
\`\`\`bash
# Install k6
brew install k6  # macOS
# or
sudo apt install k6  # Ubuntu

# Run load test
k6 run scripts/load-test.js
\`\`\`

### Integration Testing
\`\`\`bash
# Test full pipeline
python scripts/test-integration.py
\`\`\`

## 🔄 Management Commands

### Service Management
\`\`\`bash
# Start all services
./scripts/start.sh

# Stop all services
./scripts/stop.sh

# Restart specific service
docker-compose restart api

# View logs
docker-compose logs -f api
docker-compose logs -f data-collection
\`\`\`

### Database Management
\`\`\`bash
# Apply migrations
supabase db push

# Reset database
supabase db reset

# Backup database
supabase db dump > backup.sql

# View database
supabase db studio
\`\`\`

### Model Management
\`\`\`bash
# Trigger manual training
curl -X POST http://localhost:8000/model/train

# Update model
curl -X POST http://localhost:8000/model/update \
  -H "Content-Type: application/json" \
  -d '{"model_path": "/app/models/new-model"}'

# Check model info
curl http://localhost:8000/model/info
\`\`\`

## 💰 Monetization

### Subscription Tiers

#### Free Tier
- 100 requests/hour
- 50,000 tokens/day
- Basic model responses
- Community support

#### Pro Tier ($19/month)
- 10,000 requests/hour
- 1,000,000 tokens/day
- Advanced model features
- WebSocket access
- Priority support
- Custom model training

### Stripe Integration
\`\`\`bash
# Set up Stripe webhook
STRIPE_WEBHOOK_SECRET=your-webhook-secret

# Handle subscription events
POST /subscription/webhook
\`\`\`

## 🐛 Troubleshooting

### Common Issues

#### Service Won't Start
\`\`\`bash
# Check logs
docker-compose logs service-name

# Check ports
netstat -tulpn | grep :8000

# Restart service
docker-compose restart service-name
\`\`\`

#### Database Connection Issues
\`\`\`bash
# Check Supabase connection
curl -H "apikey: YOUR_ANON_KEY" \
  "https://your-project.supabase.co/rest/v1/user_profiles"

# Reset database connection
docker-compose restart api
\`\`\`

#### Model Loading Issues
\`\`\`bash
# Check model directory
ls -la models/

# Check GPU availability
nvidia-smi

# Use CPU-only mode
export CUDA_VISIBLE_DEVICES=""
\`\`\`

#### Memory Issues
\`\`\`bash
# Check memory usage
docker stats

# Reduce batch size
export BATCH_SIZE=1

# Limit workers
export API_WORKERS=1
\`\`\`

### Debug Mode
\`\`\`bash
# Enable debug logging
export DEBUG=true
export LOG_LEVEL=DEBUG

# View detailed logs
docker-compose logs -f api
\`\`\`

## 📚 Development

### Project Structure
\`\`\`
indra-ai/
├── data-collection/      # Web scraping service
├── data-processing/      # Data cleaning and NLP
├── model-training/       # Training pipeline
├── model-serving/        # FastAPI application
├── orchestration/        # Job scheduling
├── monitoring/          # Prometheus & Grafana
├── supabase/           # Database migrations
├── scripts/            # Setup and management
├── api/                # Vercel serverless
└── README.md
\`\`\`

### Adding New Features

1. **New Scraping Source**:
   - Add to `data-collection/config/sources.yaml`
   - Test with limited pages first
   - Monitor quality scores

2. **New API Endpoint**:
   - Add to `model-serving/app.py`
   - Update OpenAPI documentation
   - Add authentication if needed
   - Update rate limiting

3. **New Model**:
   - Update `model-training/config/training.yaml`
   - Test with small dataset first
   - Monitor training metrics

### Code Quality
\`\`\`bash
# Format code
black .
isort .

# Lint code
flake8 .
mypy .

# Run tests
pytest tests/
\`\`\`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Add tests for new functionality
5. Run the test suite: `./scripts/test-dev.sh`
6. Submit a pull request

### Development Workflow
\`\`\`bash
# Setup development environment
./scripts/dev-setup.sh

# Make changes
# ...

# Test changes
./scripts/test-dev.sh

# Format and lint
black .
flake8 .

# Commit and push
git add .
git commit -m "feat: add new feature"
git push origin feature-name
\`\`\`

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Hugging Face** - Transformers library and model hub
- **FastAPI** - High-performance web framework
- **Supabase** - Backend-as-a-Service platform
- **Redis** - In-memory data structure store
- **Docker** - Containerization platform
- **Prometheus & Grafana** - Monitoring and visualization
- **Vercel** - Serverless deployment platform

## 📞 Support

- **Documentation**: [API Docs](http://localhost:8000/docs)
- **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-repo/discussions)
- **Email**: support@indra-ai.com

## 🔮 Roadmap

### Q1 2024
- [ ] Multi-language support
- [ ] Advanced model fine-tuning
- [ ] Mobile app integration
- [ ] Enterprise features

### Q2 2024
- [ ] Custom model marketplace
- [ ] Advanced analytics dashboard
- [ ] Team collaboration features
- [ ] API versioning

### Q3 2024
- [ ] Voice interaction support
- [ ] Image generation capabilities
- [ ] Advanced security features
- [ ] Performance optimizations

---

**IndraAI - Intelligent AI Platform for the Future 🚀**

*Built with ❤️ for developers, by developers*
