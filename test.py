"""
Comprehensive API Test Suite
Tests all Backend API endpoints with environment variable support

Usage:
  # Local testing
  python test.py
  
  # Remote testing
  export API_BASE_URL=https://your-server.com
  export API_KEY=your-api-key
  python test.py
"""

import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API URLs from environment or use localhost
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
GRAPH_API_URL = os.getenv("GRAPH_API_URL", "http://localhost:8001")
API_KEY = os.getenv("API_KEY", "")

# Build headers with API key if provided
HEADERS = {
    "Content-Type": "application/json"
}
if API_KEY:
    HEADERS["X-API-Key"] = API_KEY


def print_section(title):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}")


def print_result(endpoint, status, data=None, show_full=False):
    emoji = "✅" if status < 400 else "❌"
    print(f"{emoji} {endpoint} - Status: {status}")
    if data:
        if show_full:
            print(f"   Full Response:")
            print(json.dumps(data, indent=2))
        else:
            preview = json.dumps(data, indent=2)
            if len(preview) > 300:
                print(f"   Response: {preview[:300]}...")
            else:
                print(f"   Response: {preview}")


# ============ TEST SUITE ============

def test_health():
    """Test 1: Health Check"""
    print_section("TEST 1: Health & Status")
    
    # Root endpoint
    try:
        r = requests.get(f"{BASE_URL}/", headers=HEADERS, timeout=5)
        try:
            print_result("GET /", r.status_code, r.json())
        except:
            print_result("GET /", r.status_code, {"response": r.text[:200]})
    except Exception as e:
        print(f"❌ GET / - Error: {e}")
    
    # Health endpoint
    try:
        r = requests.get(f"{BASE_URL}/health", headers=HEADERS, timeout=5)
        try:
            print_result("GET /health", r.status_code, r.json())
        except:
            print_result("GET /health", r.status_code, {"response": r.text[:200]})
    except Exception as e:
        print(f"❌ GET /health - Error: {e}")
    
    # Graph API health (optional)
    try:
        r = requests.get(f"{GRAPH_API_URL}/neo/health", headers=HEADERS, timeout=2)
        print_result("GET /neo/health (Graph API)", r.status_code, r.json())
    except:
        print("   ⚠️  Graph API not available (optional)")


def test_authentication():
    """Test 2: User Authentication"""
    print_section("TEST 2: Authentication")
    
    # Valid login
    r = requests.post(f"{BASE_URL}/api/login", headers=HEADERS, json={
        "username": "Victor",
        "password": "v123"
    })
    print_result("POST /api/login (valid)", r.status_code, r.json())
    
    # Invalid login
    r = requests.post(f"{BASE_URL}/api/login", headers=HEADERS, json={
        "username": "Victor",
        "password": "wrong"
    })
    print_result("POST /api/login (invalid)", r.status_code)
    
    return "Victor"


def test_interests(username):
    """Test 3: Get User Interests"""
    print_section("TEST 3: User Interests (with Graph API)")
    
    # First, get ALL topics to see what's available
    print("\n   Getting ALL topics from Neo4j...")
    try:
        r = requests.get(f"{BASE_URL}/topics/all", headers=HEADERS, timeout=5)
        if r.status_code != 200:
            print(f"   ⚠️  GET /topics/all returned {r.status_code}")
            r = None
    except Exception as e:
        print(f"   ⚠️  Could not get all topics: {e}")
        r = None
    
    if r and r.status_code == 200:
        try:
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
            print(f"   ⚠️  Could not parse topics: {e}")
    
    print(f"\n   Getting interests for user {username}...")
    try:
        r = requests.get(f"{BASE_URL}/interests", headers=HEADERS, params={"username": username}, timeout=5)
        try:
            data = r.json()
            print_result(f"GET /interests?username={username}", r.status_code, data)
            if r.status_code == 200:
                interests = data.get("interests", [])
                print(f"   Found {len(interests)} interests")
                for interest in interests[:3]:
                    print(f"   - {interest['id']}: {interest['name']}")
                return interests[0]["id"] if interests else None
        except:
            print_result(f"GET /interests?username={username}", r.status_code, {"response": r.text[:200]})
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
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
    
    stored_id = None
    try:
        r = requests.post(f"{BASE_URL}/api/articles", headers=HEADERS, json=article_data, timeout=5)
        try:
            data = r.json()
            print_result("POST /api/articles", r.status_code, data)
            stored_id = data.get("argos_id")
        except:
            print_result("POST /api/articles", r.status_code, {"response": r.text[:200]})
    except Exception as e:
        print(f"❌ POST /api/articles - Error: {e}")
    
    # Get article by ID
    if stored_id:
        try:
            r = requests.get(f"{BASE_URL}/api/articles/{stored_id}", headers=HEADERS, timeout=5)
            try:
                data = r.json()
                print_result(f"GET /api/articles/{stored_id}", r.status_code, {"title": data.get('data', {}).get('title', 'N/A')})
            except:
                print_result(f"GET /api/articles/{stored_id}", r.status_code)
        except Exception as e:
            print(f"   ⚠️  GET article error: {e}")
    
    # Get articles for topic (requires Graph API)
    if topic_id:
        print(f"\n   Testing GET /articles?topic_id={topic_id}")
        try:
            r = requests.get(f"{BASE_URL}/articles", headers=HEADERS, params={"topic_id": topic_id}, timeout=5)
            try:
                data = r.json()
                articles = data.get("articles", [])
                print_result(f"GET /articles?topic_id={topic_id}", r.status_code, {"count": len(articles)})
                print(f"   Found {len(articles)} articles")
            except:
                print_result(f"GET /articles?topic_id={topic_id}", r.status_code, {"response": r.text[:200]})
        except requests.exceptions.Timeout:
            print("   ⚠️  Timeout")
        except Exception as e:
            print(f"   ⚠️  Error: {str(e)}")


