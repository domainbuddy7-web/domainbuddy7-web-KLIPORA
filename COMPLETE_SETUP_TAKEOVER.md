# KLIPORA — Complete setup (one-shot run order)

**Video first?** → See **VIDEO_GENERATION_SETUP.md** for the pipeline (WF-GEN → WF-VIDEO → WF-ASSEMBLE) and Groq/n8n checks.

Use this as the single checklist to get everything running. Run steps in order.

---

## Pre-check: keys file

- **File:** `KEY=value.env` in repo root (or `.env`).
- **Required lines:** `TELEGRAM_BOT_TOKEN`, `MISSION_CONTROL_URL`, `OWNER_TELEGRAM_ID` (or `TELEGRAM_CHAT_ID`).
- Format: one key per line, `KEY=value`, no spaces around `=`. See **HOW_TO_ENTER_KEYS.md**.

---

## 1. Mission Control API (Railway)

- **URL:** `https://domainbuddy7-web-klipora-production.up.railway.app`
- **Verify:** Open in browser or run:
  ```powershell
  Invoke-RestMethod -Uri 'https://domainbuddy7-web-klipora-production.up.railway.app/health' -Method Get
  Invoke-RestMethod -Uri 'https://domainbuddy7-web-klipora-production.up.railway.app/health/system' -Method Get
  ```
- **Expected:** `config_ok: true` on `/health`; `status: HEALTHY` on `/health/system`.
- **If 503 / unhealthy:** Set in Railway → Variables: `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`, `N8N_URL`, then redeploy.

---

## 2. Reset Telegram webhook (optional but recommended)

So the Python bot can use long polling (no conflict with n8n webhook):

```powershell
cd E:\KLIPORA
$env:PYTHONPATH = "E:\KLIPORA"
python scripts/reset_telegram_webhook.py
```

- **Expected:** "Webhook cleared. Response: ..."
- **If 401:** Telegram token invalid or wrong. Check `TELEGRAM_BOT_TOKEN` in `KEY=value.env` (from [@BotFather](https://t.me/BotFather)); ensure no duplicate/placeholder line overwrites it.

---

## 3. Run the Telegram bot

```powershell
cd E:\KLIPORA
.\run_telegram_bot.ps1
```

- **Expected:** Bot starts (no crash). In Telegram: `/start`, then `/status` — you should see **KLIPORA SYSTEM STATUS** with Redis/n8n and queues.
- **If "Could not reach Mission Control API":** Bot can’t reach Railway (timeout/blocked). Message now includes a reason; fix network or run from a machine that can reach the API.
- **If "Unauthorized":** Set `OWNER_TELEGRAM_ID` (or `TELEGRAM_CHAT_ID`) to your numeric Telegram ID ([@userinfobot](https://t.me/userinfobot)).
- **If "Conflict: terminated by other getUpdates":** Only one process can use the bot (one Python bot **or** n8n webhook, not both). Stop the other bot process, or clear the webhook with `python scripts/reset_telegram_webhook.py` so the Python bot can poll.

---

## 4. n8n workflows

- **WF-GEN:** Set **Groq API key** in the “Generate Script” node (see **N8N_GROQ_KEY.md**).
- **WF-VIDEO:** Uses Wavespeed; keys are in workflow JSON. Activity shows in Wavespeed only when jobs run (time window 12:00–20:00 UTC+4, max 2/day). See **N8N_WAVESPEED_ACTIVITY.md**.
- **WF-ASSEMBLE:** For review flow, ensure “Save pending_approve to Redis” and “Notify Preview” (POST to Mission Control `/internal/notify-preview`) are present. Import from `Automation/WF-ASSEMBLE.json` or update manually (see **N8N_REVIEW_FLOW.md**).
- **Upload WF-ASSEMBLE via script (optional):** Set `N8N_URL` and `N8N_API_KEY` in `KEY=value.env`, then:
  ```powershell
  .\RUN_UPLOAD_WORKFLOW.ps1
  ```
  If 401, create/copy API key in n8n → Settings → API.

---

## 5. Quick verification checklist

| Step | Command / action | Expected |
|------|------------------|----------|
| API root | Open `https://domainbuddy7-web-klipora-production.up.railway.app/` | JSON with `service`, `config_ok` |
| API health/system | Open `.../health/system` | JSON with `status`, `flags`, `queues` |
| Webhook reset | `python scripts/reset_telegram_webhook.py` | "Webhook cleared" (or 401 → fix token) |
| Bot run | `.\run_telegram_bot.ps1` | Process runs; Telegram `/status` shows panel |
| One video test | Telegram → Generate (genre/style) → Confirm | Script ready message, then (in time window) video pipeline runs |

---

## 6. Where things live

- **Mission Control API:** Railway (auto-deploys on push to `main`).
- **Telegram bot:** Your PC — `run_telegram_bot.ps1`; keys from `KEY=value.env`.
- **n8n:** Railway (or your instance); workflows in repo `Automation/*.json`.
- **Redis:** Upstash; used by Mission Control and n8n (queues, flags).
- **Docs:** `SETUP_COMPLETE.md`, `DEPLOY_NOW.md`, `N8N_GROQ_KEY.md`, `N8N_REVIEW_FLOW.md`, `N8N_WAVESPEED_ACTIVITY.md`, `HOW_TO_ENTER_KEYS.md`.

---

*Last takeover run: verified API healthy; webhook reset returned 401 (check token); bot run script and docs aligned to KEY=value.env.*
