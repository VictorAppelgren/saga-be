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
from src.api.routes import articles, admin, strategies, stats

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

# Worker tracking import
from src.storage.worker_registry import update_worker

# Request logging middleware (also tracks worker headers)
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"📥 {request.method} {request.url.path}")

    # Track worker if headers present
    worker_id = request.headers.get("X-Worker-ID")
    if worker_id:
        machine = request.headers.get("X-Worker-Machine", "unknown")
        update_worker(worker_id, machine)

    response = await call_next(request)
    logger.info(f"📤 Status: {response.status_code}")
    return response

# Include routers
app.include_router(articles.router)
app.include_router(admin.router)
app.include_router(strategies.router)
app.include_router(stats.router)

# Startup: Ensure all users have directories
@app.on_event("startup")
async def startup_event():
    """Ensure all users from users.json have directories"""
    user_manager.ensure_user_directories()

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
    test: bool = False  # If True, return full context for debugging


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

def _execute_news_search(query: str) -> str:
    """Execute news search tool. Returns formatted results."""
    try:
        response = requests.post(
            f"{GRAPH_API_URL}/chat/search-news",
            json={"query": query, "max_results": 5},
            timeout=15
        )
        if response.status_code != 200:
            return "News search unavailable."

        articles = response.json().get("articles", [])
        if not articles:
            return "No recent news found for this query."

        lines = [f"Found {len(articles)} recent articles:"]
        for i, a in enumerate(articles, 1):
            lines.append(f"\n[News {i}] {a.get('title', 'N/A')}")
            lines.append(f"Source: {a.get('source', 'Unknown')} | Date: {a.get('pubDate', '')[:10]}")
            if a.get('summary'):
                lines.append(f"Summary: {a['summary'][:300]}")

        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"News search failed: {e}")
        return f"News search error: {str(e)}"


