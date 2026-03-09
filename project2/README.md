# KLIPORA Project 2 — Fully Unlocked (Same Architecture)

Second project: **same stack as KLIPORA** — Telegram frontend, n8n + Upstash + Railway + Git backend. Fully unlocked (no payment, no subscription). No website or mobile app.

---

## Architecture (identical to main KLIPORA)

| Layer | What |
|-------|------|
| **Frontend** | Telegram (second bot) |
| **Backend** | n8n (workflows), Upstash Redis (second DB), Railway (Mission Control API + n8n + Render) |
| **Git** | Same repo; this folder + env file |

Flow: Telegram → Mission Control API → WF-GEN (n8n) → script_queue → WF-VIDEO (Wavespeed) → render_queue → WF-ASSEMBLE → pending_approve → Telegram review → Approve → Railway Render (FFmpeg) → video to Telegram.

---

## What you need (single Upstash + Railway)

**Reuse the same Upstash and same Railway** (one free-tier environment). Project 2 uses a **Redis key prefix** `p2:` so both projects share one database without overwriting each other.

- **Telegram:** **New** bot (BotFather) → token + your chat ID (Project 2 bot only)  
- **Upstash:** **Same** as Project 1 — no second database.  
- **Railway:** **Same** Mission Control API URL as Project 1.  
- **n8n:** **Same** instance. Import **Project 2 workflows** from `project2/Automation/` (WF-GEN-P2, WF-VIDEO-P2, WF-ASSEMBLE-P2); they use `p2:` keys.  
- **Wavespeed:** Same API key as Project 1 (shared).  

Set **N8N_WEBHOOK_WF_GEN_P2** in Railway (and in project2 env when running the bot locally) to the webhook path of WF-GEN-P2 (e.g. `/webhook/wf-gen-p2`).  

All steps and **exact URLs + what to copy** are in **OPEN_THESE_URLS.md**. Use **KEY=value.env.project2.example** to create your local env file.

---

## Run the Project 2 Telegram bot (local)

From repo root (`E:\KLIPORA`):

```powershell
.\project2\run_bot.ps1
```

This loads `project2\KEY=value.env.project2` (create from `.example`) and runs the same Telegram bot code with Project 2 credentials. **First time (optional):** run `.\project2\run_setup_p2.ps1` once to initialize `p2:` Redis keys (videos_per_day, clear paused, etc.).

---

## Deploy (same Railway)

**No second Railway service.** Use the **same** Mission Control API. Add one env var for Project 2:

- **N8N_WEBHOOK_WF_GEN_P2** = `/webhook/wf-gen-p2` (so the API triggers WF-GEN-P2 when `project_id=p2`).  

In n8n, import the three workflows from **project2/Automation/** (WF-GEN-P2, WF-VIDEO-P2, WF-ASSEMBLE-P2), activate them, and set the same schedule as Project 1. Step-by-step: **SETUP_STEPS.md**.
