# 🤖 AutoProspect AI

## 📸 Screenshots

### Dashboard
![Dashboard](screenshots/dashboard.png)

### Leads Database
![Leads](screenshots/leads.png)

### New Campaign
![Campaign](screenshots/campaign.png)

### Messages
![Messages](screenshots/messages.png)
> AI-powered B2B lead generation & outreach automation.
> LangGraph multi-agent pipeline · FastAPI · Supabase · n8n · Streamlit

---

## What It Does

1. **Finds** companies matching your Ideal Customer Profile (Apollo.io + Google Maps)
2. **Enriches** them with emails, contact names, company context (Hunter.io + web scraper)
3. **Scores** each lead hot / warm / cold using rules + GPT-4o-mini validation
4. **Writes** personalized 3-email sequences with GPT-4o (hot) or GPT-4o-mini (warm)
5. **Sends** emails via Gmail API with human-like delays and A/B subject testing
6. **Tracks** replies via n8n Gmail trigger and schedules follow-ups automatically
7. **Learns** which ICP attributes and messages convert best

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys

# Generate secure API keys
python scripts/generate_api_key.py
# Paste the output into your .env
```

### 3. Set up database

Run `database/schema.sql` in your Supabase SQL Editor.

### 4. Set up Gmail

```bash
python scripts/setup_gmail.py
```

Follow the OAuth prompt. `token.json` will be saved to project root.

### 5. Run

```bash
# Start FastAPI backend
uvicorn api.main:app --reload

# In a second terminal — start Streamlit dashboard
streamlit run dashboard/app.py

# Optional: test the pipeline (no emails sent)
python scripts/test_pipeline.py --dry-run
```

---

## API Authentication

All API endpoints require `X-API-Key` header:

```bash
curl -X POST http://localhost:8000/api/campaigns/create \
  -H "X-API-Key: your-api-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test", "icp": {...}, ...}'
```

n8n webhook endpoints require `X-Webhook-Secret` header instead.

---

## Project Structure

```
autoprospect-ai/
├── agents/
│   ├── graph.py           ← LangGraph state machine (entry point)
│   ├── lead_finder.py     ← Apollo.io + Google Maps
│   ├── lead_enricher.py   ← Hunter.io + web scraper + LLM summarizer
│   ├── lead_scorer.py     ← Rule engine + LLM borderline validator
│   ├── copywriter.py      ← GPT-4o email generator + A/B subject
│   ├── outreach.py        ← Gmail sender with daily limits
│   └── analytics.py       ← Stats tracker + DB persistence
├── api/
│   ├── main.py            ← FastAPI app (rate limiting, CORS, error handling)
│   └── routes/
│       ├── campaigns.py   ← Campaign CRUD + run triggers
│       └── leads.py       ← Lead queries + follow-up + CSV export
├── tools/
│   ├── apollo.py          ← Apollo.io API client
│   ├── hunter.py          ← Hunter.io email finder
│   ├── gmail.py           ← Gmail API sender/reader
│   ├── scraper.py         ← httpx + BeautifulSoup + Playwright
│   └── supabase_client.py ← Supabase singleton client
├── models/schemas.py      ← Pydantic request/response models
├── utils/
│   ├── auth.py            ← API key + webhook secret auth
│   ├── logger.py          ← Loguru logger
│   └── retry.py           ← Async retry with exponential backoff
├── dashboard/app.py       ← Streamlit UI (5 pages)
├── database/schema.sql    ← Full Supabase schema
├── n8n_workflows/         ← Ready-to-import n8n JSON files
├── scripts/
│   ├── setup_gmail.py     ← Gmail OAuth setup
│   ├── test_pipeline.py   ← End-to-end test (--dry-run flag)
│   └── generate_api_key.py← Generate secure secrets
├── config.py              ← Pydantic settings (env vars)
├── .env.example           ← Environment variable template
├── requirements.txt
├── Procfile               ← Railway deployment
└── railway.toml
```

---

## Deployment (Railway)

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway up

# Set environment variables in Railway dashboard
# Copy all keys from your .env file
```

**Important:** Set `ALLOWED_ORIGINS` in Railway to your actual frontend domain, not `*`.

---

## n8n Workflows

Import the JSON files from `n8n_workflows/` into your n8n instance:

| File | Purpose |
|------|---------|
| `campaign_runner.json` | Runs all active campaigns at 9 AM weekdays |
| `reply_detector.json` | Polls Gmail every minute, marks replied leads |
| `followup_scheduler.json` | Sends day-3 follow-ups at 10 AM weekdays |

**n8n env vars required:**
- `BACKEND_URL` — your Railway backend URL
- `N8N_WEBHOOK_SECRET` — from your `.env`

---

## Cost Estimates

| Service | Usage | Cost |
|---------|-------|------|
| OpenAI (GPT-4o + 4o-mini) | 500 leads/day | ~$2.50/day |
| Apollo.io | 1,500 credits/mo (free tier) | $0 |
| Hunter.io | 25 searches/mo (free tier) | $0 |
| Railway (backend + n8n) | Always-on | ~$10/mo |
| Supabase | Free tier | $0 |
| **Total** | | **~$85/mo** |

Margin at $300/mo/client: **71%**. At $500/mo: **83%**.

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key | ✅ |
| `APOLLO_API_KEY` | Apollo.io API key | ✅ |
| `HUNTER_API_KEY` | Hunter.io API key | ✅ |
| `GOOGLE_MAPS_API_KEY` | Google Places API key | Optional |
| `SUPABASE_URL` | Supabase project URL | ✅ |
| `SUPABASE_KEY` | Supabase **service role** key | ✅ |
| `API_SECRET_KEY` | API authentication key | ✅ |
| `N8N_WEBHOOK_SECRET` | n8n webhook authentication | ✅ |
| `REDIS_URL` | Redis URL (for Celery) | Optional |
| `ALLOWED_ORIGINS` | CORS origins (comma-separated) | Production |

> ⚠️ **Use the service role key for `SUPABASE_KEY`**, not the anon key. The anon key is for frontend clients only.
