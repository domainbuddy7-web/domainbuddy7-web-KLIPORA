# KLIPORA staged workflow upgrade – deployment execution guide

**Project root:** E:\KLIPORA  
**Purpose:** Step-by-step procedure to upgrade the live n8n pipeline from schedule-only polling to a hybrid **event-driven + queue-based** architecture, performed manually in the n8n editor.

**Reference docs:**
- `docs/DEPLOYMENT_PLAN_EVENT_DRIVEN_TRIGGERS.md`
- `docs/PRE_DEPLOYMENT_VALIDATION_REPORT.md`

**Workflow IDs (live):**
- WF-GEN: `VCw1KVSRcgRmlujA`
- WF-VIDEO: `jTJnXHXjqo7FwGZV`
- WF-ASSEMBLE: `EzV0MUz5U6ZOnOjV`

**Base URL:** `https://n8n-production-2762.up.railway.app`

---

## Current vs target pipeline

**Current (live):**  
WF-GEN → Redis `script_queue` → WF-VIDEO (schedule poller) → Redis `render_queue` → WF-ASSEMBLE (schedule poller)

**Target:**  
WF-GEN → Redis `script_queue` → **Trigger WF-VIDEO (POST webhook)** → WF-VIDEO → Redis `render_queue` → **Trigger WF-ASSEMBLE (POST webhook)** → WF-ASSEMBLE

**Fallback (must remain):** Queue polling and schedule triggers stay active.

---

## Stage 1 – Add webhook listeners

Webhook listeners must exist **before** Stage 2 so that POSTs from WF-GEN and WF-VIDEO trigger the correct workflows.

---

### Stage 1a – WF-VIDEO: add webhook listener

**Workflow:** WF-VIDEO (Klipora WF-VIDEO – 5-Scene Video & Voice Generation V2)  
**Live ID:** `jTJnXHXjqo7FwGZV`

1. Open n8n: `https://n8n-production-2762.up.railway.app`
2. Open the **WF-VIDEO** workflow (search by name or open from list).
3. Add a **Webhook** node:
   - Click **+** to add a node (or drag from node panel).
   - Search for **Webhook** and add it.
4. Configure the Webhook node:
   - **Name:** `WF-VIDEO Webhook` (or keep default; ensure it is identifiable).
   - **Webhook path:** `wf-video`
   - **HTTP Method:** `POST`
   - **Response Mode:** `On Received` (or equivalent so the workflow continues without waiting for a response body).
5. Connect the webhook to the existing flow:
   - Drag a connection **from** the new Webhook node **to** the **Check Paused** node.
   - The webhook is now an alternative entry point; the existing **Queue Poller** (schedule) remains unchanged.
6. Position the node (e.g. to the left of **Check Paused**) so the graph is clear.
7. **Save** the workflow (Ctrl+S / Cmd+S).
8. If the workflow was deactivated by editing, **Activate** it again (toggle in the editor or workflow list).
9. Confirm the workflow is **Active** and that **Queue Poller** and **WF-VIDEO Webhook** are both present.

**Resulting webhook URL:**  
`https://n8n-production-2762.up.railway.app/webhook/wf-video`

---

### Stage 1b – WF-ASSEMBLE: add webhook listener

**Workflow:** WF-ASSEMBLE (Klipora WF-ASSEMBLE – Assembly & Publishing V2)  
**Live ID:** `EzV0MUz5U6ZOnOjV`

1. Open the **WF-ASSEMBLE** workflow in the n8n editor.
2. Add a **Webhook** node.
3. Configure the Webhook node:
   - **Name:** `WF-ASSEMBLE Webhook`
   - **Webhook path:** `wf-assemble`
   - **HTTP Method:** `POST`
   - **Response Mode:** `On Received`
4. Connect:
   - **WF-ASSEMBLE Webhook** → **Check Paused**
   - Leave **Assembly Poller** (schedule) and its connection to the rest of the flow unchanged.
5. Position the node, **Save**, and **Activate** the workflow if needed.
6. Confirm the workflow is **Active** and both **Assembly Poller** and **WF-ASSEMBLE Webhook** are present.

**Resulting webhook URL:**  
`https://n8n-production-2762.up.railway.app/webhook/wf-assemble`

---

## Verify Stage 1

Before Stage 2, confirm that the new webhooks start the workflows.

