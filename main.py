"""
Saga Backend API - Main entry point for frontend
Handles file storage + proxies to Graph API for Neo4j/LLM
"""
import os
import json
import logging
import requests
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:     %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Import storage managers
from src.storage.user_manager import UserManager
from src.storage.article_manager import ArticleStorageManager
from src.storage.strategy_manager import StrategyStorageManager

# Import API routers
from src.api.routes import articles, admin, strategies

# Initialize managers
user_manager = UserManager()
article_manager = ArticleStorageManager()
strategy_manager = StrategyStorageManager()

# Graph API URL
GRAPH_API_URL = os.getenv("GRAPH_API_URL", "http://localhost:8001")

# Initialize FastAPI
app = FastAPI(
    title="Saga Backend API",
    description="Main API for frontend - handles storage + proxies to Graph API",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"📥 {request.method} {request.url.path}")
    logger.info(f"   Cookies: {dict(request.cookies)}")
    response = await call_next(request)
    logger.info(f"📤 Status: {response.status_code}")
    return response

# Include routers
app.include_router(articles.router)
app.include_router(admin.router)
app.include_router(strategies.router)

# Models
class LoginRequest(BaseModel):
    username: str
    password: str

class ChatRequest(BaseModel):
    message: str
    history: List[Dict[str, str]] = []
    topic_id: Optional[str] = None
    strategy_id: Optional[str] = None
    username: Optional[str] = None


