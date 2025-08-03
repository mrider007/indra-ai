import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, AsyncGenerator
from contextlib import asynccontextmanager
from fastapi import Request

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
import redis
from supabase import create_client, Client
from loguru import logger
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import stripe

# Metrics
REQUESTS_TOTAL = Counter('requests_total', 'Total requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('request_duration_seconds', 'Request duration')
ACTIVE_CONNECTIONS = Gauge('active_websocket_connections', 'Active WebSocket connections')
MODEL_INFERENCE_TIME = Histogram('model_inference_seconds', 'Model inference time')
TOKEN_USAGE = Counter('tokens_used_total', 'Total tokens used', ['user_tier'])

# Rate limiting
limiter = Limiter(key_func=get_remote_address)

# Pydantic models
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    session_id: Optional[str] = None
    max_length: Optional[int] = Field(default=150, ge=50, le=500)
    temperature: Optional[float] = Field(default=0.7, ge=0.1, le=2.0)

class ChatResponse(BaseModel):
    response: str
    session_id: str
    timestamp: datetime
    inference_time: float
    tokens_used: int
    remaining_quota: Optional[int] = None

class ModelInfo(BaseModel):
    model_name: str
    model_path: str
    loaded_at: datetime
    parameters: int
    status: str
    version: str

class HealthCheck(BaseModel):
    status: str
    model_loaded: bool
    timestamp: datetime
    version: str

class UserStats(BaseModel):
    user_id: str
    tier: str
    requests_today: int
    tokens_used_today: int
    quota_remaining: int
    subscription_status: str

# Global model storage
class ModelManager:
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.model_info = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
    def load_model(self, model_path: str):
        """Load model and tokenizer"""
        try:
            logger.info(f"Loading model from: {model_path}")
            
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
                
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map="auto" if torch.cuda.is_available() else None,
            )
            
            # Count parameters
            param_count = sum(p.numel() for p in self.model.parameters())
            
            self.model_info = ModelInfo(
                model_name=os.path.basename(model_path),
                model_path=model_path,
                loaded_at=datetime.utcnow(),
                parameters=param_count,
                status="loaded",
                version=os.getenv('MODEL_VERSION', 'v1.0.0')
            )
            
            logger.info(f"Model loaded successfully: {param_count:,} parameters")
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
            
    def generate_response(self, prompt: str, max_length: int = 150, temperature: float = 0.7) -> tuple[str, int]:
        """Generate response using the loaded model"""
        if not self.model or not self.tokenizer:
            raise HTTPException(status_code=503, detail="Model not loaded")
            
        try:
            with MODEL_INFERENCE_TIME.time():
                inputs = self.tokenizer.encode(prompt, return_tensors="pt").to(self.device)
                
                with torch.no_grad():
                    outputs = self.model.generate(
                        inputs,
                        max_length=inputs.shape[1] + max_length,
                        temperature=temperature,
                        do_sample=True,
                        pad_token_id=self.tokenizer.eos_token_id,
                        eos_token_id=self.tokenizer.eos_token_id,
                        num_return_sequences=1
                    )
                    
                response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
                
                # Remove the original prompt from the response
                if response.startswith(prompt):
                    response = response[len(prompt):].strip()
                    
                # Count tokens used
                tokens_used = len(outputs[0]) - len(inputs[0])
                    
                return response, tokens_used
                
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise HTTPException(status_code=500, detail="Error generating response")

# Initialize components
model_manager = ModelManager()
security = HTTPBearer()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        ACTIVE_CONNECTIONS.set(len(self.active_connections))
        
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        ACTIVE_CONNECTIONS.set(len(self.active_connections))

manager = ConnectionManager()

