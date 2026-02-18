# Complete Setup Guide - AI-Powered Community Matching System

Follow these steps in order to run the system without errors.

---

## Step 1: Install Prerequisites

### Required Software
1. **Python 3.10+**
   ```bash
   python --version  # Should be 3.10 or higher
   ```

2. **PostgreSQL 16**
   - Download: https://www.postgresql.org/download/windows/
   - During installation, remember your password for the `postgres` user

3. **Redis**
   - Download for Windows: https://github.com/microsoftarchive/redis/releases
   - OR use WSL2/Docker:
   ```bash
   docker run -d -p 6379:6379 redis:latest
   ```

### API Keys Required
- **OpenAI API Key**: Get from https://platform.openai.com/api-keys
- **Pinecone API Key**: Get from https://www.pinecone.io/ (free tier available)

---

## Step 2: Environment Setup

### 2.1 Create Virtual Environment
```bash
cd "d:\code anti\matching_system"
python -m venv venv
.\venv\Scripts\activate  # Windows
```

### 2.2 Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 2.3 Configure Environment Variables
```bash
# Copy the example file
copy .env.example .env

# Edit .env with your actual values
notepad .env
```

**Fill in these required values in `.env`:**
```bash
POSTGRES_PASSWORD=your_actual_postgres_password
OPENAI_API_KEY=sk-your-actual-openai-key
PINECONE_API_KEY=your-actual-pinecone-key
```

---

## Step 3: Database Setup

### 3.1 Create PostgreSQL Database
```bash
# Connect to PostgreSQL
psql -U postgres

# In the psql prompt:
CREATE DATABASE community_matching;
\c community_matching
```

### 3.2 Create Tables
Copy and paste this SQL:

```sql
-- Communities table
CREATE TABLE communities (
    community_id TEXT PRIMARY KEY,
    community_name TEXT NOT NULL,
    category TEXT NOT NULL,
    city TEXT NOT NULL,
    timezone TEXT NOT NULL,
    member_count INTEGER DEFAULT 0,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Community members table
CREATE TABLE community_members (
    user_id TEXT NOT NULL,
    community_id TEXT NOT NULL,
    joined_at TIMESTAMP DEFAULT NOW(),
    auto_joined BOOLEAN DEFAULT false,
    PRIMARY KEY (user_id, community_id)
);

-- Community activity table
CREATE TABLE community_activity (
    message_id TEXT PRIMARY KEY,
    community_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Users table
CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    username TEXT NOT NULL,
    bio TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Performance indexes
CREATE INDEX idx_communities_location ON communities(city, timezone);
CREATE INDEX idx_activity_recent ON community_activity(community_id, created_at);
CREATE INDEX idx_communities_active ON communities(is_active, member_count DESC);

-- Exit psql
\q
```

### 3.3 Add Sample Data (Optional but Recommended)
```sql
-- Insert sample communities
INSERT INTO communities (community_id, community_name, category, city, timezone, member_count, description) VALUES
('comm_001', 'Python Developers SF', 'Programming', 'San Francisco', 'America/Los_Angeles', 1250, 'Python enthusiasts'),
('comm_002', 'AI/ML Researchers', 'AI', 'San Francisco', 'America/Los_Angeles', 890, 'Machine learning community'),
('comm_003', 'Web Dev NYC', 'Programming', 'New York', 'America/New_York', 2100, 'Full-stack developers'),
('comm_004', 'Data Science Hub', 'Data Science', 'San Francisco', 'America/Los_Angeles', 1500, 'Data scientists'),
('comm_005', 'Gaming Community', 'Gaming', 'San Francisco', 'America/Los_Angeles', 3200, 'Gamers unite');

-- Insert sample users
INSERT INTO users (user_id, username, bio) VALUES
('user_001', 'alice_dev', 'Senior Python developer, love ML'),
('user_002', 'bob_gamer', 'Casual gamer, tech enthusiast');
```

---

## Step 4: Verify Services

### 4.1 Check PostgreSQL
```bash
psql -U postgres -d community_matching -c "SELECT COUNT(*) FROM communities;"
# Should return the count (5 if you added sample data)
```

### 4.2 Check Redis
```bash
redis-cli ping
# Should return: PONG
```