1. **Test WF-VIDEO webhook**
   - From a terminal or Postman:
     ```bash
     curl -X POST https://n8n-production-2762.up.railway.app/webhook/wf-video
     ```
   - In n8n, open **Executions** for the WF-VIDEO workflow and confirm a new execution was started by the webhook (trigger type Webhook).  
   - If the queue is empty, the run may finish quickly after **Check Paused** / queue checks; that is expected.

2. **Test WF-ASSEMBLE webhook**
   - From a terminal or Postman:
     ```bash
     curl -X POST https://n8n-production-2762.up.railway.app/webhook/wf-assemble
     ```
   - In **Executions** for WF-ASSEMBLE, confirm a new execution was started by the webhook.

3. **Confirm**
   - Both workflows remain **Active**.
   - Schedule triggers (Queue Poller, Assembly Poller) are still in place and unchanged.
   - No need to change anything else if both webhook tests start an execution.

If either webhook does not start a run, fix the webhook path, method, and connection to **Check Paused** before proceeding to Stage 2.

---

## Stage 2 – Add event-driven HTTP trigger nodes

Stage 2 adds the nodes that **call** the webhooks you added in Stage 1.

---

### Stage 2a – WF-GEN: add Trigger WF-VIDEO

**Workflow:** WF-GEN (Klipora WF-GEN – Content Generation V2)  
**Live ID:** `VCw1KVSRcgRmlujA`

1. Open the **WF-GEN** workflow in the n8n editor.
2. Locate the nodes **Push to script_queue** and **Notify Script Ready** (currently connected in that order).
3. Add an **HTTP Request** node:
   - Add node → search **HTTP Request** → add.
4. Configure the HTTP Request node:
   - **Name:** `Trigger WF-VIDEO`
   - **Method:** `POST`
   - **URL:** `https://n8n-production-2762.up.railway.app/webhook/wf-video`
   - **Send Body:** `false` (or leave empty).
5. Update connections:
   - **Remove** the existing connection: **Push to script_queue** → **Notify Script Ready**.
   - **Add** connection: **Push to script_queue** → **Trigger WF-VIDEO**.
   - **Add** connection: **Trigger WF-VIDEO** → **Notify Script Ready**.
6. Position **Trigger WF-VIDEO** between **Push to script_queue** and **Notify Script Ready**.
7. **Save** the workflow and ensure it stays **Active**.

**Result:** After WF-GEN pushes a job to `script_queue`, it immediately POSTs to `/webhook/wf-video`, starting WF-VIDEO without waiting for the schedule.

---

### Stage 2b – WF-VIDEO: add Trigger WF-ASSEMBLE

**Workflow:** WF-VIDEO  
**Live ID:** `jTJnXHXjqo7FwGZV`

1. Open the **WF-VIDEO** workflow again.
2. Locate **Set Count Expiry 24h** (currently the last node on the success path; it may have no outgoing connection).
3. Add an **HTTP Request** node.
4. Configure the HTTP Request node:
   - **Name:** `Trigger WF-ASSEMBLE`
   - **Method:** `POST`
   - **URL:** `https://n8n-production-2762.up.railway.app/webhook/wf-assemble`
   - **Send Body:** `false`
5. Connect:
   - **Set Count Expiry 24h** → **Trigger WF-ASSEMBLE**
   - Trigger WF-ASSEMBLE has no outgoing connection (end of branch).
6. Position the node, **Save**, and keep the workflow **Active**.

**Result:** After WF-VIDEO pushes to `render_queue` and updates daily count, it immediately POSTs to `/webhook/wf-assemble`, starting WF-ASSEMBLE.

---

## Verify Stage 2

1. **Trigger WF-GEN**
   - Call the WF-GEN webhook with a valid body (e.g. from Mission Control or Telegram generate flow, or a test POST to `/webhook/wf-gen` with the expected JSON: `genre`, `topic`, `job_id`, `chat_id`, etc., as used by your system).
   - Example (minimal test; may fail validation but can show chain):
     ```bash
     curl -X POST https://n8n-production-2762.up.railway.app/webhook/wf-gen \
       -H "Content-Type: application/json" \
       -d "{\"genre\":\"Mystery\",\"topic\":\"Test\",\"job_id\":\"test-1\",\"chat_id\":\"123\"}"
     ```
