# Vercel serverless function for IndraAI API
import os
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
import redis

# Initialize FastAPI
app = FastAPI(title="IndraAI Serverless API", version="1.0.0")

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Supabase
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
supabase: Client = create_client(supabase_url, supabase_key)

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

@app.post("/chat/free", response_model=ChatResponse)
async def chat_free(request: ChatRequest):
    """Free tier chat endpoint for Vercel deployment"""
    
    # Simple response generation (replace with actual model inference)
    response_text = f"Hello! You said: '{request.message}'. This is a demo response from IndraAI serverless API."
    
    # Log usage to Supabase
    try:
        supabase.table('api_usage').insert({
            'user_id': None,  # Anonymous for free tier
            'endpoint': '/chat/free',
            'tokens_used': len(response_text.split()),
            'created_at': datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        print(f"Failed to log usage: {e}")
    
    return ChatResponse(
        response=response_text,
        timestamp=datetime.utcnow(),
        tokens_used=len(response_text.split())
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
