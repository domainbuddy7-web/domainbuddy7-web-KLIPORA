# WF-ASSEMBLE Audit Report — Hybrid Architecture

**Workflow:** Klipora WF-ASSEMBLE — Assembly & Publishing V2  
**Date:** 2026-03-09  
**Objective:** Audit and align with event-driven + fallback poller architecture; reduce unnecessary schedule runs.

---

## 1. Trigger nodes

| Node | Type | Status |
|------|------|--------|
| **WF-ASSEMBLE Webhook** | `n8n-nodes-base.webhook` | ✅ Allowed — event path |
| **Assembly Poller Schedule** | `n8n-nodes-base.scheduleTrigger` | ✅ Allowed — fallback path |

**No extra triggers found.** No duplicate webhooks, no Execute Workflow nodes, no Telegram triggers. Only the two intended triggers exist.

---

## 2. Webhook configuration

| Setting | Value | OK |
|---------|--------|-----|
| **HTTP Method** | POST | ✅ |
| **Path** | `wf-assemble` | ✅ |
| **Response Mode** | `responseNode` | ✅ |
| **Response code** | 200 (options) | ✅ |

**Connections:**
- WF-ASSEMBLE Webhook → **Respond Accepted** (returns `{"status":"accepted"}`)
- WF-ASSEMBLE Webhook → **Webhook Body to Render Result** (encodes body for downstream)

**Result:** Webhook returns **HTTP 200** and `{"status":"accepted"}` via the response node. ✅

---

## 3. Schedule poller (fallback)

| Setting | Before | After |
|---------|--------|--------|
| **Node** | Assembly Poller Schedule | — |
| **Interval (repo)** | Every **5** minutes | Every **15** minutes |
| **Interval (deployed)** | Reported **~3 min** in n8n | Must be updated in n8n to match repo |

**Change applied in repo:** `Automation/WF-ASSEMBLE.json` — `minutesInterval` updated from **5** to **15**.

**Reason:** Fallback should not run as the primary driver. Every 15 minutes is enough to drain the queue when the webhook path is unavailable.

**Action:** Re-import or push the updated workflow to n8n so the deployed schedule is **Every 15 minutes**. If the live workflow was edited to 3 minutes in the UI, overwriting with the repo version will set it to 15.

---

## 4. Fallback queue logic

**Path:**
```
Assembly Poller Schedule
  → Check Paused
  → IF Not Paused
  → RPOP render_queue
  → IF Render Queue Not Empty
  → Decode Render Package
  → Try Lock (SETNX)   [NEW]
  → Poll All Scenes Status
  → …
```

**Behavior:**
- **Check Paused:** GET `system:paused` from Redis; if paused, workflow stops at IF Not Paused.
- **RPOP render_queue:** One item popped; empty queue → `result` empty.
- **IF Render Queue Not Empty:** `result` not empty → continue; otherwise workflow exits with no further nodes.

**Result:** When the queue is empty, the fallback path exits immediately after the IF. ✅

---

## 5. Event-driven path and convergence

**Webhook path:**
```
WF-ASSEMBLE Webhook
  → Respond Accepted (response branch)
  → Webhook Body to Render Result
  → IF Render Queue Not Empty   [uses body as “result”]
  → Decode Render Package
  → Try Lock (SETNX)
  → Poll All Scenes Status
  → … → Notify Preview (Mission Control)
```

**Poller path:** Same from **IF Render Queue Not Empty** onward (RPOP supplies `result`; then Decode → Try Lock → Poll All Scenes Status → …).

**Convergence:** Both paths meet at **IF Render Queue Not Empty** and then share **Decode Render Package → Try Lock (SETNX) → Poll All Scenes Status** and the rest of the assembly pipeline. ✅

---

## 6. Recursion and cross-workflow calls

