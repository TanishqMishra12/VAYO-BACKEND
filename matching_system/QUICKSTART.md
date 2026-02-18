# Quick Start - 5 Minutes to Running System

## Prerequisites Checklist
- [ ] Python 3.10+ installed
- [ ] PostgreSQL 16 installed
- [ ] Redis installed or Docker available
- [ ] OpenAI API key ready
- [ ] Pinecone API key ready (free tier)

---

## Step 1: Environment Setup (2 minutes)

```bash
# Navigate to project
cd "d:\code anti\matching_system"

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env
notepad .env  # Add your API keys
```

**Edit `.env` - Fill these 3 values:**
```
POSTGRES_PASSWORD=your_password
OPENAI_API_KEY=sk-your-key
PINECONE_API_KEY=your-key
```

---

## Step 2: Database Setup (1 minute)

```bash
# Create database
psql -U postgres -c "CREATE DATABASE community_matching;"

# Run setup script
psql -U postgres -d community_matching -f setup_database.sql
```

**Expected output:** "Communities created: 15"

---

## Step 3: Start Services (1 minute)

### Option A: Automatic (Windows)
```bash
.\start_system.bat
```

### Option B: Manual (3 terminals)
```bash
# Terminal 1: FastAPI
uvicorn matching_system.api:app --reload

# Terminal 2: Celery
celery -A matching_system.celery_tasks worker --pool=solo --loglevel=info

# Terminal 3: Redis (if needed)
redis-server
```

---

## Step 4: Test (1 minute)

### Browser Test
Open: http://localhost:8000/api/v1/health

Should show:
```json
{"status": "healthy", "postgres": "connected", "pinecone": "connected"}
```

### API Test
```bash
curl -X POST http://localhost:8000/api/v1/match -H "Content-Type: application/json" -d "{\"user_id\":\"test_123\",\"bio\":\"Python developer passionate about AI\",\"interest_tags\":[\"Python\",\"AI\"],\"city\":\"San Francisco\",\"timezone\":\"America/Los_Angeles\"}"
```

**Get results** (use task_id from above):
```bash
curl http://localhost:8000/api/v1/match/{your-task-id}
```

---

## Troubleshooting Quick Fixes

| Error | Fix |
|-------|-----|
| `ModuleNotFoundError` | Activate venv: `.\venv\Scripts\activate` |
| `Connection refused (PostgreSQL)` | Start PostgreSQL service in `services.msc` |
| `Connection refused (Redis)` | Run `redis-server` or `docker run -d -p 6379:6379 redis` |
| `OpenAI auth failed` | Check `.env` has correct `OPENAI_API_KEY` |
| `Celery not starting` | Use `--pool=solo` on Windows |

---

## What Next?

1. ✅ **Full Documentation:** See [SETUP_GUIDE.md](SETUP_GUIDE.md)
2. ✅ **Run Tests:** `python matching_system/test_example.py`
3. ✅ **API Docs:** http://localhost:8000/docs
4. ✅ **Architecture:** See [README.md](README.md)

---

## Common First-Run Issues

### "Pinecone index not found"
**Fix:** System auto-creates it on first run. Wait 30 seconds and retry.

### "Task timeout"
**Fix:** First OpenAI call is slow. Normal behavior, retry.

### "No matches found"
**Fix:** Sample data might not match your test query. Check database:
```sql
psql -U postgres -d community_matching -c "SELECT community_name, city FROM communities LIMIT 5;"
```

---

**You're ready!** The system should respond to match requests in <2 seconds. 🚀