### 4.3 Check Pinecone (will auto-create index on first run)
The system will automatically create the Pinecone index when it starts.

---

## Step 5: Start the System

You need **3 terminal windows** running simultaneously:

### Terminal 1: Start FastAPI Server
```bash
cd "d:\code anti\matching_system"
.\venv\Scripts\activate
uvicorn matching_system.api:app --reload --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

### Terminal 2: Start Celery Worker
```bash
cd "d:\code anti\matching_system"
.\venv\Scripts\activate
celery -A matching_system.celery_tasks worker --loglevel=info --pool=solo
```

**Note:** Use `--pool=solo` on Windows (Celery limitation)

**Expected output:**
```
[tasks]
  . matching_system.celery_tasks.process_match_task
celery@hostname ready.
```

### Terminal 3: Ensure Redis is Running
```bash
redis-server
# OR if using Docker:
docker ps  # Check if Redis container is running
```

---

## Step 6: Test the System

### 6.1 Health Check
Open browser: http://localhost:8000/api/v1/health

Should return:
```json
{
  "status": "healthy",
  "postgres": "connected",
  "pinecone": "connected",
  "redis": "connected"
}
```

### 6.2 Test API with cURL
```bash
curl -X POST http://localhost:8000/api/v1/match ^
  -H "Content-Type: application/json" ^
  -d "{\"user_id\":\"test_user_123\",\"bio\":\"Software engineer passionate about AI and machine learning\",\"interest_tags\":[\"Programming\",\"AI\"],\"city\":\"San Francisco\",\"timezone\":\"America/Los_Angeles\"}"
```

**Expected response:**
```json
{
  "task_id": "some-uuid",
  "status": "processing",
  "estimated_time_ms": 2000,
  "websocket_channel": "match_updates_test_user_123"
}
```

### 6.3 Get Results
```bash
# Use the task_id from previous response
curl http://localhost:8000/api/v1/match/{task_id}
```

---

## Common Errors & Solutions

### Error: "ModuleNotFoundError: No module named 'matching_system'"
**Solution:** Make sure you're in the parent directory and virtual environment is activated:
```bash
cd "d:\code anti"
.\venv\Scripts\activate
```

### Error: "Connection refused" (PostgreSQL)
**Solution:** 
1. Check if PostgreSQL is running: `services.msc` → Find PostgreSQL
2. Verify connection settings in `.env`

### Error: "Connection refused" (Redis)
**Solution:**
1. Start Redis: `redis-server`
2. Or start Docker container: `docker start <redis-container-id>`

### Error: "OpenAI API authentication failed"
**Solution:** Verify your `OPENAI_API_KEY` in `.env`:
```bash
echo $env:OPENAI_API_KEY  # Should show your key
```

### Error: "Pinecone index not found"
**Solution:** The system auto-creates it, but you can create manually:
```python
from pinecone import Pinecone, ServerlessSpec
pc = Pinecone(api_key="your-key")
pc.create_index(
    name="community-vectors",
    dimension=1536,
    metric="cosine",
    spec=ServerlessSpec(cloud="aws", region="us-east-1")
)
```

### Error: "Task timeout" in Celery
**Solution:** First run might be slow due to cold-start. Wait 10 seconds and retry.

---

## Quick Start Script

For convenience, use the provided startup script:
```bash
.\start_system.bat
```

This will start all services in separate windows.

---

## Next Steps

Once everything is running:
1. ✅ Test with the example script: `python matching_system/test_example.py`
2. ✅ View API docs: http://localhost:8000/docs
3. ✅ Build your frontend to integrate with the API

---

## Development Tips

- **Logs:** Check Celery terminal for task execution logs
- **API Docs:** FastAPI auto-generates docs at `/docs`
- **Database:** Use `pgAdmin` or `psql` to inspect data
- **Redis:** Use `redis-cli` to check cache: `KEYS *`

---

## Still Having Issues?

Check the logs in this order:
1. FastAPI terminal - API errors
2. Celery terminal - Task processing errors  
3. Redis logs - Caching issues
4. PostgreSQL logs - Database errors

Most errors are due to:
- Missing environment variables
- Services not running
- Invalid API keys
- Database not initialized
