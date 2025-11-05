#!/usr/bin/env python3
"""
Admin API Integration Tests
Tests Backend → Graph API flow with beautiful output
"""
import requests
import json
from datetime import datetime

# Configuration
BACKEND_URL = "http://localhost:8000"
GRAPH_API_URL = "http://localhost:8001"

def print_header(text):
    """Print a header"""
    print(f"\n{'='*80}")
    print(f"  {text}")
    print(f"{'='*80}\n")


def print_test(name):
    """Print test name"""
    print(f"▶ {name}")


def print_success(message):
    """Print success message"""
    print(f"  ✓ {message}")


def print_data(label, value):
    """Print data in a nice format"""
    print(f"  {label}: {value}")


def print_trend(dates, values, label):
    """Print trend data in a visual format"""
    print(f"\n  {label}:")
    for date, value in zip(dates, values):
        bar = "█" * min(int(value / 2), 50)  # Scale bars
        print(f"    {date}: {bar} {value}")


def test_health():
    """Test health endpoints"""
    print_test("Health Check")
    
    # Backend
    r = requests.get(f"{BACKEND_URL}/health")
    assert r.status_code == 200, "Backend health check failed"
    print_success(f"Backend healthy: {r.json()['status']}")
    
    # Graph API
    r = requests.get(f"{GRAPH_API_URL}/neo/health")
    assert r.status_code == 200, "Graph API health check failed"
    print_success(f"Graph API healthy: {r.json()['status']}")


def test_stats_today():
    """Test today's statistics"""
    print_test("Today's Statistics")
    
    r = requests.get(f"{BACKEND_URL}/api/admin/stats/today")
    assert r.status_code == 200, "Failed to get today's stats"
    
    data = r.json()
    today = data["today"]
    graph_state = data["graph_state"]
    
    # Print key metrics
    print_data("Articles Added", today["ingestion"]["articles_added"])
    print_data("Articles Processed", today["ingestion"]["articles_processed"])
    print_data("Duplicates Skipped", today["ingestion"]["duplicates_skipped"])
    print_data("Queries", today["ingestion"]["queries"])
    print_data("Sections Written", today["analysis"]["sections_written"])
    print_data("Topics in Graph", graph_state["topics"])
    print_data("Articles in Graph", graph_state["articles"])
    print_data("Connections", graph_state["connections"])
    print_data("Errors", today["system"]["errors"])
    
    print_success("Stats retrieved successfully")


def test_stats_range():
    """Test stats range"""
    print_test("Stats Range (Last 7 Days)")
    
    r = requests.get(f"{BACKEND_URL}/api/admin/stats/range?days=7")
    assert r.status_code == 200, "Failed to get stats range"
    
    data = r.json()
    print_data("Days Retrieved", len(data))
    
    if data:
        print_data("Oldest Date", data[-1]["date"])
        print_data("Newest Date", data[0]["date"])
    
    print_success(f"Retrieved {len(data)} days of statistics")


def test_trends_articles():
    """Test article trends"""
    print_test("Article Ingestion Trends (Last 10 Days)")
    
    r = requests.get(f"{BACKEND_URL}/api/admin/trends/articles?days=10")
    assert r.status_code == 200, "Failed to get article trends"
    
    data = r.json()
    
    # Print trend visualization
    print_trend(data["dates"], data["articles_added"], "Articles Added")
    print_trend(data["dates"], data["duplicates_skipped"], "Duplicates Skipped")
    
    total_added = sum(data["articles_added"])
    total_processed = sum(data["articles_processed"])
    
    print_data("\nTotal Added (10 days)", total_added)
    print_data("Total Processed (10 days)", total_processed)
    print_data("Average per Day", round(total_added / len(data["dates"]), 1))
    
    print_success("Article trends retrieved")


def test_trends_analysis():
    """Test analysis trends"""
    print_test("Analysis Generation Trends (Last 10 Days)")
    
    r = requests.get(f"{BACKEND_URL}/api/admin/trends/analysis?days=10")
    assert r.status_code == 200, "Failed to get analysis trends"
    
    data = r.json()
    
    print_trend(data["dates"], data["sections_written"], "Sections Written")
    
    total_sections = sum(data["sections_written"])
    total_attempts = sum(data["rewrite_attempts"])
    
    print_data("Total Sections (10 days)", total_sections)
    print_data("Total Rewrite Attempts", total_attempts)
    if len(data["dates"]) > 0:
        print_data("Average per Day", round(total_sections / len(data["dates"]), 1))
    
    print_success("Analysis trends retrieved")


def test_trends_graph():
    """Test graph growth trends"""
    print_test("Graph Growth Trends (Last 10 Days)")
    
    r = requests.get(f"{BACKEND_URL}/api/admin/trends/graph?days=10")
    assert r.status_code == 200, "Failed to get graph trends"
    
    data = r.json()
    
    print_trend(data["dates"], data["topics"], "Topics")
    print_trend(data["dates"], data["articles"], "Articles")
    
    # Calculate growth
    if len(data["topics"]) > 1:
        topic_growth = data["topics"][-1] - data["topics"][0]
        article_growth = data["articles"][-1] - data["articles"][0]
        
        print_data("\nTopic Growth (10 days)", f"+{topic_growth}" if topic_growth >= 0 else topic_growth)
        print_data("Article Growth (10 days)", f"+{article_growth}" if article_growth >= 0 else article_growth)
    
    print_success("Graph trends retrieved")


