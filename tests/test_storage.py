#!/usr/bin/env python3
"""
Simple storage test - Tests article storage directly
Run from saga-be directory: python tests/test_storage.py
"""
import sys
import json
from pathlib import Path

# Add parent directory to path so we can import src
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.article_manager import ArticleStorageManager


def test_storage():
    """Test article storage operations"""
    print("\n" + "=" * 60)
    print("🧪 TESTING ARTICLE STORAGE")
    print("=" * 60)
    
    # Initialize storage
    print("\n1. Initializing storage...")
    storage = ArticleStorageManager("data/raw_news")
    print(f"   Data dir: {storage.data_dir.absolute()}")
    print(f"   Today dir: {storage.today_dir.absolute()}")
    
    # Create test article
    print("\n2. Creating test article...")
    test_article = {
        "argos_id": "TESTXYZ123",
        "url": "https://test.example.com/article",
        "title": "Test Article",
        "pubDate": "2025-11-04",
        "content": "Test content"
    }
    
    # Store article
    print("\n3. Storing article...")
    result = storage.store_article(test_article)
    print(f"   Stored ID: {result}")
    assert result == "TESTXYZ123", "Storage should return correct ID"
    
    # Verify file exists
    print("\n4. Verifying file exists...")
    file_path = storage.today_dir / f"{result}.json"
    assert file_path.exists(), f"File should exist: {file_path}"
    print(f"   ✅ File exists: {file_path}")
    
    with open(file_path) as f:
        data = json.load(f)
        assert data.get('title') == "Test Article", "Title should match"
        print(f"   ✅ Title: {data.get('title')}")
    
    # Test retrieval
    print("\n5. Testing retrieval...")
    retrieved = storage.get_article(result)
    assert retrieved is not None, "Should retrieve article"
    assert retrieved.get('title') == "Test Article", "Retrieved title should match"
    print(f"   ✅ Retrieved: {retrieved.get('title')}")
    
    # Test deduplication
    print("\n6. Testing deduplication...")
    dup_id = storage.find_article_by_url(test_article["url"])
    assert dup_id == result, f"Should find duplicate: expected {result}, got {dup_id}"
    print(f"   ✅ Deduplication works: {dup_id}")
    
    # Test storing duplicate (should skip)
    print("\n7. Testing duplicate storage...")
    result2 = storage.store_article(test_article)
    assert result2 == result, "Should return same ID for duplicate"
    print(f"   ✅ Duplicate skipped: {result2}")
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        test_storage()
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        exit(1)
