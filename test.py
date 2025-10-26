"""
Comprehensive Frontend Simulation Test Suite
Tests all Backend API endpoints as if called from the frontend
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def print_section(title):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}")

def print_result(endpoint, status, data=None):
    emoji = "✅" if status < 400 else "❌"
    print(f"{emoji} {endpoint} - Status: {status}")
    if data:
        print(f"   Response: {json.dumps(data, indent=2)[:200]}...")

# ============ TEST SUITE ============

def test_health():
    """Test 1: Health Check"""
    print_section("TEST 1: Health & Status")
    
    # Root endpoint
    r = requests.get(f"{BASE_URL}/")
    print_result("GET /", r.status_code, r.json())
    
    # Health endpoint
    r = requests.get(f"{BASE_URL}/health")
    print_result("GET /health", r.status_code, r.json())


def test_authentication():
    """Test 2: User Authentication"""
    print_section("TEST 2: Authentication")
    
    # Valid login
    r = requests.post(f"{BASE_URL}/login", json={
        "username": "Victor",
        "password": "v123"
    })
    print_result("POST /login (valid)", r.status_code, r.json())
    
    # Invalid login
    r = requests.post(f"{BASE_URL}/login", json={
        "username": "Victor",
        "password": "wrong"
    })
    print_result("POST /login (invalid)", r.status_code)
    
    return "Victor"


def test_interests(username):
    """Test 3: Get User Interests"""
    print_section("TEST 3: User Interests (with Graph API)")
    
    # First, get ALL topics to see what's available
    print("\n   Getting ALL topics from Neo4j...")
    try:
        r = requests.get(f"{BASE_URL}/topics/all", timeout=5)
        if r.status_code == 200:
            all_topics = r.json()
            print(f"\n   📊 COMPLETE TOPIC LIST FROM NEO4J:")
            print(f"   Total in database: {all_topics.get('total_in_db', 'unknown')}")
            print(f"   Showing all: {all_topics.get('showing_all', 'unknown')}")
            print(f"   Count returned: {all_topics['count']}")
            print(f"\n   {'='*80}")
            
            # Show ALL topics
            for i, topic in enumerate(all_topics['topics'], 1):
                importance = topic.get('importance', 0)
                category = topic.get('category', '')
                cat_str = f" [{category}]" if category else ""
                print(f"   {i:3d}. {topic['id']:30s} → {topic['name']}{cat_str} (importance: {importance})")
            
            print(f"   {'='*80}\n")
    except Exception as e:
        print(f"   ⚠️  Could not get all topics: {e}")
    
    print(f"\n   Getting interests for user {username}...")
    r = requests.get(f"{BASE_URL}/interests", params={"username": username})
    print_result(f"GET /interests?username={username}", r.status_code, r.json())
    
    if r.status_code == 200:
        interests = r.json()["interests"]
        print(f"   Found {len(interests)} interests")
        for interest in interests[:3]:
            print(f"   - {interest['id']}: {interest['name']}")
        return interests[0]["id"] if interests else None
    return None


def test_articles(topic_id):
    """Test 4: Article Operations"""
    print_section("TEST 4: Articles")
    
    # Store article
    article_data = {
        "argos_id": f"test_article_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "data": {
            "title": "Test Article - Brent Crude Analysis",
            "content": "This is a test article about Brent crude oil prices...",
            "source": {"domain": "test-news.com"},
            "pubDate": datetime.now().isoformat(),
            "argos_summary": "Test summary of the article"
        }
    }
    
    r = requests.post(f"{BASE_URL}/api/articles", json=article_data)
    print_result("POST /api/articles", r.status_code, r.json())
    stored_id = r.json().get("argos_id")
    
    # Get article by ID
    if stored_id:
        r = requests.get(f"{BASE_URL}/api/articles/{stored_id}")
        print_result(f"GET /api/articles/{stored_id}", r.status_code)
        if r.status_code == 200:
            article = r.json()
            print(f"   Title: {article.get('data', {}).get('title', 'N/A')}")
    
    # Get articles for topic (requires Graph API)
    if topic_id:
        print(f"\n   Testing GET /articles?topic_id={topic_id}")
        print(f"   (Requires Graph API to be running on port 8001)")
        try:
            r = requests.get(f"{BASE_URL}/articles", params={"topic_id": topic_id}, timeout=5)
            print_result(f"GET /articles?topic_id={topic_id}", r.status_code)
            if r.status_code == 200:
                articles = r.json()["articles"]
                print(f"   Found {len(articles)} articles")
        except requests.exceptions.Timeout:
            print("   ⚠️  Timeout - Graph API may not be running")
        except Exception as e:
            print(f"   ⚠️  Error: {str(e)}")


def test_strategies(username):
    """Test 5: Strategy Operations"""
    print_section("TEST 5: Strategies")
    
    # List strategies
    r = requests.get(f"{BASE_URL}/strategies", params={"username": username})
    print_result(f"GET /strategies?username={username}", r.status_code, r.json())
    
    existing_strategies = r.json().get("strategies", [])
    print(f"   Found {len(existing_strategies)} existing strategies")
    
    # Create new strategy
    r = requests.post(f"{BASE_URL}/strategies", json={
        "username": username,
        "asset_primary": "brent",
        "strategy_text": "Bullish on Brent due to supply constraints",
        "position_text": "Long 100 barrels @ $85",
        "target": "$95"
    })
    print_result("POST /strategies", r.status_code, r.json())
    
    if r.status_code == 200:
        new_strategy = r.json()
        strategy_id = new_strategy["id"]
        print(f"   Created strategy: {strategy_id}")
        
        # Get strategy
        r = requests.get(f"{BASE_URL}/strategies/{strategy_id}", params={"username": username})
        print_result(f"GET /strategies/{strategy_id}", r.status_code)
        
        # Update strategy
        new_strategy["user_input"]["target"] = "$100"
        r = requests.put(f"{BASE_URL}/strategies/{strategy_id}", json=new_strategy)
        print_result(f"PUT /strategies/{strategy_id}", r.status_code)
        
        # Delete strategy
        r = requests.delete(f"{BASE_URL}/strategies/{strategy_id}", params={"username": username})
        print_result(f"DELETE /strategies/{strategy_id}", r.status_code, r.json())
        
        return strategy_id
    
    return None


def test_reports(topic_id):
    """Test 6: Reports (requires Graph API)"""
    print_section("TEST 6: Reports (requires Graph API)")
    
    if not topic_id:
        print("   ⚠️  No topic_id available, skipping")
        return
    
    print(f"   Testing GET /reports/{topic_id}")
    print(f"   (Requires Graph API to be running on port 8001)")
    
    try:
        r = requests.get(f"{BASE_URL}/reports/{topic_id}", timeout=10)
        print_result(f"GET /reports/{topic_id}", r.status_code)
        if r.status_code == 200:
            report = r.json()
            print(f"   Topic: {report.get('topic_name', 'N/A')}")
            print(f"   Markdown length: {len(report.get('markdown', ''))} chars")
    except requests.exceptions.Timeout:
        print("   ⚠️  Timeout - Graph API may not be running")
    except Exception as e:
        print(f"   ⚠️  Error: {str(e)}")


def test_chat(topic_id, username):
    """Test 7: Chat (requires Graph API)"""
    print_section("TEST 7: Chat with LLM (requires Graph API)")
    
    print(f"   Testing POST /chat")
    print(f"   (Requires Graph API to be running on port 8001)")
    
    # Chat without strategy
    try:
        r = requests.post(f"{BASE_URL}/chat", json={
            "message": "What's the current outlook for Brent crude?",
            "topic_id": topic_id,
            "history": []
        }, timeout=15)
        print_result("POST /chat (topic only)", r.status_code)
        if r.status_code == 200:
            response = r.json()
            print(f"   Response preview: {response.get('response', '')[:100]}...")
    except requests.exceptions.Timeout:
        print("   ⚠️  Timeout - Graph API may not be running")
    except Exception as e:
        print(f"   ⚠️  Error: {str(e)}")
    
    # Chat with strategy (if exists)
    strategies_r = requests.get(f"{BASE_URL}/strategies", params={"username": username})
    if strategies_r.status_code == 200:
        strategies = strategies_r.json().get("strategies", [])
        if strategies:
            strategy_id = strategies[0]["id"]
            try:
                r = requests.post(f"{BASE_URL}/chat", json={
                    "message": "How does this align with my strategy?",
                    "topic_id": topic_id,
                    "strategy_id": strategy_id,
                    "username": username,
                    "history": []
                }, timeout=15)
                print_result("POST /chat (topic + strategy)", r.status_code)
            except Exception as e:
                print(f"   ⚠️  Error: {str(e)}")


def test_error_handling():
    """Test 8: Error Handling"""
    print_section("TEST 8: Error Handling")
    
    # Non-existent article
    r = requests.get(f"{BASE_URL}/api/articles/nonexistent123")
    print_result("GET /api/articles/nonexistent123", r.status_code)
    
    # Non-existent strategy
    r = requests.get(f"{BASE_URL}/strategies/nonexistent123", params={"username": "Victor"})
    print_result("GET /strategies/nonexistent123", r.status_code)
    
    # Invalid user
    r = requests.get(f"{BASE_URL}/interests", params={"username": "InvalidUser"})
    print_result("GET /interests?username=InvalidUser", r.status_code)


# ============ MAIN TEST RUNNER ============

def main():
    print("\n" + "="*80)
    print("  COMPREHENSIVE FRONTEND SIMULATION TEST SUITE")
    print("  Testing Backend API as if called from React frontend")
    print("="*80)
    print(f"\n  Backend API: {BASE_URL}")
    print(f"  Graph API: http://localhost:8001 (optional for some tests)")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Test 1: Health
        test_health()
        
        # Test 2: Authentication
        username = test_authentication()
        
        # Test 3: Interests (may need Graph API)
        topic_id = test_interests(username)
        
        # Test 4: Articles
        test_articles(topic_id)
        
        # Test 5: Strategies
        test_strategies(username)
        
        # Test 6: Reports (needs Graph API)
        test_reports(topic_id)
        
        # Test 7: Chat (needs Graph API)
        test_chat(topic_id, username)
        
        # Test 8: Error Handling
        test_error_handling()
        
        print_section("TEST SUMMARY")
        print("✅ All basic tests completed!")
        print("\nNotes:")
        print("  - Tests marked with ⚠️ require Graph API (port 8001)")
        print("  - File-based operations (auth, strategies, articles) work standalone")
        print("  - Neo4j operations (interests, reports, chat) need Graph API")
        
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Cannot connect to {BASE_URL}")
        print("   Make sure Backend API is running: python main.py")
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