# ============ AUTH & USERS ============
@app.post("/api/login")
def login(request: LoginRequest, response: Response):
    """Authenticate user"""
    user = user_manager.authenticate(request.username, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Generate session token (simple: username + timestamp hash)
    import hashlib
    import time
    session_token = hashlib.sha256(f"{user['username']}{time.time()}".encode()).hexdigest()
    
    # Set secure HTTP-only cookie
    response.set_cookie(
        key="session_token",
        value=session_token,
        path="/",
        httponly=True,
        max_age=86400,  # 24 hours
        samesite="lax"
    )
    
    # Store session in memory (simple dict for now)
    if not hasattr(app.state, 'sessions'):
        app.state.sessions = {}
    app.state.sessions[session_token] = user['username']
    
    return user


@app.get("/api/users")
def list_users():
    """Get all users (for saga-graph to iterate over)"""
    usernames = user_manager.list_users()
    return {"users": [{"username": u} for u in usernames]}


# ============ INTERESTS ============
@app.get("/api/topics/all")
def get_all_topics():
    """Get all topics from Neo4j - for debugging"""
    try:
        response = requests.get(
            f"{GRAPH_API_URL}/neo/topics/all",
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")


@app.get("/api/interests")
def get_interests(username: str = Query(...)):
    """Get user's accessible topics with names from Neo4j"""
    user = user_manager.get_user(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    topic_ids = user["accessible_topics"]
    
    # Call Graph API to get topic names
    try:
        response = requests.get(
            f"{GRAPH_API_URL}/neo/topic-names",
            params={"topic_ids": ",".join(topic_ids)},
            timeout=10
        )
        response.raise_for_status()
        topic_names = response.json()
    except Exception as e:
        # Fallback if Graph API unavailable
        topic_names = {tid: tid for tid in topic_ids}
    
    interests = [
        {"id": tid, "name": topic_names.get(tid, tid)}
        for tid in topic_ids
    ]
    
    return {"interests": interests}


# ============ ARTICLES ============
# Article routes moved to src/api/routes/articles.py router
# Router includes: POST /articles/ingest, GET /articles/{id}, POST /articles/search


# ============ STRATEGIES ============
# Strategy endpoints moved to src/api/routes/strategies.py
# All strategy CRUD operations now use resource-based REST API:
#   POST   /api/users/{username}/strategies                              # Create
#   GET    /api/users/{username}/strategies                              # List
#   GET    /api/users/{username}/strategies/{strategy_id}                # Get
#   PUT    /api/users/{username}/strategies/{strategy_id}                # Update
#   DELETE /api/users/{username}/strategies/{strategy_id}                # Delete (archive)
#   POST   /api/users/{username}/strategies/{strategy_id}/topics         # Save topics
#   GET    /api/users/{username}/strategies/{strategy_id}/topics         # Get topics
#   POST   /api/users/{username}/strategies/{strategy_id}/analysis       # Save analysis
#   GET    /api/users/{username}/strategies/{strategy_id}/analysis       # Get latest analysis
#   GET    /api/users/{username}/strategies/{strategy_id}/analysis/history  # Get history
#   POST   /api/users/{username}/strategies/{strategy_id}/question       # Save question
#   GET    /api/users/{username}/strategies/{strategy_id}/question       # Get question


# ============ REPORTS ============
@app.get("/api/reports/{topic_id}")
def get_report(topic_id: str):
    """Get report - proxy to Graph API"""
    try:
        response = requests.get(
            f"{GRAPH_API_URL}/neo/reports/{topic_id}",
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")


# ============ CHAT ============
@app.post("/api/chat")
def chat(request: ChatRequest):
    """Chat - Backend handles ALL LLM logic with incredible prompt"""
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    
    try:
        # 1. Load strategy from files if provided
        strategy_data = None
        if request.strategy_id and request.username:
            strategy_data = strategy_manager.get_strategy(request.username, request.strategy_id)
            if not strategy_data:
                raise HTTPException(status_code=404, detail="Strategy not found")
        
        # 2. Get Neo4j context from Graph API
        neo_context = None
        if request.topic_id:
            try:
                response = requests.post(
                    f"{GRAPH_API_URL}/neo/build-context",
                    json={"topic_id": request.topic_id},
                    timeout=10
                )
                response.raise_for_status()
                neo_context = response.json()
            except Exception as e:
                print(f"Graph API context unavailable: {e}")
                # Continue without Neo4j context
        
        # 3. Build INCREDIBLE context
        context_parts = []
        
        # PART 1: Market Intelligence from Neo4j
        if neo_context and neo_context.get("topic_name"):
            context_parts.append("═══ MARKET INTELLIGENCE ═══")
            context_parts.append(f"Asset: {neo_context['topic_name']}")
            context_parts.append("")
            
            # Add recent developments
            articles = neo_context.get("articles", [])
            if articles:
                context_parts.append("◆ RECENT DEVELOPMENTS:")
                for i, article in enumerate(articles[:5], 1):
                    context_parts.append(f"{i}. {article['title']}")
                    if article.get('summary'):
                        context_parts.append(f"   {article['summary'][:200]}...")
                context_parts.append("")
            
            # Add analysis reports
            reports = neo_context.get("reports", {})
            if reports:
                context_parts.append("【ANALYSIS REPORTS】")
                for section, content in list(reports.items())[:2]:  # Top 2 sections
                    if content and content.strip():
                        section_title = section.replace('_', ' ').title()
                        content_preview = content.strip()[:400]
                        context_parts.append(f"\n{section_title}:")
                        context_parts.append(content_preview + "...")
                context_parts.append("")
        
        # PART 2: User's Trading Strategy
        if strategy_data:
            context_parts.append("═══ USER'S TRADING STRATEGY ═══")
            context_parts.append(f"Asset: {strategy_data['asset']['primary']}")
            context_parts.append("")
            context_parts.append("USER'S THESIS:")
            context_parts.append(strategy_data['user_input']['strategy_text'])
            context_parts.append("")
            
            if strategy_data['user_input'].get('position_text'):
                context_parts.append("POSITION DETAILS:")
                context_parts.append(strategy_data['user_input']['position_text'])
                context_parts.append("")
            
            if strategy_data['user_input'].get('target'):
                context_parts.append(f"TARGET: {strategy_data['user_input']['target']}")
                context_parts.append("")
            
            # Add AI analysis if exists
            if strategy_data.get('latest_analysis', {}).get('analyzed_at'):
                context_parts.append("═══ AI ANALYSIS ═══")
                analysis = strategy_data['latest_analysis']
                
                # Add executive summary
                if analysis.get('final_analysis', {}).get('executive_summary'):
                    context_parts.append(f"Executive Summary: {analysis['final_analysis']['executive_summary'][:250]}...")
                
                # Add risk summary
                if analysis.get('risk_assessment', {}).get('key_risk_summary'):
                    context_parts.append(f"Key Risks: {analysis['risk_assessment']['key_risk_summary'][:200]}...")
                
                # Add opportunity summary
                if analysis.get('opportunity_assessment', {}).get('key_opportunity_summary'):
                    context_parts.append(f"Key Opportunities: {analysis['opportunity_assessment']['key_opportunity_summary'][:200]}...")
                
                context_parts.append("")
        
        full_context = "\n".join(context_parts) if context_parts else ""
        
        # Determine context type
        if request.strategy_id and request.topic_id:
            context_type = "strategy + market intelligence"
        elif request.strategy_id:
            context_type = "user's trading strategy"
        elif request.topic_id:
            context_type = "market intelligence"
        else:
            context_type = "general financial knowledge"
        
        # 4. Build chat history
        messages = []
        for msg in request.history:
            if msg.get("role") == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg.get("role") == "assistant":
                messages.append(AIMessage(content=msg["content"]))
        
        messages.append(HumanMessage(content=request.message))
        
        # 5. THE INCREDIBLE PROMPT
        system_prompt = f"""You are Argos, an elite financial intelligence analyst delivering razor-sharp insights.

═══ MISSION ═══
Transform complex financial questions into concise, actionable intelligence. Maximum 150 words.

═══ CONTEXT TYPE ═══
{context_type}

{full_context}

═══ RESPONSE FRAMEWORK ═══
**Answer:** [Direct 2-3 sentence response]

**Key Insight:** [Most critical non-obvious factor]

**Risk/Opportunity:** [What could go wrong/right]

**Next:** [Strategic question to advance discussion]

═══ RULES ═══
• BREVITY IS INTELLIGENCE: Max 150 words total
• SPECIFICITY: Use exact numbers, dates, probabilities
• Contrarian Edge: Challenge consensus where evidence supports
• ACTIONABLE ONLY: Every sentence drives decisions
• CONVERSATION LEADERSHIP: End with strategic question

Question: "{request.message}"

Deliver maximum insight density. Every word must earn its place."""
        
        # 6. Call LLM (Anthropic Claude)
        llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            temperature=0.2,
            max_tokens=300,
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        
        # Claude requires system message to be separate
        messages_with_system = [SystemMessage(content=system_prompt)] + messages
        response = llm.invoke(messages_with_system)
        reply = response.content if hasattr(response, 'content') else str(response)
        
        return {
            "response": reply.strip(),
            "topic_id": request.topic_id,
            "strategy_id": request.strategy_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


# ============ HEALTH ============
@app.get("/")
def root():
    return {"status": "online", "service": "Saga Backend API", "version": "1.0.0"}


@app.get("/health")
def health():
    graph_status = "unknown"
    try:
        response = requests.get(f"{GRAPH_API_URL}/neo/health", timeout=5)
        graph_status = "connected" if response.status_code == 200 else "error"
    except:
        graph_status = "unavailable"
    
    return {
        "status": "healthy",
        "graph_api": graph_status,
        "graph_url": GRAPH_API_URL
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    print(f"\n🚀 Saga Backend API starting on port {port}")
    print(f"📚 Docs: http://localhost:{port}/docs")
    print(f"🔗 Graph API: {GRAPH_API_URL}\n")
    uvicorn.run(app, host="0.0.0.0", port=port)
