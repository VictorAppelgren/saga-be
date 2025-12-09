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
import random
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API URLs from environment or use localhost
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
GRAPH_API_URL = os.getenv("GRAPH_API_URL", "http://localhost:8001")
API_KEY = os.getenv("API_KEY", "")
DIAG_ARTICLE_IDS = os.getenv("DIAG_ARTICLE_IDS", "")
try:
    ARTICLE_DIAG_MAX_IDS = int(os.getenv("ARTICLE_DIAG_MAX_IDS", "1000"))
except ValueError:
    ARTICLE_DIAG_MAX_IDS = 1000

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


def test_article_storage_diagnostics():
    """Test 10: Article Storage Diagnostics (optional)"""
    print_section("TEST 10: Article Storage Diagnostics")
    
    # Storage stats
    try:
        r = requests.get(f"{BASE_URL}/api/articles/storage/stats", headers=HEADERS, timeout=10)
        try:
            data = r.json()
        except Exception:
            data = {"response": r.text[:200]}
        print_result("GET /api/articles/storage/stats", r.status_code, data)
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    # Optional existence check for specific IDs from env
    if DIAG_ARTICLE_IDS:
        raw_ids = [s.strip() for s in DIAG_ARTICLE_IDS.split(",") if s.strip()]
        if not raw_ids:
            return
        print(f"\n   Checking existence of {len(raw_ids)} IDs from DIAG_ARTICLE_IDS...")
        try:
            r = requests.post(
                f"{BASE_URL}/api/articles/check-existence",
                headers=HEADERS,
                json=raw_ids,
                timeout=30,
            )
            try:
                data = r.json()
            except Exception:
                data = {"response": r.text[:200]}
            summary = {
                "checked": data.get("checked", len(raw_ids)),
                "existing": len(data.get("existing", [])),
                "missing": len(data.get("missing", [])),
            }
            print_result(
                "POST /api/articles/check-existence (DIAG_ARTICLE_IDS)",
                r.status_code,
                summary,
            )
            missing = data.get("missing") or []
            if missing:
                preview = ", ".join(missing[:20])
                more = "" if len(missing) <= 20 else f"... (+{len(missing) - 20} more)"
                print(f"   Missing IDs (sample): {preview}{more}")
        except Exception as e:
            print(f"   ⚠️  Existence check error: {e}")
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


def test_article_listing_and_sampling():
    """Test 11: Article Listing & Sampling"""
    print_section("TEST 11: Article Listing & Sampling")
    
    # List first batch of article IDs
    try:
        params = {"offset": 0, "limit": 200}
        r = requests.get(f"{BASE_URL}/api/articles/ids", headers=HEADERS, params=params, timeout=30)
        try:
            data = r.json()
        except Exception:
            data = {"response": r.text[:200]}
        ids = data.get("article_ids", [])
        meta = {
            "count": len(ids),
            "has_more": data.get("has_more", False),
        }
        print_result("GET /api/articles/ids", r.status_code, meta)
    except Exception as e:
        print(f"   ⚠️  Error listing article IDs: {e}")
        return
    
    if not ids:
        print("   ⚠️  No article IDs returned from /api/articles/ids")
        return
    
    # Sample a few articles and print basic info
    sample_size = min(5, len(ids))
    sample_ids = random.sample(ids, sample_size)
    print(f"\n   Sampling {sample_size} articles:")
    
    for article_id in sample_ids:
        try:
            r = requests.get(f"{BASE_URL}/api/articles/{article_id}", headers=HEADERS, timeout=10)
            try:
                payload = r.json()
                article_data = payload.get("data", {})
                inner = article_data.get("data", article_data)
                title = inner.get("title", "N/A")
                summary = inner.get("summary") or inner.get("description") or inner.get("argos_summary") or ""
                content = inner.get("content") or ""
                text = " ".join([title or "", summary or "", content or ""]).strip()
                preview = text[:300] if text else ""
                print_result(
                    f"GET /api/articles/{article_id}",
                    r.status_code,
                    {"title": title, "preview": preview},
                )
            except Exception:
                print_result(
                    f"GET /api/articles/{article_id}",
                    r.status_code,
                    {"response": r.text[:200]},
                )
        except Exception as e:
            print(f"   ⚠️  Error fetching article {article_id}: {e}")


