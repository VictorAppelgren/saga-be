"""
Saga Backend API - Main entry point for frontend
Handles file storage + proxies to Graph API for Neo4j/LLM
"""
import os
import json
import logging
import requests
from datetime import datetime
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
from src.storage.conversations import conversation_store
from src.storage.session_manager import session_manager
from src.models.conversation import Message, MessageRole

# Import API routers
from src.api.routes import articles, admin, strategies, stats

# Import stats tracking (same as stats router but as a sync helper)
from datetime import date as date_helper
from pathlib import Path
import json as json_helper

def track_event(event_type: str, message: str = None):
    """Track a stat event (sync helper for backend routes)."""
    try:
        today = date_helper.today().isoformat()
        stats_dir = Path("stats/stats")
        stats_dir.mkdir(parents=True, exist_ok=True)
        stats_file = stats_dir / f"stats_{today}.json"

        if stats_file.exists():
            stats_data = json_helper.loads(stats_file.read_text())
        else:
            stats_data = {"date": today, "events": {}}

        stats_data["events"][event_type] = stats_data["events"].get(event_type, 0) + 1
        stats_file.write_text(json_helper.dumps(stats_data, indent=2))
    except Exception as e:
        logger.warning(f"Stats tracking failed: {e}")

# Initialize managers
user_manager = UserManager()
article_manager = ArticleStorageManager()
strategy_manager = StrategyStorageManager()

# Graph API URL
GRAPH_API_URL = os.getenv("GRAPH_API_URL", "http://localhost:8001")

# Anthropic API Key (for chat)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

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

class ContactFormRequest(BaseModel):
    name: str
    email: str
    company: str
    message: str = ""

class ChatRequest(BaseModel):
    message: str
    topic_id: Optional[str] = None
    strategy_id: Optional[str] = None
    username: Optional[str] = None
    test: bool = False  # If True, return full context for debugging