def test_strategies(username):
    """Test 5: Strategy Operations"""
    print_section("TEST 5: Strategies")
    
    # List strategies
    try:
        r = requests.get(f"{BASE_URL}/users/{username}/strategies", headers=HEADERS, timeout=5)
        try:
            data = r.json()
            print_result(f"GET /users/{username}/strategies", r.status_code, data)
            existing_strategies = data.get("strategies", [])
        except:
            print_result(f"GET /users/{username}/strategies", r.status_code, {"response": r.text[:200]})
            existing_strategies = []
    except Exception as e:
        print(f"❌ GET /users/{username}/strategies - Error: {e}")
        existing_strategies = []
    
    print(f"   Found {len(existing_strategies)} existing strategies")
    
    # Create new strategy
    try:
        r = requests.post(f"{BASE_URL}/users/{username}/strategies", headers=HEADERS, json={
            "asset": {"primary": "brent"},
            "user_input": {
                "strategy_text": "Bullish on Brent due to supply constraints",
                "position_text": "Long 100 barrels @ $85",
                "target": "$95"
            }
        }, timeout=5)
        try:
            data = r.json()
            print_result(f"POST /users/{username}/strategies", r.status_code, data)
        except:
            print_result(f"POST /users/{username}/strategies", r.status_code, {"response": r.text[:200]})
            return None
    except Exception as e:
        print(f"❌ POST /users/{username}/strategies - Error: {e}")
        return None
    
    if r and r.status_code == 200:
        try:
            new_strategy = r.json()
            strategy_id = new_strategy.get("id")
            if not strategy_id:
                print("   ⚠️  No strategy ID in response")
                return None
            print(f"   Created strategy: {strategy_id}")
            
            # Get strategy
            try:
                r = requests.get(f"{BASE_URL}/users/{username}/strategies/{strategy_id}", headers=HEADERS, timeout=5)
                try:
                    print_result(f"GET /users/{username}/strategies/{strategy_id}", r.status_code, r.json())
                except:
                    print_result(f"GET /users/{username}/strategies/{strategy_id}", r.status_code)
            except Exception as e:
                print(f"   ⚠️  GET strategy error: {e}")
            
            # Update strategy
            try:
                new_strategy["user_input"]["target"] = "$100"
                r = requests.put(f"{BASE_URL}/users/{username}/strategies/{strategy_id}", headers=HEADERS, json=new_strategy, timeout=5)
                try:
                    print_result(f"PUT /users/{username}/strategies/{strategy_id}", r.status_code, r.json())
                except:
                    print_result(f"PUT /users/{username}/strategies/{strategy_id}", r.status_code)
            except Exception as e:
                print(f"   ⚠️  PUT strategy error: {e}")
            
            # Delete strategy
            try:
                r = requests.delete(f"{BASE_URL}/users/{username}/strategies/{strategy_id}", headers=HEADERS, timeout=5)
                try:
                    print_result(f"DELETE /users/{username}/strategies/{strategy_id}", r.status_code, r.json())
                except:
                    print_result(f"DELETE /users/{username}/strategies/{strategy_id}", r.status_code)
            except Exception as e:
                print(f"   ⚠️  DELETE strategy error: {e}")
            
            return strategy_id
        except Exception as e:
            print(f"   ⚠️  Strategy operations error: {e}")
    
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
        r = requests.get(f"{BASE_URL}/reports/{topic_id}", headers=HEADERS, timeout=10)
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
    
    # Chat without strategy (TEST MODE - show context)
    print("\n--- Chat Test 1: Topic Only (TEST MODE) ---")
    try:
        r = requests.post(f"{BASE_URL}/chat", headers=HEADERS, json={
            "message": "What's the current outlook for Brent crude?",
            "topic_id": topic_id,
            "history": [],
            "test": True  # Enable test mode to see full context
        }, timeout=20)
        if r.status_code == 200:
            data = r.json()
            if data.get("test_mode"):
                print_result("POST /chat (topic only, test mode)", r.status_code, {
                    "test_mode": True,
                    "context_type": data.get("context_type"),
                    "context_size_chars": data.get("context_size_chars"),
                    "context_size_tokens": data.get("context_size_tokens")
                })
                print("\n" + "="*80)
                print("  FULL CONTEXT SENT TO LLM:")
                print("="*80)
                full_context = data.get("full_context", "")
                if len(full_context) > 3000:
                    print(full_context[:3000] + "\n\n... (truncated, total: " + str(len(full_context)) + " chars)")
                else:
                    print(full_context)
                print("="*80)
            else:
                print_result("POST /chat (topic only)", r.status_code, data)
        else:
            print_result("POST /chat (topic only)", r.status_code)
    except requests.exceptions.Timeout:
        print("   ⚠️  Timeout - Graph API may not be running")
    except Exception as e:
        print(f"   ⚠️  Error: {str(e)}")
    
    # Chat with strategy (if exists)
    print("\n--- Chat Test 2: Topic + Strategy (TEST MODE) ---")
    try:
        strategies_r = requests.get(f"{BASE_URL}/users/{username}/strategies", headers=HEADERS, timeout=5)
    except Exception as e:
        print(f"   ⚠️  Could not get strategies: {e}")
        return
    
    if strategies_r and strategies_r.status_code == 200:
        strategies = strategies_r.json().get("strategies", [])
        if strategies:
            strategy_id = strategies[0]["id"]
            try:
                r = requests.post(f"{BASE_URL}/chat", headers=HEADERS, json={
                    "message": "How does this align with my strategy?",
                    "topic_id": topic_id,
                    "strategy_id": strategy_id,
                    "username": username,
                    "history": [],
                    "test": True  # Enable test mode
                }, timeout=15)
                if r.status_code == 200:
                    data = r.json()
                    if data.get("test_mode"):
                        print_result("POST /chat (topic + strategy, test mode)", r.status_code, {
                            "test_mode": True,
                            "context_type": data.get("context_type"),
                            "context_size_chars": data.get("context_size_chars"),
                            "context_size_tokens": data.get("context_size_tokens")
                        })
                        print("\n" + "="*80)
                        print("  FULL CONTEXT WITH STRATEGY:")
                        print("="*80)
                        full_context = data.get("full_context", "")
                        if len(full_context) > 3000:
                            print(full_context[:3000] + "\n\n... (truncated, total: " + str(len(full_context)) + " chars)")
                        else:
                            print(full_context)
                        print("="*80)
                    else:
                        print_result("POST /chat (topic + strategy)", r.status_code, data, show_full=True)
                else:
                    print_result("POST /chat (topic + strategy)", r.status_code)
            except Exception as e:
                print(f"   ⚠️  Error: {str(e)}")