def test_article_search_and_existence():
    """Test 12: Article Search & Existence"""
    print_section("TEST 12: Article Search & Existence")
    
    # Keyword search
    search_body = {
        "keywords": ["fed", "rate", "inflation"],
        "limit": 5,
        "min_keyword_hits": 2,
    }
    results = []
    try:
        r = requests.post(
            f"{BASE_URL}/api/articles/search",
            headers=HEADERS,
            json=search_body,
            timeout=30,
        )
        try:
            data = r.json()
        except Exception:
            data = {"response": r.text[:200]}
        results = data.get("results", [])
        example_id = results[0]["article_id"] if results else None
        meta = {
            "count": len(results),
            "example_id": example_id,
        }
        print_result("POST /api/articles/search", r.status_code, meta)
    except Exception as e:
        print(f"   ⚠️  Search error: {e}")
        return
    
    # Existence check on search results (sanity check for storage)
    if not results:
        print("   ⚠️  No search results to check existence for")
        return
    
    ids = [r["article_id"] for r in results]
    try:
        r = requests.post(
            f"{BASE_URL}/api/articles/check-existence",
            headers=HEADERS,
            json=ids,
            timeout=30,
        )
        try:
            data = r.json()
        except Exception:
            data = {"response": r.text[:200]}
        summary = {
            "checked": data.get("checked", len(ids)),
            "existing": len(data.get("existing", [])),
            "missing": len(data.get("missing", [])),
        }
        print_result(
            "POST /api/articles/check-existence (search results)",
            r.status_code,
            summary,
        )
    except Exception as e:
        print(f"   ⚠️  Existence check error (search results): {e}")


def test_article_random_sampling_large():
    """Test 13: Article Random Sampling (Large)"""
    print_section("TEST 13: Article Random Sampling (Large)")
    
    # Fetch a larger pool of IDs using pagination
    ids: list[str] = []
    offset = 0
    page_limit = 500
    pages = 0
    target = max(ARTICLE_DIAG_MAX_IDS, 100)
    
    while len(ids) < target:
        try:
            params = {"offset": offset, "limit": page_limit}
            r = requests.get(
                f"{BASE_URL}/api/articles/ids",
                headers=HEADERS,
                params=params,
                timeout=60,
            )
            try:
                data = r.json()
            except Exception:
                data = {"response": r.text[:200]}
            page_ids = data.get("article_ids", [])
            if not page_ids:
                break
            ids.extend(page_ids)
            pages += 1
            offset += len(page_ids)
            if not data.get("has_more", False):
                break
        except Exception as e:
            print(f"   ⚠️  Error fetching article IDs page at offset {offset}: {e}")
            break
    
    if not ids:
        print("   ⚠️  No article IDs available for large sampling")
        return
    
    print(
        f"   Collected {len(ids)} IDs across {pages} pages "
        f"(target={target}, total_raw_articles may be larger)."
    )
    
    # Sample many articles and check success rate
    sample_size = min(len(ids), max(100, min(ARTICLE_DIAG_MAX_IDS, 500)))
    sample_ids = random.sample(ids, sample_size)
    print(f"\n   Sampling {sample_size} random articles for detailed checks...")
    
    ok = 0
    missing = 0
    errors = 0
    shown = 0
    max_show = 10
    
    for article_id in sample_ids:
        try:
            r = requests.get(
                f"{BASE_URL}/api/articles/{article_id}",
                headers=HEADERS,
                timeout=10,
            )
            status = r.status_code
            if status == 200:
                ok += 1
                if shown < max_show:
                    try:
                        payload = r.json()
                    except Exception:
                        payload = {"response": r.text[:200]}
                    article_data = payload.get("data", {})
                    inner = article_data.get("data", article_data)
                    title = inner.get("title", "N/A")
                    summary = (
                        inner.get("summary")
                        or inner.get("description")
                        or inner.get("argos_summary")
                        or ""
                    )
                    content = inner.get("content") or ""
                    text = " ".join([title or "", summary or "", content or ""]).strip()
                    preview = text[:300] if text else ""
                    print_result(
                        f"GET /api/articles/{article_id}",
                        status,
                        {"title": title, "preview": preview},
                    )
                    shown += 1
            elif status == 404:
                missing += 1
            else:
                errors += 1
        except Exception as e:
            errors += 1
            if shown < max_show:
                print(f"   ⚠️  Error fetching article {article_id}: {e}")
                shown += 1
    
    summary = {
        "sample_size": sample_size,
        "ok": ok,
        "missing_404": missing,
        "other_errors": errors,
    }
    print_result(
        "Article Random Sampling (Large)",
        200 if errors == 0 else 500,
        summary,
    )