@app.post("/api/chat")
def chat(request: ChatRequest):
    """Agentic chat - LLM decides when to use tools"""
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

    try:
        # 1. Load strategy from files if provided
        strategy_data = None
        if request.strategy_id and request.username:
            strategy_data = strategy_manager.get_strategy(request.username, request.strategy_id)
            if not strategy_data:
                raise HTTPException(status_code=404, detail="Strategy not found")
        
        # 2. Get EXCEPTIONAL Neo4j context from Graph API
        neo_context = None
        if request.topic_id:
            try:
                # Request FULL context with related topics
                response = requests.post(
                    f"{GRAPH_API_URL}/neo/build-context",
                    json={
                        "topic_id": request.topic_id,
                        "include_full_articles": True,  # Get full article content
                        "include_related_topics": True,  # Get related assets
                        "max_articles": 15  # More articles for better context
                    },
                    timeout=15
                )
                response.raise_for_status()
                neo_context = response.json()
            except Exception as e:
                print(f"Graph API context unavailable: {e}")
                # Continue without Neo4j context
        
        # 3. Build EXCEPTIONAL context
        context_parts = []
        
        # PART 1: Market Intelligence from Neo4j (FULL CONTENT)
        if neo_context and neo_context.get("topic_name"):
            context_parts.append("═══ PRIMARY ASSET INTELLIGENCE ═══")
            context_parts.append(f"Asset: {neo_context['topic_name']}")
            context_parts.append("")
            
            # Add FULL analysis reports (all sections)
            reports = neo_context.get("reports", {})
            if reports:
                context_parts.append("【COMPLETE ANALYSIS】")
                # Include ALL key sections, not truncated
                priority_sections = [
                    "executive_summary",
                    "market_dynamics",
                    "risk_factors",
                    "opportunity_assessment",
                    "recent_developments"
                ]
                for section in priority_sections:
                    content = reports.get(section, "")
                    if content and content.strip():
                        section_title = section.replace('_', ' ').title()
                        context_parts.append(f"\n{section_title}:")
                        context_parts.append(content.strip())  # FULL content, no truncation
                context_parts.append("")
            
            # Add recent developments with FULL article content + SOURCE INFO
            articles = neo_context.get("articles", [])
            if articles:
                context_parts.append("◆ RECENT DEVELOPMENTS (Full Articles):")
                context_parts.append("")
                for i, article in enumerate(articles[:10], 1):  # Top 10 articles
                    # Format: [Article ID] Source - Title
                    article_id = article.get('id', 'unknown')
                    source = article.get('source', 'Unknown Source')
                    title = article.get('title', 'Untitled')
                    published = article.get('published_at', 'N/A')
                    
                    context_parts.append(f"[Article {i}] ({article_id})")
                    context_parts.append(f"Source: {source}")
                    context_parts.append(f"Title: {title}")
                    context_parts.append(f"Published: {published}")
                    
                    # Include full content if available
                    if article.get('content'):
                        context_parts.append(f"Content: {article['content'][:1000]}...")  # First 1000 chars
                    elif article.get('summary'):
                        context_parts.append(f"Summary: {article['summary']}")
                    
                    # Include LLM analysis from ABOUT relationship
                    if article.get('motivation'):
                        context_parts.append(f"Why Relevant: {article['motivation']}")
                    if article.get('implications'):
                        context_parts.append(f"Implications: {article['implications']}")
                    context_parts.append("")  # Blank line between articles
                context_parts.append("")
            
            # Add RELATED ASSETS with their executive summaries
            related_topics = neo_context.get("related_topics", [])
            if related_topics:
                context_parts.append("【RELATED ASSETS】")
                for rel in related_topics:
                    context_parts.append(f"\n• {rel['name']} ({rel['relationship']})")
                    context_parts.append(f"  {rel['executive_summary']}")
                context_parts.append("")
        
        # PART 2: User's Trading Strategy (FULL CONTEXT)
        if strategy_data:
            context_parts.append("═══ USER'S TRADING STRATEGY ═══")
            context_parts.append(f"Primary Asset: {strategy_data['asset']['primary']}")
            
            # Add related assets from strategy
            if strategy_data['asset'].get('related'):
                context_parts.append(f"Related Assets: {', '.join(strategy_data['asset']['related'])}")
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
            
            # Add COMPLETE AI analysis (not truncated)
            if strategy_data.get('latest_analysis', {}).get('analyzed_at'):
                context_parts.append("═══ COMPLETE AI ANALYSIS ═══")
                analysis = strategy_data['latest_analysis']
                
                # Add FULL executive summary
                if analysis.get('final_analysis', {}).get('executive_summary'):
                    context_parts.append(f"Executive Summary:\n{analysis['final_analysis']['executive_summary']}")
                    context_parts.append("")
                
                # Add FULL risk assessment
                if analysis.get('risk_assessment', {}).get('key_risk_summary'):
                    context_parts.append(f"Key Risks:\n{analysis['risk_assessment']['key_risk_summary']}")
                    context_parts.append("")
                
                # Add FULL opportunity assessment
                if analysis.get('opportunity_assessment', {}).get('key_opportunity_summary'):
                    context_parts.append(f"Key Opportunities:\n{analysis['opportunity_assessment']['key_opportunity_summary']}")
                    context_parts.append("")
                
                # Add mapped topics from strategy analysis
                if analysis.get('topic_mapping', {}).get('primary_topics'):
                    primary = analysis['topic_mapping']['primary_topics']
                    context_parts.append(f"Primary Topics: {', '.join(primary)}")
                if analysis.get('topic_mapping', {}).get('driver_topics'):
                    drivers = analysis['topic_mapping']['driver_topics']
                    context_parts.append(f"Driver Topics: {', '.join(drivers)}")
                context_parts.append("")
                
                # Get executive summaries for strategy-related topics
                try:
                    all_topics = []
                    if analysis.get('topic_mapping', {}).get('primary_topics'):
                        all_topics.extend(analysis['topic_mapping']['primary_topics'])
                    if analysis.get('topic_mapping', {}).get('driver_topics'):
                        all_topics.extend(analysis['topic_mapping']['driver_topics'])
                    
                    if all_topics:
                        context_parts.append("【STRATEGY-RELATED ASSETS】")
                        for topic_name in all_topics[:5]:  # Top 5
                            # Try to get executive summary for this topic
                            try:
                                # Find topic ID by name
                                topic_search = requests.get(
                                    f"{GRAPH_API_URL}/neo/topics/all",
                                    timeout=5
                                )
                                if topic_search.status_code == 200:
                                    topics = topic_search.json().get("topics", [])
                                    matching_topic = next((t for t in topics if t["name"].lower() == topic_name.lower()), None)
                                    if matching_topic:
                                        # Get executive summary
                                        topic_context = requests.post(
                                            f"{GRAPH_API_URL}/neo/build-context",
                                            json={"topic_id": matching_topic["id"]},
                                            timeout=5
                                        )
                                        if topic_context.status_code == 200:
                                            topic_data = topic_context.json()
                                            exec_summary = topic_data.get("reports", {}).get("executive_summary", "")
                                            if exec_summary:
                                                context_parts.append(f"\n• {topic_name}:")
                                                context_parts.append(f"  {exec_summary[:500]}...")  # First 500 chars
                            except:
                                pass  # Skip if can't fetch
                        context_parts.append("")
                except:
                    pass  # Skip if error
        
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

        # 5. Define tool for the agent
        tools = [
            {
                "name": "search_news",
                "description": "Search recent news articles (past 14 days) when you need current information about markets, events, or topics not covered in the provided context. Use this when: (1) user asks about recent/latest/current events, (2) you lack sufficient context to answer, (3) you need to verify or expand on information.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query - use a statement not a question. Example: 'Federal Reserve interest rate policy impact' instead of 'What is the Fed doing?'"
                        }
                    },
                    "required": ["query"]
                }
            }
        ]

        # 6. Build system prompt
        system_prompt = f"""You are Saga—an elite financial intelligence analyst with access to live news search.

═══ AVAILABLE TOOL ═══
You have ONE tool: search_news
- Use it when you need current market information not in your context
- Use it when user asks about "latest", "recent", "current", "today", "news"
- Use it when your context is insufficient to answer properly
- You can call it multiple times with different queries if needed

═══ CONTEXT ═══
Type: {context_type}

{full_context if full_context else "No pre-loaded context. Use search_news tool if you need current information."}

═══ RESPONSE STYLE ═══
After gathering information (via tool or from context):
- **Answer**: Direct 2-3 sentence response with causal chain
- **Key Insight**: Most critical non-obvious factor
- **Risk/Opportunity**: What could go wrong/right
- Cite sources: [News 1], [Article 2], etc.
- Max 150 words in final response
- End with a strategic follow-up question"""

        # 7. Call LLM with tools (agentic loop)
        if request.test:
            return {
                "test_mode": True,
                "context_type": context_type,
                "system_prompt": system_prompt,
                "full_context": full_context,
                "tools": tools,
                "message": request.message
            }

        # Initialize LLM with tools
        llm = ChatAnthropic(model="claude-sonnet-4-5-20250929", temperature=0.7)

        # Agentic loop - let LLM decide when to use tools
        current_messages = [SystemMessage(content=system_prompt)] + messages
        max_iterations = 5  # Prevent infinite loops

        for iteration in range(max_iterations):
            response = llm.invoke(current_messages, tools=tools)

            # Check if LLM wants to use a tool
            if response.tool_calls:
                # Process each tool call
                for tool_call in response.tool_calls:
                    if tool_call["name"] == "search_news":
                        query = tool_call["args"].get("query", request.message)
                        logger.info(f"Agent calling search_news: {query[:50]}...")

                        # Execute the tool
                        tool_result = _execute_news_search(query)

                        # Add assistant message with tool call
                        current_messages.append(response)

                        # Add tool result
                        current_messages.append(
                            ToolMessage(
                                content=tool_result,
                                tool_call_id=tool_call["id"]
                            )
                        )

                # Continue the loop to let LLM process tool results
                continue
            else:
                # No tool calls - LLM is ready to respond
                return {"response": response.content}

        # Fallback if max iterations reached
        return {"response": response.content if hasattr(response, 'content') else "I encountered an issue processing your request."}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