def test_error_handling():
    """Test 8: Error Handling"""
    print_section("TEST 8: Error Handling")
    
    # Non-existent article
    try:
        r = requests.get(f"{BASE_URL}/api/articles/nonexistent123", headers=HEADERS, timeout=5)
        print_result("GET /api/articles/nonexistent123", r.status_code)
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    # Non-existent strategy
    try:
        r = requests.get(f"{BASE_URL}/users/Victor/strategies/nonexistent123", headers=HEADERS, timeout=5)
        print_result("GET /users/Victor/strategies/nonexistent123", r.status_code)
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    # Invalid user
    try:
        r = requests.get(f"{BASE_URL}/interests", headers=HEADERS, params={"username": "InvalidUser"}, timeout=5)
        print_result("GET /interests?username=InvalidUser", r.status_code)
    except Exception as e:
        print(f"   ⚠️  Error: {e}")


def test_admin_endpoints():
    """Test 9: Admin Endpoints"""
    print_section("TEST 9: Admin Endpoints")
    
    # Admin summary
    try:
        r = requests.get(f"{BASE_URL}/api/admin/summary", headers=HEADERS, timeout=5)
        try:
            data = r.json()
            print_result("GET /api/admin/summary", r.status_code, {
                "date": data.get("date"),
                "pipeline": data.get("pipeline"),
                "topics": data.get("topics")
            })
        except:
            print_result("GET /api/admin/summary", r.status_code, {"response": r.text[:200]})
    except Exception as e:
        print(f"   ⚠️  Error: {e}")


# ============ MAIN TEST RUNNER ============

def main():
    print("\n" + "="*80)
    print("  COMPREHENSIVE API TEST SUITE")
    print("  Testing Backend API with full output")
    print("="*80)
    print(f"\n  Backend API: {BASE_URL}")
    print(f"  Graph API: {GRAPH_API_URL}")
    print(f"  API Key: {'✅ Configured' if API_KEY else '❌ Not set (localhost mode)'}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n  Chat test=True mode shows FULL CONTEXT")
    
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
        
        # Test 9: Admin Endpoints
        test_admin_endpoints()
        
        print_section("TEST SUMMARY")
        print("✅ All tests completed!")
        print("\nNotes:")
        print("  - Tests marked with ⚠️ require Graph API")
        print("  - Some endpoints may return non-JSON responses")
        print("  - Check individual test results above")
        
    except requests.exceptions.ConnectionError as e:
        print(f"\n❌ Cannot connect to {BASE_URL}")
        print(f"   Error: {e}")
        print("   Make sure Backend API is running and accessible")
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        print("\nContinuing with remaining tests...")


if __name__ == "__main__":
    main()
