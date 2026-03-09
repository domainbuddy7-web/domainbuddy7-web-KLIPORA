# KLIPORA — Complete environment setup

One-place guide to get the full environment and n8n review flow running.

---

## 1. Mission Control API (already on Railway)

- URL: `https://domainbuddy7-web-klipora-production.up.railway.app`
- Env on Railway: `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`, `N8N_URL`, `N8N_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- No action needed if health returns `config_ok: true`.

---

## 2. Telegram Mission Console (run on your PC)

1. Use **`KEY=value.env`** in the repo root (or `.env`). See **HOW_TO_ENTER_KEYS.md**.
2. Set in that file:
   - `TELEGRAM_BOT_TOKEN` = from [@BotFather](https://t.me/BotFather)
   - `MISSION_CONTROL_URL` = `https://domainbuddy7-web-klipora-production.up.railway.app`
   - `OWNER_TELEGRAM_ID` or `TELEGRAM_CHAT_ID` = your Telegram user ID ([@userinfobot](https://t.me/userinfobot))
3. Run the bot:
   ```powershell
   cd E:\KLIPORA
   .\run_telegram_bot.ps1
   ```
   Or: set the 3 variables in `run_telegram_bot.ps1` and run it.
4. In Telegram: `/start`, then use panels: `/status`, `/videos`, `/finance`, etc.

---

## 3. n8n workflow (human-in-the-loop)

WF-ASSEMBLE has been updated in the repo so that when a video is ready it:
1. Saves the job to Redis as `pending_approve:{job_id}`
2. Calls Mission Control `POST /internal/notify-preview` so you get a Telegram message with **Approve & Publish / Regenerate / Edit Metadata / Discard**

### Option A — Upload via script (recommended)

1. In `.env` (or env) set:
   - `N8N_URL` = `https://n8n-production-2762.up.railway.app` (your n8n URL)
   - `N8N_API_KEY` = your n8n API key (n8n → Settings → API)
2. From repo root:
   ```powershell
   python scripts/upload_wf_assemble.py
   ```
3. If the script says "workflow not found", the workflow ID in the script may not match your n8n. Use Option B.

### Option B — Import manually in n8n

1. In n8n, open workflow **WF-ASSEMBLE** (Assembly & Publishing V2).
2. Remove the connection from **IF All Complete** (true branch) to **Call Railway Render**.
3. Add a **Code** node after **IF All Complete** (true):
   - Name: `Save pending_approve to Redis`
   - Code: (copy from `Automation/WF-ASSEMBLE.json` node `asm-save-pending` parameters.jsCode)
4. Add an **HTTP Request** node after that:
   - Method: POST
   - URL: `https://domainbuddy7-web-klipora-production.up.railway.app/internal/notify-preview`
   - Body (JSON): `{ "job_id": "{{ $json.job_id }}" }`
5. Connect: **IF All Complete** (true) → **Save pending_approve** → **Notify Preview**.
6. Save and activate.

---

## 4. Approve → Render

When you tap **Approve & Publish** in Telegram, the Mission Control API will:
- Call your **Railway Render** service with the job’s clips and voiceover so FFmpeg assembles the video and sends it to Telegram.
- Ensure `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set in Railway (they already are if you get run-cycle alerts). Optional: set `RAILWAY_RENDER_URL` in Railway if your render service URL is different.

---

## 5. Checklist

| Step | Done |
|------|------|
| Mission Control API live and healthy | ✓ |
| Telegram bot running locally with MISSION_CONTROL_URL | |
| WF-ASSEMBLE updated in n8n (script or manual) | |
| One test: generate a video → get review message → Approve | |

---

**One-shot run order:** see **COMPLETE_SETUP_TAKEOVER.md**.

For deployment and scheduling see **DEPLOY_NOW.md** and **AUTOMATION_SETUP.md**.