# ============ AUTH & USERS ============
@app.post("/api/login")
def login(request: LoginRequest, response: Response):
    """Authenticate user and create session"""
    user = user_manager.authenticate(request.username, request.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Track user session
    track_event("user_session_started", request.username)

    # Create persistent session (24h TTL)
    session_token = session_manager.create_session(user['username'], ttl_hours=24)

    # Set secure HTTP-only cookie
    response.set_cookie(
        key="session_token",
        value=session_token,
        path="/",
        httponly=True,
        max_age=86400,  # 24 hours
        samesite="lax"
    )

    return user


@app.post("/api/logout")
def logout(request: Request, response: Response):
    """Invalidate session and clear cookie"""
    token = request.cookies.get("session_token")
    if token:
        session_manager.invalidate_session(token)

    # Clear the cookie
    response.delete_cookie(key="session_token", path="/")
    return {"success": True}


@app.get("/api/validate-session")
def validate_session(request: Request):
    """
    Validate session token from cookie.
    Used by nginx auth_request - returns 200 if valid, 401 if invalid.
    This endpoint is called by nginx BEFORE proxying to other /api/ routes.
    """
    token = request.cookies.get("session_token")

    # Also check X-API-Key for worker requests (they bypass session auth)
    api_key = request.headers.get("X-API-Key")
    if api_key:
        # API key validation is handled by nginx map, but double-check here
        # If request has API key and reached here, nginx already validated it
        return Response(status_code=200)

    # Validate session token
    username = session_manager.validate_session(token)
    if username:
        return Response(
            status_code=200,
            headers={"X-Auth-User": username}  # Pass username to upstream
        )

    return Response(status_code=401)


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
    # Track report view
    track_event("report_viewed", topic_id)

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


def _build_full_context(request: ChatRequest, strategy_data: dict = None) -> tuple:
    """Build context from Neo4j and strategy. Returns (context_str, context_type)."""
    context_parts = []

    # Get Neo4j context if topic provided
    neo_context = None
    if request.topic_id:
        try:
            response = requests.post(
                f"{GRAPH_API_URL}/neo/build-context",
                json={
                    "topic_id": request.topic_id,
                    "include_full_articles": True,
                    "include_related_topics": True,
                    "max_articles": 15
                },
                timeout=15
            )
            response.raise_for_status()
            neo_context = response.json()
        except Exception as e:
            logger.warning(f"Graph API context unavailable: {e}")

    # PART 1: Market Intelligence from Neo4j
    if neo_context and neo_context.get("topic_name"):
        context_parts.append("═══ PRIMARY ASSET INTELLIGENCE ═══")
        context_parts.append(f"Asset: {neo_context['topic_name']}\n")

        reports = neo_context.get("reports", {})
        if reports:
            context_parts.append("【COMPLETE ANALYSIS】")
            for section in ["executive_summary", "market_dynamics", "risk_factors", "opportunity_assessment", "recent_developments"]:
                content = reports.get(section, "")
                if content and content.strip():
                    context_parts.append(f"\n{section.replace('_', ' ').title()}:")
                    context_parts.append(content.strip())
            context_parts.append("")

        articles = neo_context.get("articles", [])
        if articles:
            context_parts.append("◆ RECENT DEVELOPMENTS:")
            for i, article in enumerate(articles[:10], 1):
                context_parts.append(f"\n[Article {i}] {article.get('title', 'Untitled')}")
                context_parts.append(f"Source: {article.get('source', 'Unknown')} | {article.get('published_at', 'N/A')}")
                if article.get('content'):
                    context_parts.append(f"Content: {article['content'][:800]}...")
                if article.get('motivation'):
                    context_parts.append(f"Why Relevant: {article['motivation']}")
            context_parts.append("")

        related_topics = neo_context.get("related_topics", [])
        if related_topics:
            context_parts.append("【RELATED ASSETS】")
            for rel in related_topics:
                context_parts.append(f"• {rel['name']} ({rel['relationship']}): {rel.get('executive_summary', '')[:200]}")
            context_parts.append("")

    # PART 2: User's Trading Strategy
    if strategy_data:
        context_parts.append("═══ USER'S TRADING STRATEGY ═══")
        context_parts.append(f"Primary Asset: {strategy_data['asset']['primary']}")
        if strategy_data['asset'].get('related'):
            context_parts.append(f"Related: {', '.join(strategy_data['asset']['related'])}")
        context_parts.append(f"\nTHESIS: {strategy_data['user_input']['strategy_text']}")
        if strategy_data['user_input'].get('position_text'):
            context_parts.append(f"POSITION: {strategy_data['user_input']['position_text']}")
        if strategy_data['user_input'].get('target'):
            context_parts.append(f"TARGET: {strategy_data['user_input']['target']}")

        analysis = strategy_data.get('latest_analysis', {})
        if analysis.get('analyzed_at'):
            if analysis.get('final_analysis', {}).get('executive_summary'):
                context_parts.append(f"\nAI Summary: {analysis['final_analysis']['executive_summary']}")
            if analysis.get('risk_assessment', {}).get('key_risk_summary'):
                context_parts.append(f"Risks: {analysis['risk_assessment']['key_risk_summary']}")
            if analysis.get('opportunity_assessment', {}).get('key_opportunity_summary'):
                context_parts.append(f"Opportunities: {analysis['opportunity_assessment']['key_opportunity_summary']}")
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

    return full_context, context_type


@app.post("/api/chat")
def chat(request: ChatRequest):
    """Agentic chat with backend conversation state. Context built once per day."""
    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

    try:
        username = request.username or "anonymous"

        # 1. Get or create today's conversation
        conv, is_new = conversation_store.get_or_create(
            username=username,
            topic_id=request.topic_id,
            strategy_id=request.strategy_id
        )

        # 2. Load strategy if provided
        strategy_data = None
        if request.strategy_id and request.username:
            strategy_data = strategy_manager.get_strategy(request.username, request.strategy_id)
            if not strategy_data:
                raise HTTPException(status_code=404, detail="Strategy not found")

        # 3. If new conversation, build context ONCE
        if is_new:
            full_context, context_type = _build_full_context(request, strategy_data)

            system_prompt = f"""You are Saga—an elite financial intelligence analyst with access to live news search.

═══ AVAILABLE TOOL ═══
You have ONE tool: search_news
- Use it when you need current market information not in your context
- Use it when user asks about "latest", "recent", "current", "today", "news"
- You can call it multiple times with different queries if needed

═══ CONTEXT ═══
Type: {context_type}

{full_context if full_context else "No pre-loaded context. Use search_news tool if you need current information."}

═══ RESPONSE STYLE ═══
- **Answer**: Direct 2-3 sentence response with causal chain
- **Key Insight**: Most critical non-obvious factor
- **Risk/Opportunity**: What could go wrong/right
- Cite sources: [News 1], [Article 2], etc.
- Max 150 words in final response
- End with a strategic follow-up question"""

            conv.messages.append(Message(
                role=MessageRole.CONTEXT,
                content=system_prompt,
                timestamp=datetime.now()
            ))

        # 4. Add user message
        conv.messages.append(Message(
            role=MessageRole.USER,
            content=request.message,
            timestamp=datetime.now()
        ))

        # 5. Test mode - return context without calling LLM
        if request.test:
            conversation_store.save(conv)
            return {
                "test_mode": True,
                "conversation_id": conv.id,
                "is_new_conversation": is_new,
                "messages": conv.get_visible_messages(limit=10)
            }

        # 6. Build LLM messages from conversation history
        llm_messages = []
        for msg in conv.messages:
            if msg.role == MessageRole.CONTEXT:
                llm_messages.append(SystemMessage(content=msg.content))
            elif msg.role == MessageRole.SEARCH:
                llm_messages.append(HumanMessage(content=f"[Previous search results]\n{msg.content}"))
            elif msg.role == MessageRole.USER:
                llm_messages.append(HumanMessage(content=msg.content))
            elif msg.role == MessageRole.ASSISTANT:
                llm_messages.append(AIMessage(content=msg.content))

        # 7. Define tool
        tools = [{
            "name": "search_news",
            "description": "Search recent news articles (past 14 days). Use when you need current information.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query as a statement, not a question"}
                },
                "required": ["query"]
            }
        }]

        # 8. Agentic loop
        if not ANTHROPIC_API_KEY:
            raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")
        llm = ChatAnthropic(model="claude-sonnet-4-5-20250929", temperature=0.7, api_key=ANTHROPIC_API_KEY)
        search_results = []

        for _ in range(5):  # Max iterations
            response = llm.invoke(llm_messages, tools=tools)

            if response.tool_calls:
                for tool_call in response.tool_calls:
                    if tool_call["name"] == "search_news":
                        query = tool_call["args"].get("query", request.message)
                        logger.info(f"Agent searching: {query[:50]}...")

                        tool_result = _execute_news_search(query)
                        search_results.append({"query": query, "result": tool_result})

                        llm_messages.append(response)
                        llm_messages.append(ToolMessage(content=tool_result, tool_call_id=tool_call["id"]))
                continue
            else:
                break

        # 9. Store search results as hidden messages (for future context)
        for sr in search_results:
            conv.messages.append(Message(
                role=MessageRole.SEARCH,
                content=f"[Search: {sr['query']}]\n{sr['result']}",
                timestamp=datetime.now()
            ))

        # 10. Store assistant response
        response_text = response.content if hasattr(response, 'content') else "I encountered an issue."
        conv.messages.append(Message(
            role=MessageRole.ASSISTANT,
            content=response_text,
            timestamp=datetime.now()
        ))

        # 11. Save conversation
        conversation_store.save(conv)

        # 12. Return response + visible messages
        return {
            "response": response_text,
            "conversation_id": conv.id,
            "messages": conv.get_visible_messages(limit=10)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}")
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
        rewrite_context_msg = f"[I just updated the {section_title} section based on: '{request.feedback}'. Briefly confirm what was changed in 1-2 sentences, starting with ✅]"

        chat_request = ChatRequest(
            message=rewrite_context_msg,
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


# ============ CONTACT FORM ============
CONTACTS_FILE = os.path.join(os.path.dirname(__file__), "data", "contacts.json")
NTFY_TOPIC = os.getenv("NTFY_TOPIC", "")  # e.g., "saga-leads"


def _send_ntfy_ping():
    """Send a privacy-safe ping notification (no PII)"""
    if not NTFY_TOPIC:
        return
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data="New lead received - check admin panel".encode("utf-8"),
            headers={"Title": "Saga: New Lead", "Priority": "high", "Tags": "briefcase"},
            timeout=5
        )
        logger.info(f"📱 Ntfy ping sent to {NTFY_TOPIC}")
    except Exception as e:
        logger.warning(f"Ntfy ping failed: {e}")


