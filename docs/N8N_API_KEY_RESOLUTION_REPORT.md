# n8n API Authentication Resolution Report

**Date:** 2026-03-09  
**Issue:** `GET /api/v1/workflows` returned **401 Unauthorized** (API key invalid or expired).

---

## 1. Steps completed (Browserbase)

1. **Opened n8n dashboard** — `https://n8n-production-2762.up.railway.app`
2. **Navigated to Settings → API** — `https://n8n-production-2762.up.railway.app/settings/api`
3. **Existing API keys** — Found: parallep project, klipora api, klipora automation, klipora-v2, klipora-deploy.
4. **Created new API key** — Label: **klipora-scripts-2026** (expiration: 30 days). n8n showed the key once on the "API Key Created" screen; it is not stored in this report because the key value is not exposed to the browser automation layer (copy-only / masked in the UI).
5. **Closed dialog** — Clicked "Done".

---

## 2. API key: created or reused

| Item | Result |
|------|--------|
| **Action** | **New API key created** (label: `klipora-scripts-2026`) |
| **Reuse** | Did not reuse an existing key; created a new one so automation scripts have a dedicated key. |
| **Key value** | **Not captured.** n8n displays the key only once after creation. You must copy it from n8n and set it in `.env` (see below). |

**If you did not copy the key when the "API Key created" dialog was open:**

- Go to **n8n → Settings → n8n API**.
- Click **Create an API Key**, give it a label (e.g. `klipora-scripts`), then **copy the key immediately** when it is shown.
- Set `N8N_API_KEY=<paste>` in your `.env` file (see section 4).

---

## 3. API verification result

| Check | Status |
|-------|--------|
| **GET /api/v1/workflows with new key** | **Not run.** The new key value was not available to this automation, so verification could not be performed in this session. |
| **Next step** | After you set `N8N_API_KEY` in `.env`, run:  
  `python scripts/ensure_n8n_workflows_active.py`  
  A successful run (workflow list printed, no 401) confirms **200 OK**. |

---

## 4. Environment variable updated

| Location | Action |
|----------|--------|
| **Project `.env`** | The project uses a combined instructions + example file at `E:\KLIPORA\.env`. **You must set `N8N_API_KEY`** to the key you copied from n8n (Settings → API). Ensure there is a line:  
  `N8N_API_KEY=<your-copied-key>`  
  with no spaces around `=`. |
| **Mission Control (Railway)** | For the Mission Control API to call n8n (e.g. `/automation`), set **N8N_API_KEY** in the Railway service environment variables to the same key, then redeploy. |
| **Saved for future automation** | Once `N8N_API_KEY` is set in `.env` (and in Railway if needed), scripts such as `ensure_n8n_workflows_active.py` and Mission Control will use it without further manual steps. |

---

## 5. Summary

- **API key created:** Yes — label **klipora-scripts-2026**.
- **API verification:** Pending — run `python scripts/ensure_n8n_workflows_active.py` after setting `N8N_API_KEY` in `.env`.
- **Environment variable:** You must paste the key from n8n into `.env` as `N8N_API_KEY=<key>`; for Mission Control, set the same in Railway and redeploy.

After updating `N8N_API_KEY`, re-run the workflow script to confirm 200 OK and that automation can list/activate workflows without manual intervention.