# Authentication and authorization
class AuthManager:
    def __init__(self, supabase: Client):
        self.supabase = supabase
        
    async def get_current_user(self, credentials: HTTPAuthorizationCredentials = Depends(security)):
        """Get current user from JWT token"""
        try:
            token = credentials.credentials
            user = self.supabase.auth.get_user(token)
            
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication credentials"
                )
                
            return user.user
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
            
    async def check_user_quota(self, user_id: str) -> Dict:
        """Check user's API quota"""
        today = datetime.utcnow().date()
        
        # Get user profile
        profile_result = self.supabase.table('user_profiles').select('*').eq('user_id', user_id).execute()
        
        if not profile_result.data:
            raise HTTPException(status_code=404, detail="User profile not found")
            
        profile = profile_result.data[0]
        
        # Get today's usage
        usage_result = self.supabase.table('api_usage').select('*').eq('user_id', user_id).gte('created_at', today).execute()
        
        requests_today = len(usage_result.data) if usage_result.data else 0
        tokens_today = sum(item['tokens_used'] for item in usage_result.data) if usage_result.data else 0
        
        # Check limits based on tier
        tier = profile['tier']
        if tier == 'pro':
            max_requests = int(os.getenv('PRO_REQUESTS_PER_HOUR', 10000))
            max_tokens = int(os.getenv('PRO_TOKENS_PER_DAY', 1000000))
        else:
            max_requests = int(os.getenv('FREE_REQUESTS_PER_HOUR', 100))
            max_tokens = int(os.getenv('FREE_TOKENS_PER_DAY', 50000))
            
        if requests_today >= max_requests:
            raise HTTPException(status_code=429, detail="Request quota exceeded")
            
        if tokens_today >= max_tokens:
            raise HTTPException(status_code=429, detail="Token quota exceeded")
            
        return {
            'user_id': user_id,
            'tier': tier,
            'requests_today': requests_today,
            'tokens_today': tokens_today,
            'requests_remaining': max_requests - requests_today,
            'tokens_remaining': max_tokens - tokens_today
        }
        
    async def log_api_usage(self, user_id: str, endpoint: str, tokens_used: int):
        """Log API usage"""
        try:
            self.supabase.table('api_usage').insert({
                'user_id': user_id,
                'endpoint': endpoint,
                'tokens_used': tokens_used,
                'created_at': datetime.utcnow().isoformat()
            }).execute()
        except Exception as e:
            logger.error(f"Failed to log API usage: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting IndraAI API server")
    
    # Setup Supabase
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    supabase = create_client(url, key)
    app.state.supabase = supabase
    app.state.auth_manager = AuthManager(supabase)
    
    # Setup Redis
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
    password = os.getenv('REDIS_PASSWORD')
    app.state.redis = redis.from_url(redis_url, password=password, decode_responses=True)
    
    # Setup Stripe
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
    
    # Load latest model
    models_dir = "/app/models"
    if os.path.exists(models_dir):
        model_dirs = [d for d in os.listdir(models_dir) if os.path.isdir(os.path.join(models_dir, d))]
        if model_dirs:
            latest_model = max(model_dirs)
            model_path = os.path.join(models_dir, latest_model)
            try:
                model_manager.load_model(model_path)
            except Exception as e:
                logger.error(f"Failed to load model on startup: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down IndraAI API server")

# Initialize FastAPI app
app = FastAPI(
    title="IndraAI API",
    description="Advanced AI Platform with Free and Pro Tiers",
    version="2.0.0",
    lifespan=lifespan
)

# Add CORS middleware
cors_origins = json.loads(os.getenv('CORS_ORIGINS', '["*"]'))
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Setup logging
logger.add("/app/logs/api.log", rotation="100 MB", retention="30 days")