def test_article_bulk_existence_sampling():
    """Test 14: Article Bulk Existence Sampling"""
    print_section("TEST 14: Article Bulk Existence Sampling")
    
    # Get a large set of IDs in a single call (bounded by ARTICLE_DIAG_MAX_IDS)
    limit = min(max(ARTICLE_DIAG_MAX_IDS, 100), 50000)
    try:
        params = {"offset": 0, "limit": limit}
        r = requests.get(
            f"{BASE_URL}/api/articles/ids",
            headers=HEADERS,
            params=params,
            timeout=60,
        )
        try:
            data = r.json()
        except Exception:
            data = {"response": r.text[:200]}
        ids = data.get("article_ids", [])
    except Exception as e:
        print(f"   ⚠️  Error fetching IDs for bulk existence sampling: {e}")
        return
    
    if not ids:
        print("   ⚠️  No article IDs returned for bulk existence sampling")
        return
    
    sample_size = min(len(ids), limit)
    sample_ids = random.sample(ids, sample_size)
    print(f"   Checking existence for {sample_size} randomly sampled IDs...")
    
    total_existing = 0
    total_missing = 0
    total_checked = 0
    batch_size = 500
    last_status = 200
    missing_sample: list[str] = []
    
    for i in range(0, sample_size, batch_size):
        batch = sample_ids[i : i + batch_size]
        try:
            r = requests.post(
                f"{BASE_URL}/api/articles/check-existence",
                headers=HEADERS,
                json=batch,
                timeout=60,
            )
            last_status = r.status_code
            try:
                data = r.json()
            except Exception:
                data = {"response": r.text[:200]}
                continue
            existing = data.get("existing", [])
            missing = data.get("missing", [])
            checked = data.get("checked", len(batch))
            total_existing += len(existing)
            total_missing += len(missing)
            total_checked += checked
            if not missing_sample and missing:
                missing_sample = missing[:20]
        except Exception as e:
            print(f"   ⚠️  Error in bulk existence batch {i}-{i+len(batch)}: {e}")
    
    summary = {
        "sample_size": sample_size,
        "checked_reported": total_checked,
        "existing": total_existing,
        "missing": total_missing,
    }
    print_result(
        "POST /api/articles/check-existence (bulk sample)",
        last_status,
        summary,
    )
    
    if missing_sample:
        preview = ", ".join(missing_sample)
        more = "" if total_missing <= len(missing_sample) else f"... (+{total_missing - len(missing_sample)} more)"
        print(f"   Missing IDs (sample): {preview}{more}")


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
        
        # Test 10: Article Storage Diagnostics (optional)
        test_article_storage_diagnostics()
        
        # Test 11: Article Listing & Sampling
        test_article_listing_and_sampling()

        # Test 12: Article Search & Existence
        test_article_search_and_existence()

        # Test 13: Article Random Sampling (Large)
        test_article_random_sampling_large()

        # Test 14: Article Bulk Existence Sampling
        test_article_bulk_existence_sampling()

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
