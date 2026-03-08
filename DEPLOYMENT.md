# KLIPORA Deployment (Railway)

This guide covers deploying the **Mission Control API** (dashboard backend) and optional **orchestrator** to Railway so you can access the control panel from anywhere (phone, laptop) without keeping your PC on.

## What Gets Deployed

| Service | Description | Repo entrypoint |
|--------|-------------|------------------|
| **Mission Control API** | FastAPI dashboard backend: health, production, finance, events, commands | `Dockerfile` → `uvicorn Command_Center.dashboard_api:app` |
| **Orchestrator** (optional) | Run `run_company.py` on a schedule (cron / Railway cron job) | Not in Dockerfile; run separately or add a second service |

The existing **n8n**, **Render Service**, and **Upstash Redis** are already on Railway/Upstash; this deployment adds the **Python Command Center** layer.

---

## 1. Mission Control API on Railway

### 1.1 Connect repository

1. Go to [Railway](https://railway.app) → your project (or create one).
2. **New** → **GitHub Repo** (or **GitHub Repo** from existing project).
3. Select the repo containing KLIPORA (with `Dockerfile` and `Command_Center/` at the root).

### 1.2 Configure the service

- **Root directory**: leave default (repo root).
- **Build**: Railway will detect the `Dockerfile` and build the image.
- **Start command**: leave default (Dockerfile `CMD` runs the API).

### 1.3 Set environment variables

In Railway → your service → **Variables**, add:

| Variable | Description | Example |
|----------|-------------|--------|
| `UPSTASH_REDIS_REST_URL` | Upstash Redis REST URL | `https://wealthy-hyena-4511.upstash.io` |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash Redis REST token | (from Upstash dashboard or `Infrastructure/config.json`) |
| `N8N_URL` | n8n instance URL | `https://n8n-production-2762.up.railway.app` |
| `N8N_API_KEY` | n8n API key (for workflow/execution APIs) | (from Section 3F in KLIPORA_CREWAI_HANDOFF) |

- **PORT** is set by Railway automatically; the Dockerfile uses it.

You can copy `upstash_url` / `upstash_token` from `E:\KLIPORA\Infrastructure\config.json` into `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN` (same values).

### 1.4 Deploy and get URL

- **Deploy** the service. Railway will build the image and start the container.
- In **Settings** → **Networking** → **Generate domain**. You’ll get a URL like:
  - `https://klipora-control.up.railway.app`  
  or  
  - `https://<service-name>.up.railway.app`

### 1.5 Verify

- Open `https://<your-domain>/` → should return JSON: `{"service": "KLIPORA Mission Control API", ...}`.
- Try `https://<your-domain>/health/system` → system health snapshot (Redis + n8n).
- Try `https://<your-domain>/events` → event stream (may be empty at first).

---

## 2. Optional: Run orchestrator on a schedule

The **orchestrator** (`run_company.py`) runs one cycle: CEO aligns plan → CTO health check → Operations production cycle. To run it periodically in the cloud:

**Option A — Railway cron (if available)**  
- Add a second service or a cron job that runs:
  - `python run_company.py`
  with the same env vars and PYTHONPATH so that `Infrastructure` and `Command_Center` resolve.

**Option B — External cron (e.g. cron-job.org)**  
- Call **`POST https://<your-domain>/commands/run-cycle`** (no body). The API runs one full cycle (CEO → CTO → Operations) and returns health + production summary.

**Option C — n8n schedule**  
- Create an n8n workflow triggered on a schedule (e.g. every 6 hours). Add an HTTP Request node: **POST** `https://<your-domain>/commands/run-cycle`. No auth by default; add an API key header if you later secure the endpoint.

---

## 3. Local run (no Docker)

From the repo root (e.g. `E:\KLIPORA`):

```bash
# Optional: set env vars if you don't have config.json
# set UPSTASH_REDIS_REST_URL=...
# set UPSTASH_REDIS_REST_TOKEN=...
# set N8N_URL=...
# set N8N_API_KEY=...

pip install -r requirements.txt
set PYTHONPATH=%CD%
uvicorn Command_Center.dashboard_api:app --reload --port 8000
```

Then open `http://localhost:8000/` and `/health/system`, `/events`, etc.

---

## 4. Security notes

- **Secrets**: Never commit `Infrastructure/config.json` with real tokens to a public repo. Use Railway (and env) for production.
- **Dashboard**: The API has no auth by default. For a public URL, add authentication (e.g. API key header or OAuth) or restrict access (e.g. VPN / IP allowlist).
- **CORS**: `dashboard_api.py` currently allows all origins; tighten `allow_origins` to your frontend domain (e.g. `https://dashboard.klipora.ai`) when you add the React/Next.js UI.

---

## 5. Troubleshooting

| Issue | Check |
|-------|--------|
| Build fails | Ensure `Dockerfile` and `requirements.txt` are at repo root and `COPY . /app` includes `Command_Center`, `Infrastructure`, `Agents`. |
| Module not found (e.g. `Infrastructure`) | `PYTHONPATH` must include the app root; Dockerfile sets `ENV PYTHONPATH=/app`. |
| Redis/n8n connection errors | Verify `UPSTASH_REDIS_REST_*` and `N8N_URL` / `N8N_API_KEY` in Railway Variables. |
| PORT not used | Railway sets `PORT`; the Dockerfile CMD uses `sh -c '... ${PORT:-8000}'`. |

---

## Summary

1. Push the repo (with `Dockerfile`, `requirements.txt`, env-based config) to GitHub.
2. In Railway, create a service from that repo, set `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN`, `N8N_URL`, `N8N_API_KEY`.
3. Deploy and open the generated URL for the Mission Control API.
4. Optionally add a scheduled run of the orchestrator (cron, n8n, or a future `/commands/run-cycle` endpoint).
