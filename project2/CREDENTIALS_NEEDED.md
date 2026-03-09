# Project 2 — Credentials checklist (single Upstash + Railway)

**Reuse the same Upstash and Railway.** Only create a **new Telegram bot** for Project 2.

| Credential | Where | Env key |
|------------|--------|---------|
| **Telegram bot token** (new) | [@BotFather](https://t.me/BotFather) → new bot → API Token | `TELEGRAM_BOT_TOKEN` |
| **Your Telegram chat ID** | [@userinfobot](https://t.me/userinfobot) → Id | `TELEGRAM_CHAT_ID`, `OWNER_TELEGRAM_ID` |
| Mission Control URL | **Copy from Project 1** (same Railway) | `MISSION_CONTROL_URL` |
| Upstash Redis URL | **Copy from Project 1** (same DB) | `UPSTASH_REDIS_REST_URL` |
| Upstash Redis token | **Copy from Project 1** | `UPSTASH_REDIS_REST_TOKEN` |
| n8n URL | **Copy from Project 1** | `N8N_URL` |
| n8n API key | **Copy from Project 1** | `N8N_API_KEY` |
| P2 webhook path | Set to `/webhook/wf-gen-p2` | `N8N_WEBHOOK_WF_GEN_P2` |

Create **KEY=value.env.project2** from **KEY=value.env.project2.example**. Add **N8N_WEBHOOK_WF_GEN_P2** in Railway Variables for the existing Mission Control service. No website or app — everything runs via Telegram + n8n + Railway + Upstash.
