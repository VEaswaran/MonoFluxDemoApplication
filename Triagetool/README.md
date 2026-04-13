# 🤖 MS Teams Issue Triage Bot

Interactive triage bot for Microsoft Teams.  
Collects issue details via guided Q&A → queries ELK → feeds logs to your refinement model → returns Root Cause Analysis.

---

## Architecture

```
Teams User
   │
   ▼
Azure Bot Framework  ←── app.py (webhook)
   │
   ▼
TriageBot (handlers/triage_bot.py)
   │
   ├─ SessionManager   → tracks per-user Q&A state
   ├─ ELKClient        → builds + executes Elasticsearch queries
   └─ ModelClient      → calls your refinement model API
```

---

## Conversation Flow

The bot is added to your **issue reporting channel**. No commands needed —
any new message posted there auto-starts a triage session.
All Q&A and the final report appear **inside the same thread** as the original post.

```
── Channel: #issue-reports ──────────────────────────────────────────────────

Reporter:  "Login button broken on Chrome after today's deployment"

  └─ Thread ──────────────────────────────────────────────────────────────

  Bot: 🚨 Issue Triage Started
       I'll ask you 6 quick questions. Type `skip` for optional fields.

  Bot: 🛠️ Step 1/6 — Which service or application is affected?
  Reporter: auth-service

  Bot: 🌍 Step 2/6 — Which environment? (prod / staging / dev)
  Reporter: prod

  Bot: 🕐 Step 3/6 — What time range? (e.g. 1h, 24h)
  Reporter: 2h

  Bot: 🔍 Step 4/6 — Error keyword?
  Reporter: JWT expired

  Bot: 🔗 Step 5/6 — Trace ID? (optional)
  Reporter: abc-123-xyz

  Bot: 👤 Step 6/6 — User/Team? (optional)
  Reporter: skip

  Bot: ✅ All details collected!
  Bot: 🔍 Querying ELK logs...
  Bot: 📊 Found 47 log entries. Running root cause analysis...
  Bot: ⚙️ Analyzing with refinement model...
  Bot: 🧠 Root Cause Analysis Report
       ───────────────────────────────
       [RCA output from your model]
```

Multiple reporters can post simultaneously — each gets their own isolated thread session.

---

## Setup

### 1. Register Azure Bot

1. Go to [Azure Portal](https://portal.azure.com) → Create **Azure Bot**
2. Note the **App ID** and generate an **App Password**
3. Set messaging endpoint to: `https://your-domain.com/api/messages`
4. Enable the **Microsoft Teams** channel

### 2. Configure Environment

```bash
cp .env.example .env
# Fill in your values in .env
```

### 3. Install & Run

```bash
pip install -r requirements.txt
python app.py
```

### 4. Expose Locally (Dev)

```bash
# Use ngrok to expose port 3978 for local testing
ngrok http 3978
# Set the ngrok URL as your bot's messaging endpoint in Azure Portal
```

### 5. Deploy to Production

Deploy to **Azure App Service** or **Azure Container Apps**:

```bash
# Azure App Service example
az webapp create --resource-group myRG --plan myPlan --name my-triage-bot --runtime "PYTHON:3.11"
az webapp config appsettings set --name my-triage-bot --resource-group myRG --settings @appsettings.json
```

---

## Adapting to Your Model

Edit `services/model_client.py`:

1. **`analyze()`** — adjust the request payload to match your model's input schema
2. **`_normalize()`** — map your model's response fields to the standard shape
3. **`format_rca_report()`** — customize the Teams message formatting

---

## Project Structure

```
teams-triage-bot/
├── app.py                        # Webhook entry point (aiohttp)
├── requirements.txt
├── .env.example
├── config/
│   ├── settings.py               # All env-based config
│   └── questions.py              # Triage Q&A template (edit here)
├── handlers/
│   └── triage_bot.py             # Azure Bot Framework activity handler
└── services/
    ├── session_manager.py        # Per-user session state
    ├── elk_client.py             # ELK query builder + API caller
    └── model_client.py           # Refinement model integration
```

---

## Commands Available in Chat

| Command | Action |
|---|---|
| `start` | Begin new triage session |
| `restart` | Reset current session |
| `skip` | Skip an optional question |
| `help` | Show help message |

---

## Customizing Questions

Edit `config/questions.py` to add, remove, or reorder questions.  
Each `TriageQuestion` supports:
- `key` — answer dict key
- `prompt` — message shown to user
- `hint` — shown on invalid input
- `skippable` — user can type `skip`
- `validator` — optional callable to validate input