# ============ STRATEGY REWRITE ============
class RewriteSectionRequest(BaseModel):
    strategy_id: str
    section: str
    section_title: str = ""  # Human-readable title
    feedback: str
    current_content: str
    username: Optional[str] = None
    messages: list = []  # Conversation history (for chat context)


@app.post("/api/strategy/rewrite-section")
def rewrite_strategy_section(request: RewriteSectionRequest, cookies: Request = None):
    """
    Proxy rewrite request to Graph API, then use chat() to generate contextual comment.
    """
    # Get username from request or session
    username = request.username
    if not username and cookies:
        username = cookies.cookies.get("session")
    
    if not username:
        raise HTTPException(status_code=401, detail="Username required")
    
    section_title = request.section_title or request.section.replace("_", " ").title()
    
    try:
        # 1. Call graph-functions for the actual rewrite
        response = requests.post(
            f"{GRAPH_API_URL}/strategy/rewrite-section",
            json={
                "username": username,
                "strategy_id": request.strategy_id,
                "section": request.section,
                "feedback": request.feedback,
                "current_content": request.current_content,
            },
            timeout=120  # Long timeout for LLM processing
        )
        response.raise_for_status()
        result = response.json()
        new_content = result.get("new_content", "")
        
        # 2. Use existing chat() to generate contextual comment
        # Build history from messages + add context about the rewrite
        chat_history = [{"role": m.get("role", "user"), "content": m.get("content", "")} 
                        for m in request.messages[-5:]] if request.messages else []
        
        # Add the rewrite context as a system-injected user message
        rewrite_context_msg = f"[I just updated the {section_title} section based on: '{request.feedback}'. Briefly confirm what was changed in 1-2 sentences, starting with ✅]"
        
        chat_request = ChatRequest(
            message=rewrite_context_msg,
            history=chat_history,
            strategy_id=request.strategy_id,
            username=username,
        )
        
        try:
            print(f"📝 Generating comment via chat() for {section_title}...")
            chat_response = chat(chat_request)
            print(f"✅ Chat response received: {type(chat_response)}")
            comment = chat_response.get("response", f"✅ Done! I've updated the {section_title} section.")
            print(f"💬 Comment: {comment[:100]}...")
        except Exception as e:
            import traceback
            print(f"⚠️ Chat comment failed: {e}")
            print(traceback.format_exc())
            comment = f"✅ Done! I've updated the {section_title} section based on your feedback. Let me know if you'd like any other changes."
        
        return {
            "new_content": new_content,
            "comment": comment,
            "section": request.section
        }
        
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Rewrite request timed out")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rewrite failed: {str(e)}")


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
