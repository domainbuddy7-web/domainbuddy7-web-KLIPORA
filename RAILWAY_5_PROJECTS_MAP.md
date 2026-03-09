# Map your 5 Railway projects to KLIPORA

You have **5 projects** on Railway (Klipora HQ):  
**chic-essence**, **zonal-empathy**, **responsible-energy**, **honest-magic**, **amusing-heart**.

KLIPORA needs **3 roles**: Mission Control API, n8n, Render (FFmpeg). The other 2 projects can be spare, staging, or future use.

---

## 1. Get the public URL for each project

In the Railway dashboard (you’re already logged in there):

1. Click **one project** (e.g. chic-essence).
2. Click the **service** inside it (the one that shows “1/1 service online”).
3. Go to **Settings** (or **Networking**).
4. Under **Public networking**, find the **domain** (e.g. `chic-essence-production.up.railway.app`).  
   If there’s no domain, use **Generate domain**.
5. Copy the full URL: `https://<that-domain>` (no trailing slash).
6. Repeat for the other 4 projects.

---

## 2. Fill in this table

| Project name        | Public URL (https://….) | Assign to KLIPORA role        |
|---------------------|--------------------------|--------------------------------|
| chic-essence        |                          | Mission Control / n8n / Render / Other |
| zonal-empathy       |                          | Mission Control / n8n / Render / Other |
| responsible-energy  |                          | Mission Control / n8n / Render / Other |
| honest-magic        |                          | Mission Control / n8n / Render / Other |
| amusing-heart       |                          | Mission Control / n8n / Render / Other |

**How to decide which is which**

- **Mission Control** = API that serves `/health`, `/health/system`, `/commands/generate-video`, etc. (this repo’s `Command_Center/dashboard_api.py` / `start_api`). Usually a **web** or **api** service.
- **n8n** = workflow editor; opening the URL in the browser shows the n8n UI (workflows, credentials).
- **Render** = service that runs FFmpeg and has a `/render` endpoint; often a separate small service.

If you’re not sure: open the URL in a new tab.  
- JSON with `config_ok` or “Mission Control” → **Mission Control**.  
- n8n login/workflows page → **n8n**.  
- Anything else (or “Welcome” / simple app) → note it and we can assign later.

---

## 3. After you fill the table

1. Put the **Mission Control** URL in `KEY=value.env` as **MISSION_CONTROL_URL**.
2. Put the **n8n** URL in Mission Control’s Railway env as **N8N_URL** (and **N8N_API_KEY** if you use it).
3. Put the **Render** URL in Mission Control’s env as **RAILWAY_RENDER_URL** and in n8n (WF-ASSEMBLE “Call Railway Render” node) if it’s different from the default.

If you paste the table here with the URLs and roles filled in (no secrets), I can tell you exactly what to set in env and in n8n.

---

**Note:** I can’t open your Railway dashboard in my browser (it redirects to GitHub login in this session). So this mapping is something you do in your browser; once you share the filled table, we can sync everything to KLIPORA.