def _load_contacts() -> list:
    """Load contacts from disk"""
    if os.path.exists(CONTACTS_FILE):
        with open(CONTACTS_FILE, "r") as f:
            return json.load(f)
    return []


def _save_contacts(contacts: list):
    """Save contacts to disk"""
    os.makedirs(os.path.dirname(CONTACTS_FILE), exist_ok=True)
    with open(CONTACTS_FILE, "w") as f:
        json.dump(contacts, f, indent=2)


@app.post("/api/contact")
def submit_contact(request: ContactFormRequest):
    """Save contact form submission to disk"""
    try:
        contact = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S"),
            "name": request.name,
            "email": request.email,
            "company": request.company,
            "message": request.message,
            "submitted_at": datetime.now().isoformat(),
            "status": "new"
        }

        contacts = _load_contacts()
        contacts.append(contact)
        _save_contacts(contacts)

        logger.info(f"📬 New contact: {request.name} ({request.email}) from {request.company}")

        # Send privacy-safe ntfy ping (no PII in notification)
        _send_ntfy_ping()

        return {"success": True, "message": "Thank you for reaching out!"}

    except Exception as e:
        logger.error(f"Contact form error: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit contact form")


@app.get("/api/admin/contacts")
def get_contacts():
    """Get all contact form submissions (admin only)"""
    contacts = _load_contacts()
    # Sort by date descending (newest first)
    contacts.sort(key=lambda x: x.get("submitted_at", ""), reverse=True)

    # Count by status
    new_count = sum(1 for c in contacts if c.get("status") == "new")

    return {
        "contacts": contacts,
        "total": len(contacts),
        "new": new_count
    }


@app.patch("/api/admin/contacts/{contact_id}")
def update_contact_status(contact_id: str, status: str = Query(...)):
    """Update contact status (e.g., 'new' -> 'contacted' -> 'closed')"""
    contacts = _load_contacts()

    for contact in contacts:
        if contact.get("id") == contact_id:
            contact["status"] = status
            contact["updated_at"] = datetime.now().isoformat()
            _save_contacts(contacts)
            return {"success": True, "contact": contact}

    raise HTTPException(status_code=404, detail="Contact not found")


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
