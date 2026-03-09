# Railway account analysis — use existing services for KLIPORA

This doc summarizes **what KLIPORA already uses** on Railway and **how to check your other instances** so you can reuse or consolidate them.

---

## What the project currently uses (from codebase)

| Role | Current URL / env | Used by |
|------|-------------------|--------|
| **Mission Control API** | `https://domainbuddy7-web-klipora-production.up.railway.app` | Bot (`MISSION_CONTROL_URL`), WF-ASSEMBLE (notify-preview), health checks |
| **n8n** | `https://n8n-production-2762.up.railway.app` | Workflows (WF-GEN, WF-VIDEO, WF-ASSEMBLE), Mission Control (`N8N_URL`, `N8N_API_KEY`) |
| **Render (FFmpeg)** | `https://klipora-render-service-production.up.railway.app` | Mission Control + WF-ASSEMBLE (`RAILWAY_RENDER_URL`) |

**Other infra (not necessarily on Railway):**

- **Redis**: Upstash (`wealthy-hyena-4511.upstash.io` in workflows) — can be Railway Redis or stay Upstash.
- **Telegram bot**: runs on your PC; only needs `MISSION_CONTROL_URL` and token.

So today you have **at least 3 Railway services** in use: one API (Mission Control), one n8n, one render service.

---

## How to list your Railway instances and environments

You can do either **A** (CLI) or **B** (dashboard).

### A. Railway CLI (if installed)

From a terminal (PowerShell or bash):

```bash
# Login if needed
railway login

# List all projects (shows project names and which is linked)
railway list

# For each project you care about: link, then show services and env
railway link   # pick project
railway status
railway service status --all
```

To get URLs: in the [Railway dashboard](https://railway.app/dashboard) → Project → Service → **Settings** → **Networking** → **Public networking** (generate domain if needed). The public URL is what you’d use for `MISSION_CONTROL_URL`, `N8N_URL`, or `RAILWAY_RENDER_URL`.

### B. Railway dashboard (manual)

1. Open **[railway.app/dashboard](https://railway.app/dashboard)** and log in.
2. Note **each project** and, inside each project, **each service** (e.g. “web”, “n8n”, “render”, “api”).
3. For each service, open **Settings** → **Networking** and note the **public URL** (e.g. `https://something.up.railway.app`).
4. Optionally note **environments** (e.g. Production vs Staging) if you use more than one.

Use the table in the next section to map what you see to KLIPORA.

---

## How existing services can be used in KLIPORA

| If you see in Railway… | Possible use in KLIPORA | Where to set it |
|------------------------|-------------------------|------------------|
| **Web/API service** (Python, Node, etc.) | Mission Control API (replaces or backs up `domainbuddy7-web-klipora-production`) | `MISSION_CONTROL_URL` in bot env; deploy this repo’s API there |
| **n8n** (already have `n8n-production-2762`) | Keep using it; no change | `N8N_URL` / `N8N_API_KEY` on Mission Control and in bot/docs |
| **Another n8n** (different project) | Use as secondary or replace current n8n | Same env vars; update workflows to call the chosen n8n URL |
| **Service that runs FFmpeg / video render** | Render service for final video assembly | `RAILWAY_RENDER_URL` in Mission Control and in n8n (WF-ASSEMBLE) |
| **Redis** (Railway Redis plugin) | Optional: replace Upstash for queues/flags | `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN` on Mission Control (or adapt code to Railway Redis client) |
| **Cron / scheduler** | Could trigger run-cycle or WF-VIDEO instead of n8n schedule | Call `POST /commands/run-cycle` or n8n webhook on a schedule |
| **Static site / frontend** | Future dashboard or status page | Point it at Mission Control API (`/health`, `/health/system`) |
| **Duplicate of Mission Control** (same code, different project) | Staging or backup API | Use its URL as `MISSION_CONTROL_URL` for testing or failover |

---

## What to do after you have the list

1. **Fill the “Current use” column** in the table below (or in a copy of this file) with your real service names and URLs from the dashboard/CLI.
2. **Decide** which service is Mission Control, which is n8n, which is render (if any).
3. **Update env only where needed:**
   - Bot / `KEY=value.env`: `MISSION_CONTROL_URL` (and optionally `N8N_URL` if something calls n8n from your machine).
   - Mission Control (Railway env for the API service): `N8N_URL`, `N8N_API_KEY`, `RAILWAY_RENDER_URL`, Redis vars.
   - n8n (WF-ASSEMBLE): notify-preview URL = Mission Control URL + `/internal/notify-preview`; render URL = `RAILWAY_RENDER_URL` or default in workflow.

If you paste your list of projects/services/URLs (with secrets redacted), we can map them exactly to KLIPORA and suggest minimal config changes.

---

## Optional: run the helper script

From the repo root:

```powershell
.\scripts\list_railway_services.ps1
```

If Railway CLI is installed and linked, it will try to print project/service info. Otherwise it prints the dashboard steps above. You can then use the output to fill the “Current use” table and decide what to reuse.