2. **Confirm execution chain**
   - In n8n **Executions**:
     - WF-GEN: one execution for the test.
     - WF-VIDEO: one execution started shortly after (triggered by Trigger WF-VIDEO).
     - WF-ASSEMBLE: one execution started after WF-VIDEO (triggered by Trigger WF-ASSEMBLE).
   - This confirms: WF-GEN → (POST wf-video) → WF-VIDEO → (POST wf-assemble) → WF-ASSEMBLE.
3. **Confirm Redis queues**
   - If you have access to Redis or a dashboard: after a successful run, `script_queue` and `render_queue` should still be used as before (WF-GEN pushes, WF-VIDEO pops/pushes, WF-ASSEMBLE pops). Queue polling remains the fallback if webhooks are not called.

---

## Post-deployment checks

- [ ] **WF-GEN**, **WF-VIDEO**, **WF-ASSEMBLE** are all **Active**.
- [ ] **Queue Poller** (WF-VIDEO) and **Assembly Poller** (WF-ASSEMBLE) are still present and connected; schedule-based runs still occur.
- [ ] **Webhook triggers:** POSTs to `/webhook/wf-video` and `/webhook/wf-assemble` start WF-VIDEO and WF-ASSEMBLE immediately.
- [ ] **Execution logs:** Chained runs appear (WF-GEN → WF-VIDEO → WF-ASSEMBLE) when WF-GEN is triggered with valid input.
- [ ] **Mission Control / Telegram:** Generate-video and approve/preview flows still work end-to-end.

---

## Rollback procedure

If you need to revert to the previous schedule-only behaviour:

### Rollback Stage 2 (remove event-driven triggers only)

**WF-GEN:**

1. Open WF-GEN.
2. **Delete** the node **Trigger WF-VIDEO**.
3. **Reconnect:** **Push to script_queue** → **Notify Script Ready** (restore the direct connection that existed before Stage 2).
4. Save and leave the workflow Active.

**WF-VIDEO:**

1. Open WF-VIDEO.
2. **Delete** the node **Trigger WF-ASSEMBLE**.
3. **Remove** the connection from **Set Count Expiry 24h** to Trigger WF-ASSEMBLE (so Set Count Expiry 24h has no outgoing connection again, or reconnect only to any node that existed before).
4. Save and leave the workflow Active.

**Result:** Pipeline reverts to schedule-only polling; webhook listeners (Stage 1) remain but are unused.

---

### Rollback Stage 1 (remove webhook listeners)

If you also want to remove the webhook entry points:

**WF-VIDEO:**

1. Open WF-VIDEO.
2. **Delete** the node **WF-VIDEO Webhook**.
3. Remove any connection that referenced it. **Queue Poller** remains the only trigger.
4. Save and Activate.

**WF-ASSEMBLE:**

1. Open WF-ASSEMBLE.
2. **Delete** the node **WF-ASSEMBLE Webhook**.
3. Remove any connection that referenced it. **Assembly Poller** remains the only trigger.
4. Save and Activate.

**Result:** Pipeline is back to the pre-upgrade state (schedule-only, no webhook listeners for wf-video/wf-assemble).

---

## Summary checklist

| Step | Action | Workflow | Verify |
|------|--------|----------|--------|
| 1a | Add Webhook `wf-video`, connect to Check Paused | WF-VIDEO | Save, Activate |
| 1b | Add Webhook `wf-assemble`, connect to Check Paused | WF-ASSEMBLE | Save, Activate |
| 1 verify | POST to `/webhook/wf-video` and `/webhook/wf-assemble` | — | Executions show webhook-triggered runs |
| 2a | Add HTTP Request Trigger WF-VIDEO; Push to script_queue → Trigger WF-VIDEO → Notify Script Ready | WF-GEN | Save, Active |
| 2b | Add HTTP Request Trigger WF-ASSEMBLE; Set Count Expiry 24h → Trigger WF-ASSEMBLE | WF-VIDEO | Save, Active |
| 2 verify | Trigger WF-GEN; confirm WF-GEN → WF-VIDEO → WF-ASSEMBLE in Executions | — | Chain runs; queues still used |
| Post | All workflows active; queue polling and webhooks both work | All | Checklist above |

This guide is for **manual execution in the n8n editor** only. No automated changes to workflows have been applied.
