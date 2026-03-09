# Project 2 — Setup Steps (same Upstash + same Railway)

**Single environment:** Reuse the same Upstash Redis and same Railway. Project 2 uses Redis key prefix `p2:` so data is isolated.

---

## 1. Create Project 2 Telegram bot only

1. Telegram → [@BotFather](https://t.me/BotFather) → `/newbot` → name e.g. `Klipora P2 Bot`.  
2. Copy the **API Token** → put in `project2/KEY=value.env.project2` as `TELEGRAM_BOT_TOKEN`.  
3. [@userinfobot](https://t.me/userinfobot) → copy your **Id** → `TELEGRAM_CHAT_ID` and `OWNER_TELEGRAM_ID` in the same file.  
4. Copy **from Project 1** into `KEY=value.env.project2`: `MISSION_CONTROL_URL`, `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`, `N8N_URL`, `N8N_API_KEY` (same values).  
5. Add: `N8N_WEBHOOK_WF_GEN_P2=/webhook/wf-gen-p2`.

---

## 1.5 Optional: Initialize P2 Redis keys (once)

From repo root, run once so `p2:system:videos_per_day`, `p2:system:paused` (cleared), etc. are set:

```powershell
.\project2\run_setup_p2.ps1
```

If you skip this, the first **Run cycle** from the P2 bot (or Mission Control with `project_id=p2`) will set these via the CEO/CTO agents.

---

## 2. Railway — add one env var

1. Open your **existing** Railway service (Mission Control API).  
2. **Variables** → Add: **N8N_WEBHOOK_WF_GEN_P2** = `/webhook/wf-gen-p2`.  
3. Redeploy so the API uses this path when `project_id=p2` is sent.

---

## 3. n8n — import Project 2 workflows

1. Open your **same** n8n instance.  
2. Import from this repo:
   - `project2/Automation/WF-GEN-P2.json`
   - `project2/Automation/WF-VIDEO-P2.json`
   - `project2/Automation/WF-ASSEMBLE-P2.json`
3. WF-GEN-P2 webhook path will be **wf-gen-p2** (so full URL is `.../webhook/wf-gen-p2`).  
4. All three use the **same** Upstash URL/token as Project 1; keys are prefixed `p2:` inside the workflow.  
5. Set **Notify Preview** in WF-ASSEMBLE-P2 to your same Mission Control URL (it already sends `project_id: "p2"` in the body).  
6. Activate all three P2 workflows. Set schedule for WF-VIDEO-P2 and WF-ASSEMBLE-P2 (e.g. `0 8,16 * * 0-6` and `30 8,16 * * 0-6`).

---

## 4. Run the Project 2 bot locally

From repo root:

```powershell
.\project2\run_bot.ps1
```

This loads `project2\KEY=value.env.project2` and sets `PROJECT_ID=p2`. The bot sends `project_id=p2` to the API so Redis uses the `p2:` prefix. In Telegram, open your **Project 2** bot and send `/start`.

---

## 5. Fully unlocked

No plan limits or payment checks. Project 2 shares the same Mission Control, Redis, and n8n; only the Telegram bot and Redis keys (p2:*) are separate.
