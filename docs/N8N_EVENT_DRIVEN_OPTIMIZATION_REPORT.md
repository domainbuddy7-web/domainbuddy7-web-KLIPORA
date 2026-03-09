# n8n Event-Driven Optimization Report

**Date:** 2026-03-09  
**Scope:** WF-VIDEO, WF-ASSEMBLE, WF-GEN — remove schedule triggers, implement event-driven chaining.

---

## 1. Triggers removed

| Workflow     | Trigger removed | Previous schedule |
|-------------|-----------------|-------------------|
| **WF-VIDEO**   | **Queue Poller** (schedule trigger) | Cron `0 8,16 * * 0-6` (twice daily at 08:00 and 16:00 UTC) |
| **WF-ASSEMBLE** | **Assembly Poller** (schedule trigger) | Cron `30 8,16 * * 0-6` (twice daily at 08:30 and 16:30 UTC) |

Both workflows no longer run on a timer. They run only when invoked by the previous workflow in the chain.

---

## 2. How workflows are now chained

### Execution chain

```
WF-GEN (webhook /webhook/wf-gen)
  → Store Job in Redis
  → Push to script_queue
  → Trigger WF-VIDEO  (HTTP POST to /webhook/wf-video)
  → Notify Script Ready
  → Respond Success

WF-VIDEO (webhook /webhook/wf-video, triggered by WF-GEN)
  → Check Paused → Check Time Window → GET Daily Count → Evaluate Limits → IF OK to Generate
  → RPOP script_queue → IF Queue Not Empty → Load Job → … → Push to render_queue
  → INCR Daily Count → Set Count Expiry 24h
  → Trigger WF-ASSEMBLE  (HTTP POST to /webhook/wf-assemble)

WF-ASSEMBLE (webhook /webhook/wf-assemble, triggered by WF-VIDEO)
  → Check Paused
  → RPOP render_queue → IF Render Queue Not Empty → Decode Render Package → …
  → (Poll Wavespeed, Save pending_approve, Notify Preview, etc.)
```

### Mechanism

- **WF-GEN → WF-VIDEO:** After **Push to script_queue**, a new node **Trigger WF-VIDEO** sends a POST request to `https://n8n-production-2762.up.railway.app/webhook/wf-video`. WF-VIDEO starts with a **Webhook** trigger (path `wf-video`).
- **WF-VIDEO → WF-ASSEMBLE:** After **Set Count Expiry 24h**, a new node **Trigger WF-ASSEMBLE** sends a POST request to `https://n8n-production-2762.up.railway.app/webhook/wf-assemble`. WF-ASSEMBLE starts with a **Webhook** trigger (path `wf-assemble`).

No **Execute Workflow** node is used; chaining is done via HTTP POST to each workflow’s webhook URL.

---

## 3. Queue safety (unchanged)

- **WF-VIDEO** still verifies **script_queue** is not empty before doing expensive work:
  - After **RPOP script_queue**, **IF Queue Not Empty** runs; only the “true” branch continues to Load Job, Decode Job, WaveSpeed scene/voice, Build Render Package, Push to render_queue, and Trigger WF-ASSEMBLE.
  - If the queue is empty, the run stops after the IF and no WaveSpeed calls or downstream triggers occur.

- **WF-ASSEMBLE** still verifies **render_queue** is not empty:
  - After **RPOP render_queue**, **IF Render Queue Not Empty** runs; only the “true” branch continues to Decode Render Package, Poll All Scenes Status, etc.
  - If the queue is empty, the run stops after the IF and no polling or notify steps run.

So no workflow performs expensive operations without a job: both rely on RPOP + IF not empty.

---

## 4. Confirmation: no workflow runs without a job

| Workflow     | When it runs | Guard |
|-------------|--------------|--------|
| **WF-GEN**   | On request (Mission Control or caller) to `/webhook/wf-gen`. | N/A (entry point). |
| **WF-VIDEO** | Only when WF-GEN calls `/webhook/wf-video` after pushing a job to `script_queue`. | RPOP script_queue → IF Queue Not Empty; no job → run stops. |
| **WF-ASSEMBLE** | Only when WF-VIDEO calls `/webhook/wf-assemble` after pushing a package to `render_queue`. | RPOP render_queue → IF Render Queue Not Empty; no package → run stops. |

- WF-VIDEO no longer runs on a schedule; it runs only when WF-GEN has just pushed a job to `script_queue` and then triggers it.
- WF-ASSEMBLE no longer runs on a schedule; it runs only when WF-VIDEO has just pushed a render package to `render_queue` and then triggers it.

Together with the existing queue checks, this ensures no workflow runs expensive logic without a job in the relevant queue.

---

## 5. Files changed

- **Automation/WF-VIDEO.json** — Replaced Queue Poller with **WF-VIDEO Webhook** (path `wf-video`). Added **Trigger WF-ASSEMBLE** after Set Count Expiry 24h. Updated connections.
- **Automation/WF-ASSEMBLE.json** — Replaced Assembly Poller with **WF-ASSEMBLE Webhook** (path `wf-assemble`). Updated connections.
- **Automation/WF-GEN.json** — Added **Trigger WF-VIDEO** after Push to script_queue; connection: Push to script_queue → Trigger WF-VIDEO → Notify Script Ready.
- **docs/KLIPORA_SYSTEM_BRAIN.md** — Updated AUTOMATION FLOW and N8N EXECUTION SCHEDULE to describe event-driven chaining and webhook triggers.

---

## 6. Deploy notes

1. **Re-import or update in n8n**  
   Re-import the modified workflow JSONs (WF-GEN, WF-VIDEO, WF-ASSEMBLE) into n8n, or apply the same node/connection changes in the editor.

2. **Webhook paths**  
   Ensure n8n is configured so that:
   - `POST /webhook/wf-video` starts WF-VIDEO.
   - `POST /webhook/wf-assemble` starts WF-ASSEMBLE.

3. **Base URL**  
   The trigger nodes use `https://n8n-production-2762.up.railway.app`. If your n8n instance has a different URL, replace it in:
   - WF-GEN: **Trigger WF-VIDEO** node.
   - WF-VIDEO: **Trigger WF-ASSEMBLE** node.

4. **Activation**  
   After import, activate WF-VIDEO and WF-ASSEMBLE so their webhooks are registered. WF-GEN should remain active for `/webhook/wf-gen`.
