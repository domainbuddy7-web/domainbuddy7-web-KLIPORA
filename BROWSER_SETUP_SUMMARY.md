# Browser setup summary

Automated checks and browser steps that were run (with you logged into n8n):

## Verified (browser + API)

- **Mission Control**
  - Opened: `https://domainbuddy7-web-klipora-production.up.railway.app/health`
  - Result: `{"status":"ok","config_ok":true}`
  - Opened: `https://domainbuddy7-web-klipora-production.up.railway.app/health/system`
  - Result: `status: "HEALTHY"`, queues empty, no n8n failures

- **n8n (logged in)**
  - **WF-VIDEO** — Opened workflow; **Active** (Deactivate button visible).
  - **WF-ASSEMBLE** — Opened via command palette; **Active** (Deactivate button visible).
  - WF-GEN: Groq key must be set manually in the "Generate Script" node (Bearer `gsk_...`); see N8N_GROQ_KEY.md.

## Could not complete (needs you)

1. **Telegram webhook reset**  
   `python scripts/reset_telegram_webhook.py` returned **401 Unauthorized**.  
   → Check `TELEGRAM_BOT_TOKEN` in `KEY=value.env`: it must be the real bot token from [@BotFather](https://t.me/BotFather). No spaces or quotes.

2. **n8n setup**  
   In the browser, after logging into n8n:
   - Add Groq API key in WF-GEN (“Generate Script” node).
   - Ensure WF-VIDEO and WF-ASSEMBLE are **Active**.
   - See **VIDEO_GENERATION_SETUP.md** for the full checklist.

3. **Run the bot**  
   After fixing the token and (optionally) resetting the webhook:
   ```powershell
   .\run_telegram_bot.ps1
   ```
   Then in Telegram: `/start` → **Video Factory** → **Generate Video**.

## Quick links

| Page | URL |
|------|-----|
| Mission Control health | https://domainbuddy7-web-klipora-production.up.railway.app/health |
| Mission Control system | https://domainbuddy7-web-klipora-production.up.railway.app/health/system |
| n8n workflows | https://n8n-production-2762.up.railway.app/workflows |
