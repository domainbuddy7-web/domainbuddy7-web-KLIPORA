# Deploy KLIPORA — Steps to Run Now

Use this checklist to deploy the Mission Control API and wire automation.

---

## Step 1: Push code to GitHub

From your repo root (`E:\KLIPORA`):

```powershell
cd E:\KLIPORA
git status
git add -A
git commit -m "Mission Console + approval flow ready for deploy"
git push origin main
```

(Use your actual branch name if not `main`.)

---

## Step 2: Railway — deploy the API

1. Open **Railway** → your project → service **domainbuddy7-web-KLIPORA** (or create one from GitHub repo).
2. If the repo is already connected, Railway will **auto-deploy** on push. Check the **Deployments** tab for the latest build.
3. If this is a new service:
   - **New** → **GitHub Repo** → select your KLIPORA repo.
   - Root directory: repo root (default).
   - Railway will use the **Dockerfile** at the root.

---

## Step 3: Railway — environment variables

In Railway → your service → **Variables**, ensure these are set:

| Variable | Required | Notes |
|----------|----------|--------|
| `UPSTASH_REDIS_REST_URL` | ✅ Yes | From Upstash dashboard |
| `UPSTASH_REDIS_REST_TOKEN` | ✅ Yes | From Upstash dashboard |
| `N8N_URL` | ✅ Yes | Your n8n instance URL |
| `N8N_API_KEY` | ✅ Yes | n8n Settings → API |
| `TELEGRAM_BOT_TOKEN` | Optional | For run-cycle + review alerts |
| `TELEGRAM_CHAT_ID` | Optional | Owner chat ID |

**PORT** is set by Railway automatically; do not add it.

---

## Step 4: Railway — networking (port)

1. In Railway → your service → **Settings** → **Networking**.
2. Ensure **Public Networking** is enabled and **Target Port** is **8080** (or the port your `start_api.py` uses; Railway injects `PORT` env, so the app will listen on the correct port).
3. Copy your **public URL** (e.g. `https://domainbuddy7-web-klipora-production.up.railway.app`).

---

## Step 5: Verify the API

Open in a browser or with curl:

- `https://<your-railway-url>/`  
  → Should return: `{"service": "KLIPORA Mission Control API", ...}`

- `https://<your-railway-url>/health`  
  → `{"status": "ok", "config_ok": true}` (or `config_missing` if Redis env not set)

- `https://<your-railway-url>/health/system`  
  → System health (queues, flags)

---

## Step 6: GitHub Actions — scheduled run-cycle

1. GitHub repo → **Settings** → **Secrets and variables** → **Actions**.
2. Add repository secret:
   - **Name:** `MISSION_CONTROL_URL`
   - **Value:** `https://domainbuddy7-web-klipora-production.up.railway.app` (your Railway URL, no trailing slash)
3. Workflow **Run KLIPORA cycle** will run at **08:00 and 16:00 UTC** (12:00 and 20:00 UAE). To test now: **Actions** → **Run KLIPORA cycle** → **Run workflow**.

---

## Step 7: Telegram Mission Console (optional)

To run the Telegram bot as a **live console** on your machine (or a VPS):

1. Set in your environment (or a `.env` file):
   - `TELEGRAM_BOT_TOKEN` = your bot token
   - `MISSION_CONTROL_URL` = your Railway API URL (e.g. `https://domainbuddy7-web-klipora-production.up.railway.app`)
   - `OWNER_TELEGRAM_ID` or `TELEGRAM_CHAT_ID` = your Telegram user/chat ID

2. From repo root:
   ```powershell
   $env:PYTHONPATH = "E:\KLIPORA"
   python -m Command_Center.telegram_command_center
   ```

The bot will respond to `/start`, `/status`, `/videos`, `/finance`, etc., and use the Mission Control API on Railway.

---

## Summary

| Step | Action |
|------|--------|
| 1 | `git push` to trigger deploy |
| 2 | Railway builds from Dockerfile and deploys |
| 3 | Set Redis + n8n + optional Telegram env vars in Railway |
| 4 | Confirm public URL and port (e.g. 8080) |
| 5 | Hit `/` and `/health` to verify |
| 6 | Add `MISSION_CONTROL_URL` secret in GitHub for 2×/day run-cycle |
| 7 | (Optional) Run Telegram bot locally with `MISSION_CONTROL_URL` pointing at Railway |

After this, the API is live and run-cycle will execute on schedule. For full details see **DEPLOYMENT.md** and **AUTOMATION_SETUP.md**.
