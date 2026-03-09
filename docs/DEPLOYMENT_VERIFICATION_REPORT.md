# KLIPORA Deployment Verification Report

**Date:** 2026-03-09  
**Objectives:** Verify workflow activation, webhook registration, pipeline test, Redis queues, Health Monitor, Telegram monitoring, production readiness.

---

## 1. Webhook test results

| Endpoint | Result | Notes |
|----------|--------|--------|
| **POST /webhook/wf-gen** | **200 OK** | `{"message":"Workflow was started"}`. Triggered with payload `{"topic":"Deployment verification test","genre":"Mystery","chat_id":"8232710919"}`. |
| **POST /webhook/wf-video** | **404** | "The requested webhook \"POST wf-video\" is not registered." |
| **POST /webhook/wf-assemble** | **404** | "The requested webhook \"POST wf-assemble\" is not registered." |

**Cause:** The workflows **WF-VIDEO** (jTJnXHXjqo7FwGZV) and **WF-ASSEMBLE** (EzV0MUz5U6ZOnOjV) deployed on n8n are **older versions that do not include Webhook trigger nodes**. The repo definitions in `Automation/WF-VIDEO.json` and `Automation/WF-ASSEMBLE.json` include webhook triggers (`path: wf-video`, `path: wf-assemble`) and respond with `{"status":"accepted"}`. Pushing these via the n8n API (PUT) failed with schema validation (`Could not find property option`), so the fix must be done in the n8n UI.

**Required fix (manual in n8n UI):**

1. In n8n, open **Klipora WF-VIDEO — 5-Scene Video & Voice Generation V2** (ID: jTJnXHXjqo7FwGZV).
2. Use **Import from file** or replace the workflow by importing `E:\KLIPORA\Automation\WF-VIDEO.json` (or merge in the Webhook node and connections from that file so the workflow has both the **WF-VIDEO Webhook** trigger and the **Queue Poller**).
3. Do the same for **Klipora WF-ASSEMBLE — Assembly & Publishing V2** (ID: EzV0MUz5U6ZOnOjV) using `Automation/WF-ASSEMBLE.json`.
4. **Save** and ensure both workflows remain **Active** (toggle on).  
After that, **POST /webhook/wf-video** and **POST /webhook/wf-assemble** will return **200** and `{"status":"accepted"}`.

---

## 2. Workflow activation (n8n API)

Confirmed via `scripts/ensure_n8n_workflows_active.py` (with `N8N_API_KEY` from `KEY=value.env`):

| Workflow | Status |
|----------|--------|
| Klipora WF-ASSEMBLE — Assembly | **active** |
| Klipora WF-TREND — Daily Trend | **active** |
| Klipora WF-GEN — Content Gener | **active** |
| Klipora WF-VIDEO — 5-Scene Vid | **active** |

All four are **active**. WF-VIDEO and WF-ASSEMBLE run via their **schedule triggers** (queue pollers); the **webhook** path is missing until the repo versions are re-imported as above.

---

## 3. Full pipeline test

- **Trigger:** `POST https://n8n-production-2762.up.railway.app/webhook/wf-gen`  
  Body: `{"topic": "Deployment verification test", "genre": "Mystery", "chat_id": "8232710919"}`  
- **Result:** **HTTP 200** — `{"message":"Workflow was started"}`.

**Execution chain in current state:**

- **WF-GEN** runs (script generation, job metadata, LPUSH to `script_queue`, then HTTP POST to `/webhook/wf-video`).
- **POST /webhook/wf-video** returns **404**, so **WF-VIDEO is not triggered by the chain**.
- **WF-VIDEO** still runs on its **Queue Poller** (e.g. every 5 minutes), RPOPs `script_queue`, and processes jobs. So the pipeline **completes via poller**, not via webhook.
- After WF-VIDEO: LPUSH to `render_queue`, POST to `/webhook/wf-assemble` (currently 404). **WF-ASSEMBLE** runs via its **Assembly Poller** when it runs.

