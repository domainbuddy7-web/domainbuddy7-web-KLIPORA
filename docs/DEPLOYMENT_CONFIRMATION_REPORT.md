# KLIPORA Deployment Confirmation Report

**Date:** 2026-03-09  
**n8n instance:** https://n8n-production-2762.up.railway.app

---

## 1. Workflow activation status

| Workflow ID | Name | API check | Result |
|-------------|------|-----------|--------|
| VCw1KVSRcgRmlujA | WF-GEN | GET /rest/workflows/:id | **401 Unauthorized** — could not read state |
| jTJnXHXjqo7FwGZV | WF-VIDEO | GET /rest/workflows/:id | **401 Unauthorized** — could not read state |
| EzV0MUz5U6ZOnOjV | WF-ASSEMBLE | GET /rest/workflows/:id | **401 Unauthorized** — could not read state |

**Conclusion:** The n8n API key configured in `.env` / `KEY=value.env` is **not accepted** by this instance (401). Activation status could **not** be verified or changed via API.

**Evidence from webhooks:**
- **WF-GEN** is **active**: `POST /webhook/wf-gen` returns **200** and starts the workflow.
- **WF-VIDEO** and **WF-ASSEMBLE** production webhooks are **not registered**: their endpoints return 404, which indicates those two workflows are **inactive** (or their production webhooks are not registered).

**Action required:** In the n8n UI, open and **Activate**:
- **Klipora WF-VIDEO — 5-Scene Video & Voice Generation V2**
- **Klipora WF-ASSEMBLE — Assembly & Publishing V2**

(WF-GEN is already active.)

---

## 2. Webhook results

| Endpoint | Method | Expected | Actual | OK? |
|----------|--------|----------|--------|-----|
| /webhook/wf-video | POST | 200 `{"status":"accepted"}` | **404** — webhook not registered | No |
| /webhook/wf-assemble | POST | 200 `{"status":"accepted"}` | **404** — webhook not registered | No |

**Reason:** WF-VIDEO and WF-ASSEMBLE must be **active** for their production webhooks to be registered. Until they are activated in n8n, these endpoints will continue to return 404.

After activation, re-run:
```bash
curl -X POST "https://n8n-production-2762.up.railway.app/webhook/wf-video" -H "Content-Type: application/json" -d '{"jobId":"test"}'
curl -X POST "https://n8n-production-2762.up.railway.app/webhook/wf-assemble" -H "Content-Type: application/json" -d '{"job_id":"test"}'
```
Expected: **HTTP 200** and body `{"status":"accepted"}` for both.

---

## 3. Queue health (Redis)

| Queue | Length | Status |
|-------|--------|--------|
| script_queue | **0** | Healthy — no backlog |
| render_queue | **0** | Healthy — no backlog |

Both queues returned to zero. No buildup detected.

---

## 4. Execution chain confirmation

| Step | Action | Result |
|------|--------|--------|
| Trigger | POST /webhook/wf-gen (topic, genre, chat_id) | **200** — `{"message":"Workflow was started"}` |
| WF-GEN | Runs and enqueues job | Started successfully |
| WF-VIDEO | Should start via POST /webhook/wf-video | **Cannot complete** — wf-video webhook is 404 (workflow inactive) |
| WF-ASSEMBLE | Should start via POST /webhook/wf-assemble | **Cannot complete** — wf-assemble webhook is 404 (workflow inactive) |
| notify-preview | Called by WF-ASSEMBLE | Not reached until WF-ASSEMBLE is active |

**Conclusion:** The **event-driven chain (GEN → VIDEO → ASSEMBLE → notify-preview)** does **not** complete end-to-end until WF-VIDEO and WF-ASSEMBLE are **active**. Right now only WF-GEN runs; the job is enqueued to `script_queue`, and the fallback **Queue Poller** in WF-VIDEO would process it only when that workflow is active and its schedule runs (or when the webhook is registered after activation).

**After activating WF-VIDEO and WF-ASSEMBLE:** Trigger `POST /webhook/wf-gen` again and verify in n8n **Executions** that one GEN, one VIDEO, and one ASSEMBLE run, and that Mission Control notify-preview is called.

---

## 5. Health workflow import and Telegram monitoring status

| Step | Action | Result |
|------|--------|--------|
| Import | POST /rest/workflows with `Automation/WF-HEALTH.json` | **401 Unauthorized** — import failed |
| Activate | POST /rest/workflows/:id/activate | Not attempted (no workflow id) |

**Conclusion:** The **Klipora — Health Monitor** workflow could **not** be imported or activated via API because the n8n API key is unauthorized.

**Action required (manual):**
1. In n8n, go to **Workflows** → **Import from File** (or paste JSON).
2. Select **`E:\KLIPORA\Automation\WF-HEALTH.json`** (or paste its contents).
3. Save the workflow, then **Activate** it.

Once active, the Health Monitor runs **every 1 minute**, fetches Redis queue lengths, and sends a **KLIPORA SYSTEM STATUS** message to Telegram (chat_id in the workflow). If either queue length ≥ 5, it also sends a **KLIPORA ALERT**. **Telegram status reporting will work** after this workflow is imported and activated in the UI.

---

## Summary table

| Item | Status | Notes |
|------|--------|--------|
| Workflow activation (API) | Failed (401) | Activate WF-VIDEO and WF-ASSEMBLE in n8n UI |
| WF-GEN active | Yes | Confirmed via 200 on /webhook/wf-gen |
| WF-VIDEO / WF-ASSEMBLE active | No | 404 on webhooks; activate in UI |
| Webhook wf-video | 404 | Will be 200 after WF-VIDEO is active |
| Webhook wf-assemble | 404 | Will be 200 after WF-ASSEMBLE is active |
| Redis script_queue | 0 | Healthy |
| Redis render_queue | 0 | Healthy |
| E2E trigger (wf-gen) | 200 | GEN runs; chain stops at VIDEO/ASSEMBLE until they are active |
| Execution chain GEN→VIDEO→ASSEMBLE→notify-preview | Incomplete | Complete after activating VIDEO and ASSEMBLE |
| Health workflow import (API) | Failed (401) | Import and activate WF-HEALTH.json in n8n UI |
| Telegram monitoring | Pending | Works after Health Monitor is imported and activated |

---

## Next steps to finalize deployment

1. **Fix n8n API access (optional):** In n8n → **Settings** → **API** → create or copy a valid API key, then set `N8N_API_KEY` in `.env` or `KEY=value.env`. Then re-run `python scripts/deployment_confirm.py` to verify activation and import via API.
2. **Activate workflows in UI:** In n8n, open **WF-VIDEO** and **WF-ASSEMBLE** and turn them **Active**.
3. **Re-test webhooks:** Confirm `POST /webhook/wf-video` and `POST /webhook/wf-assemble` return 200 and `{"status":"accepted"}`.
4. **Re-run E2E:** Trigger `POST /webhook/wf-gen` and confirm in Executions: GEN → VIDEO → ASSEMBLE → notify-preview.
5. **Import and activate Health Monitor:** Import `Automation/WF-HEALTH.json` in n8n and activate it so Telegram receives status every minute.

After steps 2–5, the pipeline and Telegram monitoring will be fully operational.
