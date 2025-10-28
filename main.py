"""
Saga Backend API - Main entry point for frontend
Handles file storage + proxies to Graph API for Neo4j/LLM
"""
import os
import json
import requests
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Load environment variables
load_dotenv()

# Import storage managers
from src.storage.user_manager import UserManager
from src.storage.article_manager import ArticleStorageManager
from src.storage.strategy_manager import StrategyStorageManager

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

class CreateStrategyRequest(BaseModel):
    username: str
    asset_primary: str
    strategy_text: str
    position_text: str = ""
    target: str = ""


# ============ AUTH & USERS ============
@app.post("/login")
def login(request: LoginRequest):
    """Authenticate user"""
    user = user_manager.authenticate(request.username, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return user


@app.get("/users")
def list_users():
    """Get all users (for saga-graph to iterate over)"""
    usernames = user_manager.list_users()
    return {"users": [{"username": u} for u in usernames]}


# ============ INTERESTS ============
@app.get("/topics/all")
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


@app.get("/interests")
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
@app.post("/articles")
def store_article(article: Dict[str, Any]):
    """Store article to files"""
    argos_id = article_manager.store_article(article)
    return {"argos_id": argos_id, "status": "stored"}


@app.get("/articles/{article_id}")
def get_article(article_id: str):
    """Get article from files"""
    article = article_manager.get_article(article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@app.get("/articles")
def get_articles_for_topic(topic_id: str = Query(...)):
    """Get articles for topic - queries Neo4j then loads from files"""
    # Call Graph API to get article IDs from Neo4j
    try:
        response = requests.get(
            f"{GRAPH_API_URL}/neo/query-articles",
            params={"topic_id": topic_id},
            timeout=10
        )
        response.raise_for_status()
        article_ids = response.json()["article_ids"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph API error: {str(e)}")
    
    # Load full articles from files
    articles = []
    for article_id in article_ids:
        article = article_manager.get_article(article_id)
        if article:
            articles.append(article)
    
    return {"articles": articles}


# ============ STRATEGIES ============
@app.get("/strategies")
def list_strategies(username: str = Query(...)):
    """List user's strategies"""
    strategies = strategy_manager.list_strategies(username)
    return {"strategies": strategies}


@app.get("/strategies/{strategy_id}")
def get_strategy(strategy_id: str, username: str = Query(...)):
    """Get strategy details"""
    strategy = strategy_manager.get_strategy(username, strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strategy


@app.post("/strategies")
def create_strategy(request: CreateStrategyRequest):
    """Create new strategy"""
    from datetime import datetime
    
    strategy_id = f"strategy_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    strategy = {
        "id": strategy_id,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "version": 1,
        "asset": {"primary": request.asset_primary},
        "user_input": {
            "strategy_text": request.strategy_text,
            "position_text": request.position_text,
            "target": request.target
        },
        "analysis": {"generated_at": None}
    }
    
    strategy_manager.save_strategy(request.username, strategy)
    return strategy


@app.put("/strategies/{strategy_id}")
def update_strategy(strategy_id: str, strategy: Dict[str, Any]):
    """Update strategy"""
    username = strategy.get("username")
    if not username:
        raise HTTPException(status_code=400, detail="username required")
    
    existing = strategy_manager.get_strategy(username, strategy_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    from datetime import datetime
    strategy["updated_at"] = datetime.now().isoformat()
    strategy["version"] = existing.get("version", 1) + 1
    
    strategy_manager.save_strategy(username, strategy)
    return strategy


@app.delete("/strategies/{strategy_id}")
def delete_strategy(strategy_id: str, username: str = Query(...)):
    """Archive strategy"""
    import shutil
    from pathlib import Path
    from datetime import datetime
    
    user_dir = Path("users") / username
    strategy_path = user_dir / f"{strategy_id}.json"
    
    if not strategy_path.exists():
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    archive_dir = user_dir / "archive"
    archive_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_path = archive_dir / f"{strategy_id}_{timestamp}.json"
    shutil.move(str(strategy_path), str(archive_path))
    
    return {"message": "Strategy archived", "archived_as": archive_path.name}


# ============ REPORTS ============
@app.get("/reports/{topic_id}")
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
@app.post("/chat")
def chat(request: ChatRequest):
    """Chat - Backend handles ALL LLM logic with incredible prompt"""
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, AIMessage
    
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
            if strategy_data.get('analysis', {}).get('generated_at'):
                context_parts.append("═══ AI ANALYSIS ═══")
                analysis = strategy_data['analysis']
                if analysis.get('fundamental'):
                    context_parts.append(f"Fundamental: {analysis['fundamental'][:250]}...")
                if analysis.get('risks'):
                    context_parts.append(f"Risks: {analysis['risks'][:200]}...")
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
        
        # 6. Call LLM (OpenAI)
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.2,
            max_tokens=300,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        response = llm.invoke(system_prompt)
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
