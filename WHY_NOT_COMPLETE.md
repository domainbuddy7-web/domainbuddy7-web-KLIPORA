# Why the project is still not complete

The **code and automation** are in place. What’s left are **credentials and one manual step** that only you can do (no one else can see or set your keys).

---

## 1. Telegram bot can’t connect (401)

- **What happens:** `reset_telegram_webhook.py` and the bot get **401 Unauthorized** from Telegram.
- **Cause:** `TELEGRAM_BOT_TOKEN` in `KEY=value.env` is missing, wrong, or still a placeholder.
- **Fix (you):**
  1. Open [@BotFather](https://t.me/BotFather) in Telegram → your bot → **API Token**.
  2. Copy the token (e.g. `7123456789:AAH...`).
  3. In `KEY=value.env` set exactly:  
     `TELEGRAM_BOT_TOKEN=7123456789:AAH...`  
     (no spaces, no quotes, one line).
  4. Run: `python scripts/reset_telegram_webhook.py` then `.\run_telegram_bot.ps1`.

Until this is correct, the bot cannot receive `/start` or **Generate Video**, so the project can’t be “complete” from the user’s perspective.

---

## 2. WF-GEN will fail until Groq key is set

- **What happens:** When you trigger **Generate Video**, WF-GEN runs but the **Generate Script** node returns **401** and no script is produced.
- **Cause:** That node calls Groq with a placeholder key; your real key is not set in n8n.
- **Fix (you):**
  1. [Groq Console](https://console.groq.com) → **API Keys** → create or copy a key (`gsk_...`).
  2. n8n → **Klipora WF-GEN — Content Generation V2** → open the **Generate Script** node.
  3. Set **Authorization** to: `Bearer gsk_your_actual_key_here`.
  4. Save the workflow.

Details: **N8N_GROQ_KEY.md**.

---

## 3. Optional: owner/chat ID

- For the bot to send *you* status and previews, `OWNER_TELEGRAM_ID` (or `TELEGRAM_CHAT_ID`) in `KEY=value.env` should be your Telegram user ID (e.g. `8232710919`), not a placeholder like `123456789`.

---

## Summary

| Blocker | Who can fix | Action |
|--------|-------------|--------|
| Telegram 401 | You | Put real `TELEGRAM_BOT_TOKEN` in `KEY=value.env`, then run webhook reset + bot. |
| WF-GEN 401 | You | In n8n, set Groq Bearer key in **Generate Script** node (see N8N_GROQ_KEY.md). |
| Owner ID | You | Set `OWNER_TELEGRAM_ID` to your Telegram user ID in `KEY=value.env`. |

**Already done:** Mission Control is live and healthy; WF-VIDEO and WF-ASSEMBLE are active; code, workflows, and docs are in place. The project is “not complete” only because these **secrets and one n8n field** must be filled by you.

After you set the token and Groq key (and optionally owner ID), run the bot and do **one test**: Telegram → **Video Factory** → **Generate Video**. That completes the setup.
