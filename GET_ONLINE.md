# Get KLIPORA online (quick)

1. **Video pipeline (do this first)**  
   Follow **VIDEO_GENERATION_SETUP.md**: Mission Control live, Redis keys, n8n Groq key, WF-VIDEO/WF-ASSEMBLE active, then one test from Telegram.

2. **Run the Telegram bot**  
   From repo root:
   ```powershell
   .\run_telegram_bot.ps1
   ```
   Keep the window open. In Telegram: `/start` → tap **Video Factory** → **Generate Video** to test.

3. **Optional: reset webhook**  
   If the bot says "Conflict" or doesn’t receive updates:
   ```powershell
   $env:PYTHONPATH = (Get-Location).Path
   python scripts/reset_telegram_webhook.py
   ```
   Then start the bot again.

Mission Control API runs on Railway; the bot runs on your PC and talks to it. Keys go in `KEY=value.env` (see HOW_TO_ENTER_KEYS.md).
