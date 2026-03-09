# Project 2 — Open these URLs and capture credentials

**Use this as your single checklist.** Open each URL in your browser → log in if asked → copy the value into **KEY=value.env.project2** (create from `KEY=value.env.project2.example`). When you’re done, you’ll have all credentials in one file.

---

**Reuse same Upstash + same Railway.** Only create a **new Telegram bot**; copy the rest from Project 1 env (see section 2).

## 1. Telegram — create second bot and get your chat ID

| Step | URL / action | What to copy → env key |
|------|------------------|------------------------|
| 1a | Open **[t.me/BotFather](https://t.me/BotFather)** in Telegram | Send `/newbot`, follow name/username. Copy the **API Token** (e.g. `123456789:AAH...`) |
| 1b | Paste that token into `KEY=value.env.project2` | `TELEGRAM_BOT_TOKEN=<paste>` |
| 1c | Open **[t.me/userinfobot](https://t.me/userinfobot)** in Telegram | Send any message. Copy your **Id** (numeric, e.g. `8232710919`) |
| 1d | Paste that Id twice in env | `TELEGRAM_CHAT_ID=<paste>` and `OWNER_TELEGRAM_ID=<paste>` |

---

## 2. Upstash — second Redis database

| Step | URL / action | What to copy → env key |
|------|------------------|------------------------|
| 2a | Open **[console.upstash.com](https://console.upstash.com)** | Log in (or sign up). |
| 2b | Create database | Click **Create Database**. Name e.g. `klipora-project2`. Region: any. Create. |
| 2c | Open the new database → **REST API** tab | Copy **UPSTASH_REDIS_REST_URL** (starts with `https://`) |
| 2d | Same tab | Copy **UPSTASH_REDIS_REST_TOKEN** (Bearer token) |
| 2e | Paste into env | `UPSTASH_REDIS_REST_URL=<paste>` and `UPSTASH_REDIS_REST_TOKEN=<paste>` |

---

## 3. n8n — URL and API key

| Step | URL / action | What to copy → env key |
|------|------------------|------------------------|
| 3a | Open your **n8n** in the browser | Same as main KLIPORA (e.g. `https://n8n-production-xxxx.up.railway.app`) or a second n8n URL. |
| 3b | Paste base URL (no trailing slash) into env | `N8N_URL=<paste>` |
| 3c | In n8n: **Settings** (gear) → **API** | Create API key (or copy existing). Copy the key (long string or JWT). |
| 3d | Paste into env | `N8N_API_KEY=<paste>` |

---

## 4. Railway — Mission Control URL for Project 2

| Step | URL / action | What to copy → env key |
|------|------------------|------------------------|
| 4a | Open **[railway.app](https://railway.app)** | Log in. |
| 4b | Create **new project** (or use existing) → **New** → **GitHub Repo** | Select this repo. Add a **service** that runs the API (e.g. `python start_api.py` or your Dockerfile). |
| 4c | In the new service: **Variables** | Add all vars from `KEY=value.env.project2.example` (Telegram, Upstash, n8n for **Project 2**). Deploy. |
| 4d | **Settings** → **Networking** → **Generate domain** | Copy the public URL (e.g. `https://xxx.up.railway.app`). |
| 4e | Paste into env | `MISSION_CONTROL_URL=<paste>` (and update Railway’s own `MISSION_CONTROL_URL` if you use it there). |

---

## 5. Wavespeed (optional — only if second API key)

| Step | URL / action | What to copy |
|------|------------------|--------------|
| 5a | Open **[wavespeed.ai](https://wavespeed.ai)** (or your Wavespeed dashboard) | Log in. |
| 5b | **API Keys** (or similar) | If you create a **second** key for Project 2, copy it. |
| 5c | In **n8n** WF-VIDEO-P2 and WF-ASSEMBLE-P2 | In each HTTP node that calls Wavespeed, set **Authorization** to `Bearer <new key>`. (If you use the same key as main, skip this.) |

---

## After you’re done

1. Save **KEY=value.env.project2** in the `project2/` folder.  
2. Follow **SETUP_STEPS.md** (add N8N_WEBHOOK_WF_GEN_P2 in Railway; import project2/Automation workflows in n8n).  
3. Run the bot: from repo root, `.\project2\run_bot.ps1`.  
4. In Telegram, open your **Project 2** bot and send `/start`. You’re hands-free from here for daily use.

---

**Note:** I can’t open your browser from here. Open the links above in order; once you’re logged in, copy the values into **KEY=value.env.project2** as in the table. If you tell me “I’m on the Upstash page” or “I’ve filled the env file,” I can guide the next step (e.g. n8n workflow changes or Railway variables).
