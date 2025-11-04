# 📜 Backend Scripts

Utility scripts for managing articles and backend data.

---

## **upload_articles.py**

Bulk upload all articles from `data/raw_news/` to Backend API.

### **Usage:**

```bash
# From saga-be directory:
cd saga-be

# Upload all articles
python scripts/upload_articles.py

# Upload first 100 articles (for testing)
python scripts/upload_articles.py --limit 100

# Specify custom backend URL
python scripts/upload_articles.py --backend-url http://130.241.129.211
```

### **Features:**
- ✅ Automatic deduplication (uses `/api/articles/ingest`)
- ✅ Progress indicator with upload rate
- ✅ Summary statistics (created/existing/failed)
- ✅ Handles errors gracefully
- ✅ No dependencies on graph-functions (standalone)

### **Requirements:**
- Backend API must be running
- Optional: Set `BACKEND_API_URL` and `BACKEND_API_KEY` in environment

### **Example:**

```bash
# Local development (backend running in Docker)
python scripts/upload_articles.py

# Or with explicit URL
python scripts/upload_articles.py --backend-url http://localhost:8000

# Upload to remote server
python scripts/upload_articles.py \
  --backend-url http://130.241.129.211 \
  --api-key 785fc6c1647ff650b6b611509cc0a8f47009e6b743340503519d433f111fcf12
```

### **Output:**

```
================================================================================
📤 BULK ARTICLE UPLOAD
================================================================================
Backend URL: http://localhost:8000
API Key: ✅ Set

Data directory: /path/to/saga-be/data/raw_news

🔍 Scanning for articles...
Found 1310 articles

📤 Uploading articles...
--------------------------------------------------------------------------------
✅ [10/1310] ABC123.json → created → XYZ789 (12.5/s)
♻️  [20/1310] DEF456.json → existing → ABC123 (15.2/s)
...
--------------------------------------------------------------------------------

================================================================================
✅ UPLOAD COMPLETE!
================================================================================

Summary:
  ✅ Created: 1200
  ♻️  Existing: 100
  ❌ Failed: 10
  ⏱️  Time: 87.3s (15.0 articles/sec)
```

---

## **Workflow**

### **Initial Setup (Fresh Container):**

1. Start backend with 0 articles:
   ```bash
   cd victor_deployment
   docker compose up -d saga-apis
   ```

2. Upload all articles:
   ```bash
   cd ../saga-be
   python scripts/upload_articles.py
   ```

3. Verify:
   ```bash
   curl http://localhost:8000/api/articles?limit=10
   ```

### **Re-uploading (Deduplication):**

Running the script again will:
- ✅ Skip existing articles (returns "existing" status)
- ✅ Only create new articles
- ✅ Fast (deduplication check is efficient)

---

## **Notes**

- Script reads articles from `data/raw_news/` (local filesystem)
- Uploads via HTTP API to backend
- Backend handles ID generation and storage
- Deduplication based on URL + pubDate