| Check | Result |
|-------|--------|
| Calls to `/webhook/wf-gen` | ❌ None |
| Calls to `/webhook/wf-video` | ❌ None |
| Calls to `/webhook/wf-assemble` | ❌ None |
| Execute Workflow node | ❌ None |
| HTTP requests | Redis (Upstash), Wavespeed, Mission Control `/internal/notify-preview`, Railway Render, Telegram — no KLIPORA webhooks |

**Result:** No recursion and no self- or cross-workflow webhook triggers. ✅

---

## 7. Duplicate execution risk and lock

**Risk:** The same job can be processed twice if:
- WF-VIDEO LPUSHes to `render_queue` and POSTs to `/webhook/wf-assemble` with the package.
- Webhook run processes the body while the job remains in the queue.
- The poller later RPOPs the same job and processes it again.

**Mitigation added:** A **Try Lock (SETNX)** node after **Decode Render Package**:
- Key: `processing:assembly:{jobId}`
- Command: `SET key 1 NX EX 300` (5-minute TTL)
- If lock is acquired (`result === 'OK'`): pass the item to **Poll All Scenes Status**.
- If lock already exists: return `[]` and stop the run (no duplicate processing).

Both webhook and poller paths go through **Decode → Try Lock**, so only one execution per `jobId` proceeds into the rest of the pipeline. ✅

---

## 8. Call Railway Render / Update Analytics / Log to Telegram

**Finding:** In the current **connections** in the repo:
- **IF All Complete** (true) → **Save pending_approve to Redis** → **Notify Preview (Mission Control)**.
- **Call Railway Render** has **no incoming connection**; only **Call Railway Render → Update Analytics → Log to Telegram** is defined.

So in the graph as defined, the **Call Railway Render** branch is never executed. Possible interpretations:
- **Design:** Mission Control `/internal/notify-preview` is responsible for triggering render (or another service), and the “Call Railway Render” node is legacy/unused; or
- **Omission:** There should be a connection from **Save pending_approve to Redis** (or from **IF All Complete**) to **Call Railway Render**.

**Recommendation:** Confirm with product/design whether **Notify Preview** alone is the intended path, or if **Save pending_approve** (or **IF All Complete**) should also connect to **Call Railway Render**. If the latter, add that connection in the workflow.

---

## 9. Summary of changes made (repo)

| Item | Change |
|------|--------|
| **Assembly Poller Schedule** | `minutesInterval`: **5 → 15** in `Automation/WF-ASSEMBLE.json` |
| **Try Lock (SETNX)** | New node after **Decode Render Package**: Redis `SET processing:assembly:{jobId} 1 NX EX 300`; pass through only if lock acquired |
| **Connections** | **Decode Render Package** → **Try Lock (SETNX)** → **Poll All Scenes Status** |

---

## 10. Recommended next steps

1. **Deploy updated workflow**  
   Re-import `Automation/WF-ASSEMBLE.json` into n8n (or push via API if schema allows) so that:
   - Schedule is **Every 15 minutes**.
   - Lock node is present and wired as above.

2. **Confirm schedule in n8n**  
   Open the workflow in n8n and ensure the **Assembly Poller Schedule** node shows **Every 15 minutes** (not 3 or 5).

3. **Clarify Call Railway Render**  
   Decide if **Call Railway Render** (and thus **Update Analytics** / **Log to Telegram**) should run from this workflow; if yes, add the appropriate incoming connection.

4. **Monitor**  
   After deployment, confirm:
   - WF-ASSEMBLE runs when WF-VIDEO calls **POST /webhook/wf-assemble**.
   - Fallback runs at most every 15 minutes and only when the queue has work (or after Check Paused / IF Not Paused).
   - No duplicate processing for the same `jobId` (lock in place).

---

## Expected result

- **Event path:** WF-VIDEO → POST /webhook/wf-assemble → WF-ASSEMBLE → process render package → Mission Control notify-preview.
- **Fallback path:** Assembly Poller (every 15 min) → Check Paused → RPOP → IF not empty → process (with lock).
- **No** unnecessary runs every 3 minutes when there are no jobs.
- **No** duplicate execution of the same job thanks to `processing:assembly:{jobId}` lock.