So: **1 WF-GEN execution** per trigger; **WF-VIDEO** and **WF-ASSEMBLE** run as many times as their pollers fire and find work. For **same jobId** end-to-end, re-importing the webhook versions is required so the chain is: WF-GEN → POST wf-video → WF-VIDEO → POST wf-assemble → WF-ASSEMBLE.

---

## 4. Redis queue behavior

- **Checked:** `LLEN script_queue`, `LLEN render_queue` (Upstash REST).
- **Values at check:** `script_queue: 0`, `render_queue: 0`.
- **Expected:** Queues go up briefly when WF-GEN/WF-VIDEO push, then back to 0 when consumers run. No backlog observed.

---

## 5. Mission Control

- **URL:** https://domainbuddy7-web-klipora-production.up.railway.app  
- **GET /health:** **200** — `{"status":"ok","config_ok":true,"message":null,"fix":null}`.

---

## 6. Health Monitor workflow

- **File:** `Automation/WF-HEALTH.json` (name: **Klipora — Health Monitor**).
- **Status:** **Not imported** in this verification. API import (POST workflow) returned **500 Internal Server Error**; UI import was not performed.
- **Action for you:** In n8n, use **Workflows → Import from file** and select `E:\KLIPORA\Automation\WF-HEALTH.json`. Then open the workflow, confirm the schedule node is **Every 1 min** (60 seconds), and set the workflow **Active**.
- **Behavior once active:** Every 60 seconds the workflow will call Upstash for `LLEN script_queue` and `LLEN render_queue`, format a status message (GEN/VIDEO/ASSEMBLE OK, queue sizes), and send it to Telegram. If either queue length ≥ 5, an alert is sent.

---

## 7. Telegram monitoring

- **Configured:** `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are set (e.g. in `.env` / `KEY=value.env`). WF-HEALTH.json sends to the same chat.
- **Confirmation:** Once **Klipora — Health Monitor** is imported and active, you should see messages like:
  - **KLIPORA SYSTEM STATUS: OK** (or DEGRADED if backlog).
  - **Workflow health:** GEN: OK, VIDEO: OK, ASSEMBLE: OK.
  - **Queues:** script_queue: N, render_queue: N.
- **Alert:** If queue length ≥ 5, an additional **KLIPORA ALERT** message is sent.

---

## 8. Scripts updated in this session

- **scripts/upload_wf_assemble.py** — PUT body limited to fields n8n accepts (`name`, `nodes`, `connections`, `settings`); no `id`/`tags` (read-only). Use after fixing any node schema mismatch.
- **scripts/upload_wf_video.py** — New script to push `Automation/WF-VIDEO.json` to n8n (same payload rules). Currently fails with `Could not find property option`; re-import via UI is the reliable fix.

---

## 9. Summary and final status

| Item | Status |
|------|--------|
| n8n UI | Reachable, workflows active |
| WF-GEN webhook | **OK** — 200, pipeline trigger works |
| WF-VIDEO webhook | **404** — Re-import repo workflow in n8n to add webhook |
| WF-ASSEMBLE webhook | **404** — Re-import repo workflow in n8n to add webhook |
| Pipeline test (wf-gen) | **OK** — Workflow started |
| Execution chain (webhook path) | **Incomplete** until wf-video/wf-assemble return 200 |
| Redis queues | **OK** — 0/0, no backlog |
| Mission Control | **OK** — health 200 |
| Health Monitor | **Not deployed** — Import WF-HEALTH.json in n8n UI and activate |
| Telegram monitoring | **Pending** — Depends on Health Monitor |

**Overall system status:** **PARTIALLY OPERATIONAL**

- **OPERATIONAL:** WF-GEN, Mission Control, Redis, workflow activation, pipeline start.
- **PENDING YOUR ACTION:**  
  1) Re-import **WF-VIDEO** and **WF-ASSEMBLE** from repo JSON in n8n so webhooks register.  
  2) Import and activate **Klipora — Health Monitor** from `Automation/WF-HEALTH.json`.

After those two steps, webhook tests will pass, the chain will be GEN → VIDEO → ASSEMBLE → notify-preview → Telegram, and status messages will appear in Telegram. Then:

**KLIPORA SYSTEM STATUS: OPERATIONAL**