def test_trends_llm():
    """Test LLM usage trends"""
    print_test("LLM Usage Trends (Last 10 Days)")
    
    r = requests.get(f"{BACKEND_URL}/api/admin/trends/llm?days=10")
    assert r.status_code == 200, "Failed to get LLM trends"
    
    data = r.json()
    
    print_trend(data["dates"], data["total"], "Total LLM Calls")
    
    total_simple = sum(data["simple"])
    total_medium = sum(data["medium"])
    total_complex = sum(data["complex"])
    total_all = sum(data["total"])
    
    print_data("\nSimple Calls (10 days)", total_simple)
    print_data("Medium Calls (10 days)", total_medium)
    print_data("Complex Calls (10 days)", total_complex)
    print_data("Total Calls (10 days)", total_all)
    print_data("Average per Day", round(total_all / len(data["dates"]), 1))
    
    print_success("LLM trends retrieved")


def test_trends_errors():
    """Test error trends"""
    print_test("Error Trends (Last 10 Days)")
    
    r = requests.get(f"{BACKEND_URL}/api/admin/trends/errors?days=10")
    assert r.status_code == 200, "Failed to get error trends"
    
    data = r.json()
    
    print_trend(data["dates"], data["errors"], "Errors")
    
    total_errors = sum(data["errors"])
    total_llm_failures = sum(data["llm_failures"])
    
    print_data("\nTotal Errors (10 days)", total_errors)
    print_data("Total LLM Failures (10 days)", total_llm_failures)
    
    if total_errors == 0:
        print_success("🎉 No errors in the last 10 days!")
    else:
        print_success("Error trends retrieved")


def test_logs_today():
    """Test today's logs"""
    print_test("Today's Logs (Last 20 Lines)")
    
    r = requests.get(f"{BACKEND_URL}/api/admin/logs/today?lines=20")
    assert r.status_code == 200, "Failed to get today's logs"
    
    data = r.json()
    
    print_data("Date", data["date"])
    print_data("Lines Retrieved", len(data["lines"]))
    
    if data["lines"]:
        print(f"\n  Recent Log Entries:")
        for line in data["lines"][-5:]:  # Show last 5
            print(f"    {line[:100]}...")
    
    print_success("Logs retrieved")


def test_summary():
    """Test admin summary"""
    print_test("Admin Dashboard Summary")
    
    r = requests.get(f"{BACKEND_URL}/api/admin/summary")
    assert r.status_code == 200, "Failed to get summary"
    
    data = r.json()
    last_7 = data["last_7_days"]
    
    print(f"\n  Last 7 Days Summary:")
    print_data("Articles Added", last_7["articles_added"])
    print_data("Sections Written", last_7["sections_written"])
    print_data("Queries Processed", last_7["queries_processed"])
    print_data("Available Dates", len(data["available_dates"]))
    
    print_success("Summary retrieved")


def test_authentication():
    """Test user authentication"""
    print_test("User Authentication")
    
    # Test admin user
    r = requests.post(
        f"{BACKEND_URL}/api/login",
        json={"username": "Victor", "password": "v123"}
    )
    assert r.status_code == 200, "Admin login failed"
    user = r.json()
    assert user["is_admin"] == True, "Victor should be admin"
    print_success(f"Admin user: {user['username']} (is_admin={user['is_admin']})")
    
    # Test regular user
    r = requests.post(
        f"{BACKEND_URL}/api/login",
        json={"username": "William", "password": "w456"}
    )
    assert r.status_code == 200, "User login failed"
    user = r.json()
    assert user["is_admin"] == False, "William should not be admin"
    print_success(f"Regular user: {user['username']} (is_admin={user['is_admin']})")


def main():
    """Run all tests"""
    print(f"\n{'='*80}")
    print(f"  🧪 ADMIN API INTEGRATION TESTS")
    print(f"{'='*80}")
    
    tests = [
        ("Health Checks", test_health),
        ("Statistics", test_stats_today),
        ("Stats Range", test_stats_range),
        ("Article Trends", test_trends_articles),
        ("Analysis Trends", test_trends_analysis),
        ("Graph Growth", test_trends_graph),
        ("LLM Usage", test_trends_llm),
        ("Error Trends", test_trends_errors),
        ("Logs", test_logs_today),
        ("Summary", test_summary),
        ("Authentication", test_authentication),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        print_header(name)
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"✗ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ ERROR: {e}")
            failed += 1
    
    # Final summary
    print(f"\n{'='*80}")
    print(f"  TEST RESULTS")
    print(f"{'='*80}")
    print(f"✓ Passed: {passed}")
    if failed > 0:
        print(f"✗ Failed: {failed}")
    else:
        print(f"🎉 ALL TESTS PASSED!")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
