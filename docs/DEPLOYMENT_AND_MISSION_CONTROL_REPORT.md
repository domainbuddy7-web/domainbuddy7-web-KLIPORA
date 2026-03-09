# KLIPORA Deployment and Mission Control Connectivity Report

**Date:** 2026-03-09

---

## Mission Control connectivity

### Detected MISSION_CONTROL_URL

- **KEY=value.env:** `MISSION_CONTROL_URL=https://domainbuddy7-web-klipora-production.up.railway.app`
- **.env (example):** Same URL in docs/example block.
- **WF-ASSEMBLE (Notify Preview node):** Hardcoded URL `https://domainbuddy7-web-klipora-production.up.railway.app/internal/notify-preview` — **matches** and is correct.

### Mission Control service status

- **GET /** → **HTTP 200** — `{"service":"KLIPORA Mission Control API","version":"0.1.0","config_ok":true}`
- **GET /health** → **HTTP 200** — `{"status":"ok","config_ok":true,"message":null,"fix":null}`

The Mission Control API is **reachable and healthy**. The Telegram bot’s “Could not reach Mission Control API” message occurs when:

1. The bot is run **without** loading `KEY=value.env` (or equivalent), so `MISSION_CONTROL_URL` is unset and the bot reports failure, or  
2. The bot’s environment cannot reach the URL (network/firewall), or  
3. The API was temporarily down.

**Fix:** Ensure the Telegram bot is started with env loaded (e.g. `KEY=value.env` or `.env` containing `MISSION_CONTROL_URL`) and that the host can reach `https://domainbuddy7-web-klipora-production.up.railway.app`.

### notify-preview endpoint test

- **POST /internal/notify-preview** with body `{"job_id": "health-check"}`  
  - **Result:** **HTTP 404** with body `{"detail":"pending_approve:{job_id} not found"}`.

This is **expected**: the route exists and runs; 404 is returned when the Redis key `pending_approve:<job_id>` does not exist (e.g. test `job_id` never written by WF-ASSEMBLE). So **connectivity to the notify-preview endpoint is OK**.

### WF-ASSEMBLE node URL verification

- **Node:** “Notify Preview (Mission Control)”
- **URL:** `https://domainbuddy7-web-klipora-production.up.railway.app/internal/notify-preview`
- **Body:** `{{ JSON.stringify({ job_id: $json.job_id }) }}`

No change needed. When WF-ASSEMBLE runs for a real job, it first writes `pending_approve:<job_id>` in Redis, then calls this endpoint; Mission Control then reads that key and sends the Telegram preview.

### Final connectivity status

**Mission Control API: REACHABLE AND OPERATIONAL.**

- Base URL and `/health` respond 200.
- `/internal/notify-preview` is present and responds (404 when key missing is correct behavior).
- WF-ASSEMBLE uses the correct URL. No workflow change required for connectivity.

---

## Queue cleanup (Redis)

- **Before:** `script_queue` length = 2 (leftover from earlier tests).
- **Action:** `DEL script_queue` executed via Upstash REST.
- **After:** `script_queue` length = 0, `render_queue` = 0.

Both queues are **empty** and ready for a clean end-to-end test.

---

## Workflow activation status

Activation via n8n REST API was attempted with `N8N_API_KEY` from `KEY=value.env`. All three workflows returned **401 Unauthorized**, so activation was **not** changed programmatically.

**Action required (manual in n8n UI):**

1. Open n8n → Workflows.
2. Activate:
   - **Klipora WF-GEN — Content Generation V2**
   - **Klipora WF-VIDEO — 5-Scene Video & Voice Generation V2**
   - **Klipora WF-ASSEMBLE — Assembly & Publishing V2**

Until these are **Active**, `/webhook/wf-video` and `/webhook/wf-assemble` will return 404 and the event-driven chain will not run.

---

## Webhook verification (after activation)

Once workflows are active, test:

```bash
curl -X POST "https://n8n-production-2762.up.railway.app/webhook/wf-video" \
  -H "Content-Type: application/json" -d '{"jobId":"test-1"}'
curl -X POST "https://n8n-production-2762.up.railway.app/webhook/wf-assemble" \
  -H "Content-Type: application/json" -d '{"job_id":"test-1"}'
```

Expected for both: **HTTP 200** and body `{"status":"accepted"}`.

---

## End-to-end execution confirmation

1. Trigger: `POST /webhook/wf-gen` with a realistic payload (e.g. `topic`, `genre`, `chat_id`).
2. In n8n **Executions**, confirm:
   - One WF-GEN run → Trigger WF-VIDEO.
   - One WF-VIDEO run (from webhook) → Trigger WF-ASSEMBLE.
   - One WF-ASSEMBLE run → Notify Preview (Mission Control).
3. In Redis, confirm `script_queue` and `render_queue` briefly increase then drain.

---

## Monitoring workflow deployment

**File:** `Automation/WF-HEALTH.json`  
**Name:** Klipora — Health Monitor

- **Trigger:** Schedule every 1 minute.
- **Logic:**
  - Fetches Upstash `LLEN script_queue` and `LLEN render_queue`.
  - Builds status text: workflow health (GEN/VIDEO/ASSEMBLE), queue lengths, optional backlog note.
  - Sends **KLIPORA SYSTEM STATUS** to Telegram every minute.
  - If either queue length ≥ 5, sends an additional **KLIPORA ALERT** to Telegram.

**Deploy in n8n:**

1. n8n → Workflows → Import from File → select `Automation/WF-HEALTH.json`.
2. (Optional) Replace hardcoded Telegram bot token and chat_id with n8n credentials or env.
3. Activate the workflow.

---

## Telegram alert configuration

- **Status message (every minute):** Contains system status, queue lengths, and a short note if queues are above threshold.
- **Alert message (when backlog):** Sent when `script_queue` or `render_queue` length ≥ 5; includes queue sizes and a reminder to check n8n.

Both use the same Telegram bot and chat_id as in the workflow (configurable in the node parameters).

---

## Summary

| Check | Status |
|-------|--------|
| MISSION_CONTROL_URL in config | Set correctly in KEY=value.env and docs |
| Mission Control GET / and /health | 200, config_ok true |
| POST /internal/notify-preview | Route works; 404 when key missing is expected |
| WF-ASSEMBLE Notify Preview URL | Correct; no change needed |
| Redis queue cleanup | script_queue and render_queue cleared |
| Workflow activation (API) | 401 — activate manually in n8n |
| Health Monitor workflow | Created at Automation/WF-HEALTH.json; import and activate in n8n |

**Next steps:** Activate the three main workflows and the Health Monitor in n8n, then run the webhook and end-to-end tests above to confirm full pipeline and Telegram reporting.
