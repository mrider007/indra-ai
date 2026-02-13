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

# 🧠 Indra AI Platform

Indra AI is an advanced, self-hosting capable AI platform featuring a specialized LLM for Indian languages and culture. It includes a modern React frontend, a Python-based model serving API, and automated training pipelines.

## 🚀 Features

-   **Specialized LLM**: Fine-tuned on Indian cultural data (history, mythology, festivals).
-   **Modern Frontend**: React-based chat interface with real-time WebSocket support.
-   **Model Management**:
    -   **Auto-Training**: Self-improving model based on usage patterns.
    -   **Training Control**: Pro users can trigger training jobs directly from the UI.
    -   **Live Updates**: Zero-downtime model updates via API.
-   **Pro Tier**: Subscription-based access to faster inference, training controls, and higher quotas (via Stripe).
-   **Comprehensive API**: FastAPI backend with Swagger documentation (`/docs`).

## 🛠️ Architecture

The project is structured as follows:

```
indra-ai/
├── src/                # React Frontend source code
├── public/             # Frontend static assets
├── model-serving/      # FastAPI Backend & Model Serving
├── model-training/     # Training pipeline & workers
├── data-collection/    # Scrapers & data ingestion
├── orchestration/      # Job scheduling & management
└── docker-compose.yml  # Container orchestration
```

## ⚡ Quick Start

### Prerequisites
- Docker & Docker Compose
- Node.js 18+ (for local frontend dev)
- NVIDIA GPU (Recommended for training)

### 1. Deployment (Docker)

The easiest way to run the full platform is using our deployment script:

```bash
./deploy.sh prod
```

This will:
1.  Check system requirements.
2.  Build all Docker containers (API, Training, Redis, Supabase connection).
3.  Start the services.

Access the services at:
-   **Frontend**: `http://localhost:3000` (if running locally) or your Vercel URL.
-   **API**: `http://localhost:8000`
-   **API Docs**: `http://localhost:8000/docs`

### 2. Frontend Development (Vercel / Local)

The frontend is a standard React application located at the root.

**Install Dependencies:**
```bash
npm install
```

**Run Locally:**
```bash
npm start
``` 
(Ensure the backend API is running on port 8000 or update `.env`).

**Deploy to Vercel:**
Simply connect this repository to Vercel. It will automatically detect the React app at the root and deploy it.

### 3. Backend Development

The backend code is in `model-serving/`.

```bash
cd model-serving
pip install -r requirements.txt
python app.py
```

## 📚 API Documentation

Complete API documentation is available at `/docs` when the API is running.
Key endpoints:
-   `POST /chat`: Chat with the model.
-   `POST /model/train`: Trigger a training job (Pro).
-   `GET /model/info`: Get current model status.

## 🤝 Contribution

1.  Fork the repo.
2.  Create a feature branch.
3.  Commit your changes.
4.  Push to the branch.
5.  Create a Pull Request.

## 📄 License

MIT
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
