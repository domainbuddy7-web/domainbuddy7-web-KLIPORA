# KLIPORA — Hands-off automation setup

One-time setup so the company loop runs automatically. Pick **one** option.

---

## Option 1: GitHub Actions (recommended — no extra service)

The repo includes a workflow that calls your Mission Control API every 6 hours. You only add one secret.

### One-time setup

1. Open your repo: **https://github.com/domainbuddy7-web/domainbuddy7-web-KLIPORA**
2. Go to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
   - **Name:** `MISSION_CONTROL_URL`
   - **Value:** `https://domainbuddy7-web-klipora-production.up.railway.app`  
     (no trailing slash)
4. Save. Push the latest code (with `.github/workflows/run-klipora-cycle.yml`) if you haven't already.

### What runs

- **Schedule:** **2 times per day only** — 12:00 noon and 8:00 PM UAE time (08:00 and 16:00 UTC). Keeps credits and social flags under control.
- **Action:** `POST https://.../commands/run-cycle` (CEO → CTO → Operations cycle)
- **Manual run:** In the repo go to **Actions** → **Run KLIPORA cycle** → **Run workflow** (use this to run once now without waiting for the schedule)

No new service; runs inside GitHub. Fully hands-off after the secret is set.

---

## Option 2: cron-job.org (free external cron)

No code in the repo; a third-party service calls your API on a schedule.

### One-time setup

1. Go to **https://cron-job.org** and create a free account.
2. Create a new cron job:
   - **Title:** KLIPORA run-cycle
   - **URL:** `https://domainbuddy7-web-klipora-production.up.railway.app/commands/run-cycle`
   - **Request method:** POST
   - **Schedule:** e.g. every 6 hours or daily
3. Save. They will POST to your API on the chosen schedule.

Hands-off after this; no GitHub changes needed.

---

## Option 3: n8n (you already have it)

Use your existing n8n instance to trigger the cycle on a schedule.

### One-time setup

1. In n8n, create a new workflow.
2. Add a **Schedule Trigger** node (e.g. every 6 hours or "At 8:00" daily).
3. Add an **HTTP Request** node:
   - **Method:** POST
   - **URL:** `https://domainbuddy7-web-klipora-production.up.railway.app/commands/run-cycle`
   - **Headers:** (none required unless you add API auth later)
4. Save and **Activate** the workflow.

Hands-off after activation; n8n runs on Railway so it's in the same ecosystem.

---

## Summary

| Option           | Setup steps                          | Runs in        |
|------------------|--------------------------------------|----------------|
| GitHub Actions   | Add 1 secret, push workflow          | GitHub         |
| cron-job.org     | 1 account, 1 cron job                | Their servers  |
| n8n              | 1 workflow (Schedule + HTTP Request) | Your n8n       |

After setup, automation runs without you; no need to "start" it each time.

---

## Telegram Command Center bot (owner control panel)

A full menu-driven bot lives in `Command_Center/telegram_command_center.py`. It provides:

- **Main menu:** Generate Video, System Status, Revenue, Experiment Lab, Opportunity Radar, Automation Control, Finance, Settings, Pause System
- **Video wizard:** Genre → Visual style → Narration → Duration → Aspect ratio → Confirm (calls Mission Control API)
- **System Status / Revenue / Finance:** Live data from the API
- **Automation:** Run cycle, Pause, Resume, Diagnostics
- **Owner-only:** set `OWNER_TELEGRAM_ID` or `TELEGRAM_CHAT_ID` so only you can use it

### Run the bot (local or a second Railway service)

```bash
# From repo root, with env vars set:
set TELEGRAM_BOT_TOKEN=your_bot_token
set MISSION_CONTROL_URL=https://domainbuddy7-web-klipora-production.up.railway.app
set OWNER_TELEGRAM_ID=your_telegram_user_id
# Optional, for wizard state: UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN

python -m Command_Center.telegram_command_center
```

The bot uses long polling; no webhook required. Run it on a VPS or a second Railway worker so it stays online.
