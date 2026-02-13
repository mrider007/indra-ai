# Vercel serverless function for IndraAI API
import os
# Vercel Deployment: Active
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
import redis

# Initialize FastAPI
app = FastAPI(
    title="IndraAI Serverless API",
    version="1.0.0",
    root_path="/api",
    docs_url="/docs",
    openapi_url="/openapi.json"
)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Supabase (Safe Mode)
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
database_url = os.getenv('DATABASE_URL')
supabase: Client = None

if supabase_url and supabase_key and supabase_key != "placeholder_need_service_key":
    try:
        supabase = create_client(supabase_url, supabase_key)
    except Exception as e:
        print(f"Warning: Failed to initialize Supabase: {e}")
else:
    print("Warning: Supabase keys not set or invalid. Running in compatibility mode.")

# Postgres Direct Connection (Fallback)
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    if not database_url:
        return None
    try:
        return psycopg2.connect(database_url)
    except Exception as e:
        print(f"Failed to connect to DB: {e}")
        return None

# Pydantic models
class ChatRequest(BaseModel):
    message: str
    max_length: int = 100
    temperature: float = 0.7

class ChatResponse(BaseModel):
    response: str
    timestamp: datetime
    tokens_used: int

@app.get("/")
async def root():
    return {
        "message": "IndraAI Serverless API",
        "version": "1.0.0",
        "status": "healthy"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow(),
        "environment": "vercel"
    }

@app.get("/model/info")
async def get_model_info():
    """Dummy model info for Vercel"""
    return {
        "model_name": "IndraAI Lite (Vercel)",
        "status": "ready",
        "version": "1.0.0"
    }

@app.post("/chat", response_model=ChatResponse)
@app.post("/chat/free", response_model=ChatResponse)
async def chat_free(request: ChatRequest):
    """Free tier chat endpoint for Vercel deployment"""
    
    # Simple response generation (replace with actual model inference)
    response_text = f"Hello! You said: '{request.message}'. This is a demo response from IndraAI serverless API."
    
    # Log usage to Supabase
    # Log usage to Supabase or Direct DB
    if supabase:
        try:
            supabase.table('api_usage').insert({
                'user_id': None,  # Anonymous for free tier
                'endpoint': '/chat/free',
                'tokens_used': len(response_text.split()),
                'created_at': datetime.utcnow().isoformat()
            }).execute()
        except Exception as e:
            print(f"Failed to log usage (Supabase): {e}")
    elif database_url:
        # Fallback to direct DB
        try:
            conn = get_db_connection()
            if conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO api_usage (endpoint, tokens_used, created_at) VALUES (%s, %s, %s)",
                        ('/chat/free', len(response_text.split()), datetime.utcnow())
                    )
                conn.commit()
                conn.close()
        except Exception as e:
            print(f"Failed to log usage (Direct DB): {e}")
    
    return ChatResponse(
        response=response_text,
        timestamp=datetime.utcnow(),
        tokens_used=len(response_text.split())
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "status": 500}
    )

@app.get("/stats")
async def get_stats():
    """Get API usage statistics"""
    try:
        # Get usage stats from Supabase
        result = supabase.table('api_usage').select('endpoint, tokens_used, created_at').execute()
        
        total_requests = len(result.data) if result.data else 0
        total_tokens = sum(item['tokens_used'] for item in result.data) if result.data else 0
        
        return {
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Export for Vercel
handler = app