@app.middleware("http")
async def metrics_middleware(request, call_next):
    start_time = datetime.utcnow()
    
    response = await call_next(request)
    
    duration = (datetime.utcnow() - start_time).total_seconds()
    REQUEST_DURATION.observe(duration)
    REQUESTS_TOTAL.labels(
        method=request.method, 
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    return response

@app.get("/health", response_model=HealthCheck)
@limiter.limit("10/minute")
async def health_check(request:Request):
    """Health check endpoint"""
    return HealthCheck(
        status="healthy",
        model_loaded=model_manager.model is not None,
        timestamp=datetime.utcnow(),
        version=os.getenv('MODEL_VERSION', 'v2.0.0')
    )

@app.get("/model/info", response_model=ModelInfo)
@limiter.limit("5/minute")
async def get_model_info(request: Request):
    """Get information about the loaded model"""
    if not model_manager.model_info:
        raise HTTPException(status_code=503, detail="No model loaded")
    return model_manager.model_info

@app.post("/chat", response_model=ChatResponse)
@limiter.limit("100/hour")
async def chat(
    request: Request,  
    request_data: ChatRequest, 
    background_tasks: BackgroundTasks,
    user = Depends(lambda: app.state.auth_manager.get_current_user)
):
    """Chat with the AI model (requires authentication)"""
    start_time = datetime.utcnow()
    
    # Check user quota
    quota_info = await app.state.auth_manager.check_user_quota(user.id)
    
    # Generate session ID if not provided
    session_id = request_data.session_id or f"session_{user.id}_{int(datetime.utcnow().timestamp())}"
    
    # Generate response
    response_text, tokens_used = model_manager.generate_response(
        request_data.message,
        max_length=request_data.max_length,
        temperature=request_data.temperature
    )
    
    inference_time = (datetime.utcnow() - start_time).total_seconds()
    
    # Log usage
    background_tasks.add_task(
        app.state.auth_manager.log_api_usage,
        user.id,
        "/chat",
        tokens_used
    )
    
    # Save chat history
    background_tasks.add_task(
        save_chat_history,
        session_id,
        user.id,
        request_data.message,
        response_text,
        tokens_used,
        inference_time
    )
    
    # Update metrics
    TOKEN_USAGE.labels(user_tier=quota_info['tier']).inc(tokens_used)
    
    return ChatResponse(
        response=response_text,
        session_id=session_id,
        timestamp=datetime.utcnow(),
        inference_time=inference_time,
        tokens_used=tokens_used,
        remaining_quota=quota_info['tokens_remaining'] - tokens_used
    )

@app.post("/chat/free", response_model=ChatResponse)
@limiter.limit("10/hour")
async def chat_free(request: Request, request_data: ChatRequest, background_tasks: BackgroundTasks):
    """Free tier chat (limited functionality)"""
    start_time = datetime.utcnow()
    
    # Limit free tier capabilities
    max_length = min(request_data.max_length, 100)  # Shorter responses
    
    # Generate session ID
    session_id = request_data.session_id or f"free_session_{int(datetime.utcnow().timestamp())}"
    
    # Generate response
    response_text, tokens_used = model_manager.generate_response(
        request_data.message,
        max_length=max_length,
        temperature=0.7  # Fixed temperature for free tier
    )
    
    inference_time = (datetime.utcnow() - start_time).total_seconds()
    
    # Update metrics
    TOKEN_USAGE.labels(user_tier='free').inc(tokens_used)
    
    return ChatResponse(
        response=response_text,
        session_id=session_id,
        timestamp=datetime.utcnow(),
        inference_time=inference_time,
        tokens_used=tokens_used
    )

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time chat (Pro feature)"""
    await manager.connect(websocket)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Verify pro access if required
            token = message_data.get("token")
            if token:
                try:
                    user = app.state.supabase.auth.get_user(token)
                    if user:
                        quota_info = await app.state.auth_manager.check_user_quota(user.user.id)
                        if quota_info['tier'] != 'pro':
                            await websocket.send_text(json.dumps({
                                "error": "WebSocket access requires Pro subscription"
                            }))
                            continue
                except:
                    await websocket.send_text(json.dumps({
                        "error": "Invalid authentication"
                    }))
                    continue
            
            user_message = message_data.get("message", "")
            max_length = message_data.get("max_length", 150)
            temperature = message_data.get("temperature", 0.7)
            
            if user_message:
                # Generate response
                start_time = datetime.utcnow()
                response_text, tokens_used = model_manager.generate_response(
                    user_message,
                    max_length=max_length,
                    temperature=temperature
                )
                inference_time = (datetime.utcnow() - start_time).total_seconds()
                
                # Send response back
                response_data = {
                    "response": response_text,
                    "session_id": session_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "inference_time": inference_time,
                    "tokens_used": tokens_used
                }
                
                await websocket.send_text(json.dumps(response_data))
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"WebSocket disconnected for session: {session_id}")

@app.get("/user/stats", response_model=UserStats)
async def get_user_stats(user = Depends(lambda: app.state.auth_manager.get_current_user)):
    """Get user statistics and quota information"""
    quota_info = await app.state.auth_manager.check_user_quota(user.id)
    
    # Get subscription status
    profile_result = app.state.supabase.table('user_profiles').select('subscription_status').eq('user_id', user.id).execute()
    subscription_status = profile_result.data[0]['subscription_status'] if profile_result.data else 'inactive'
    
    return UserStats(
        user_id=user.id,
        tier=quota_info['tier'],
        requests_today=quota_info['requests_today'],
        tokens_used_today=quota_info['tokens_today'],
        quota_remaining=quota_info['tokens_remaining'],
        subscription_status=subscription_status
    )

@app.get("/chat/history/{session_id}")
async def get_chat_history(
    session_id: str, 
    limit: int = 50,
    user = Depends(lambda: app.state.auth_manager.get_current_user)
):
    """Get chat history for a session"""
    result = app.state.supabase.table('chat_messages').select('*').eq('session_id', session_id).eq('user_id', user.id).order('created_at', desc=True).limit(limit).execute()
    
    if not result.data:
        return []
        
    return [
        {
            "user_message": msg['user_message'],
            "bot_response": msg['bot_response'],
            "timestamp": msg['created_at'],
            "tokens_used": msg['tokens_used'],
            "inference_time": msg['inference_time']
        }
        for msg in reversed(result.data)
    ]

@app.post("/model/update")
async def update_model(model_path: str):
    """Update the loaded model (Admin only)"""
    # TODO: Add admin authentication
    try:
        model_manager.load_model(model_path)
        return {"status": "success", "message": f"Model updated to {model_path}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update model: {str(e)}")

@app.post("/subscription/webhook")
async def stripe_webhook(request):
    """Handle Stripe webhook events"""
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    endpoint_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle subscription events
    if event['type'] == 'customer.subscription.created':
        subscription = event['data']['object']
        # Update user to pro tier
        customer_id = subscription['customer']
        
        # Find user by customer ID and update tier
        result = app.state.supabase.table('user_profiles').update({
            'tier': 'pro',
            'subscription_status': 'active',
            'stripe_customer_id': customer_id
        }).eq('stripe_customer_id', customer_id).execute()
        
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        customer_id = subscription['customer']
        
        # Downgrade user to free tier
        result = app.state.supabase.table('user_profiles').update({
            'tier': 'free',
            'subscription_status': 'cancelled'
        }).eq('stripe_customer_id', customer_id).execute()
    
    return {"status": "success"}

@app.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

async def save_chat_history(session_id: str, user_id: str, user_message: str, bot_response: str, tokens_used: int, inference_time: float):
    """Save chat interaction to database"""
    try:
        app.state.supabase.table('chat_messages').insert({
            'session_id': session_id,
            'user_id': user_id,
            'user_message': user_message,
            'bot_response': bot_response,
            'tokens_used': tokens_used,
            'inference_time': inference_time,
            'created_at': datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        logger.error(f"Failed to save chat history: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
