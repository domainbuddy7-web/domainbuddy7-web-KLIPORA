# KLIPORA event-driven triggers – pre-deployment validation report

**Date:** Pre-deployment (no changes applied).  
**Plan:** `docs/DEPLOYMENT_PLAN_EVENT_DRIVEN_TRIGGERS.md`  
**Goal:** Confirm that adding the two HTTP trigger nodes is safe and that webhook endpoints exist or are planned.

---

## 1. Webhook endpoints in live n8n

**Method:** `GET /api/v1/workflows`; for each workflow, load full definition and look for nodes with `type` containing `webhook` and `parameters.path` or `parameters.webhookPath`.

### 1.1 Workflows with webhook nodes (live)

| Workflow name | Workflow ID | Active | Webhook node name | Webhook path | Full URL |
|---------------|-------------|--------|-------------------|--------------|----------|
| Klipora WF-GEN – Content Generation V2 | VCw1KVSRcgRmlujA | True | Gen Webhook | **wf-gen** | `https://n8n-production-2762.up.railway.app/webhook/wf-gen` |

### 1.2 Webhook endpoints required by the plan

| Endpoint path | Used by (caller) | Listener workflow (repo design) | Present in live? |
|---------------|------------------|----------------------------------|------------------|
| **/webhook/wf-video** | WF-GEN (Trigger WF-VIDEO node) | WF-VIDEO | **No** – WF-VIDEO has no webhook node; trigger is schedule only (Queue Poller). |
| **/webhook/wf-assemble** | WF-VIDEO (Trigger WF-ASSEMBLE node) | WF-ASSEMBLE | **No** – WF-ASSEMBLE has no webhook node; trigger is schedule only (Assembly Poller). |

### 1.3 Conclusion on webhook endpoints

- **wf-gen:** Exists and is active (WF-GEN, Gen Webhook). Mission Control can start WF-GEN via POST to `/webhook/wf-gen`.
- **wf-video:** Does **not** exist in the live instance. WF-VIDEO has only a **schedule** trigger (Queue Poller). The repo `Automation/WF-VIDEO.json` defines a webhook trigger with path `wf-video`, but that node is not present in the deployed WF-VIDEO.
- **wf-assemble:** Does **not** exist in the live instance. WF-ASSEMBLE has only a **schedule** trigger (Assembly Poller). The repo `Automation/WF-ASSEMBLE.json` defines a webhook trigger with path `wf-assemble`, but that node is not present in the deployed WF-ASSEMBLE.

**Implication:** Deploying only the two HTTP Request nodes (Trigger WF-VIDEO, Trigger WF-ASSEMBLE) will cause WF-GEN and WF-VIDEO to POST to `/webhook/wf-video` and `/webhook/wf-assemble`, but no workflow will run from those POSTs until WF-VIDEO and WF-ASSEMBLE have **webhook trigger nodes** with paths `wf-video` and `wf-assemble`. Until then, the pipeline remains effectively **schedule-only**; the new nodes do not introduce errors but the event-driven path will not run.

---

## 2. Webhook node details (where they exist)

- **Gen Webhook (WF-GEN)**  
  - Workflow: Klipora WF-GEN – Content Generation V2  
  - Node name: Gen Webhook  
  - Webhook path: **wf-gen**  
  - HTTP method: POST (or as configured in node)  
  - Full webhook URL: `https://n8n-production-2762.up.railway.app/webhook/wf-gen`  
  - Active: workflow is active, so the endpoint is registered.

For **wf-video** and **wf-assemble**, there are no webhook nodes in live to report; the URLs `https://n8n-production-2762.up.railway.app/webhook/wf-video` and `https://n8n-production-2762.up.railway.app/webhook/wf-assemble` match the repository trigger node URLs but have no listeners in the current deployment.

---

## 3. Match with repository trigger node URLs

Repository trigger nodes use:

- WF-GEN → Trigger WF-VIDEO: `https://n8n-production-2762.up.railway.app/webhook/wf-video`
- WF-VIDEO → Trigger WF-ASSEMBLE: `https://n8n-production-2762.up.railway.app/webhook/wf-assemble`

These URLs are the correct n8n webhook format (base URL + `/webhook/` + path). Once WF-VIDEO and WF-ASSEMBLE have webhook triggers with path `wf-video` and `wf-assemble`, the endpoints will correspond exactly to these URLs.

---

## 4. Recursion and loop check

**Intended chain:** WF-GEN → (POST) → WF-VIDEO → (POST) → WF-ASSEMBLE → (Mission Control notify-preview). No workflow in this chain calls WF-GEN.

**Verified:**

- WF-GEN: triggers WF-VIDEO only (no call to WF-ASSEMBLE or WF-GEN).
- WF-VIDEO: triggers WF-ASSEMBLE only (no call to WF-GEN or WF-VIDEO).
- WF-ASSEMBLE: calls Mission Control `/internal/notify-preview` (no call to WF-GEN, WF-VIDEO, or WF-ASSEMBLE).

**Conclusion:** No path back to WF-GEN; no recursive execution loops. Safe from a recursion perspective.

---

## 5. Redis queue operations unchanged

- **script_queue:**  
  - WF-GEN: still pushes job ID to `script_queue` (unchanged).  
  - WF-VIDEO: still RPOPs `script_queue` on schedule (unchanged).  
- **render_queue:**  
  - WF-VIDEO: still pushes render package to `render_queue` (unchanged).  
  - WF-ASSEMBLE: still RPOPs `render_queue` on schedule (unchanged).

The patch only adds HTTP Request nodes and connection wiring. No Redis node parameters or queue names are changed. **Queue fallback preserved.**

---

## 6. Schedule triggers preserved

- **WF-VIDEO:** Queue Poller (schedule) and RPOP `script_queue` logic unchanged; schedule remains as fallback when no event-driven POST.
- **WF-ASSEMBLE:** Assembly Poller (schedule) and RPOP `render_queue` logic unchanged; schedule remains as fallback.

**Conclusion:** Schedule-based polling remains intact as fallback. Hybrid behaviour (event-driven + polling) is preserved once webhook listeners exist.

---

## 7. Deployment readiness summary

| Check | Result |
|-------|--------|
| Webhook **wf-gen** exists and is active | Yes |
| Webhook **wf-video** exists in live | **No** – add webhook trigger to WF-VIDEO for full event-driven chain |
| Webhook **wf-assemble** exists in live | **No** – add webhook trigger to WF-ASSEMBLE for full event-driven chain |
| URLs in repo trigger nodes match n8n base URL | Yes |
| No recursion / no path back to WF-GEN | Yes |
| Redis queue operations unchanged | Yes |
| Schedule (Queue Poller, Assembly Poller) fallback unchanged | Yes |
| Safe to add the two HTTP trigger nodes without breaking existing behaviour | Yes |

---

## 8. Deployment readiness statement

- **Webhook endpoints:** Only **wf-gen** is currently valid in live. **wf-video** and **wf-assemble** are **not** present; adding only the two HTTP trigger nodes will not break anything but event-driven runs will not occur until webhook triggers for `wf-video` and `wf-assemble` are added to WF-VIDEO and WF-ASSEMBLE.
- **No recursion risk:** Confirmed; chain is WF-GEN → WF-VIDEO → WF-ASSEMBLE with no path back to WF-GEN.
- **Queue fallback:** Preserved; script_queue and render_queue usage and schedule polling are unchanged.
- **Safe to deploy trigger nodes:** Yes. Deploying the two HTTP Request nodes (Trigger WF-VIDEO, Trigger WF-ASSEMBLE) as in the plan is safe. For a full **hybrid event-driven + polling** pipeline, also add or enable webhook trigger nodes (path **wf-video** in WF-VIDEO and **wf-assemble** in WF-ASSEMBLE) so the posted webhook URLs have active listeners.

**Recommended deployment order (when you choose to deploy):**

1. Add webhook trigger nodes to WF-VIDEO (path `wf-video`) and WF-ASSEMBLE (path `wf-assemble`) so the endpoints exist and are active.
2. Add the two HTTP Request nodes and connection changes from `docs/DEPLOYMENT_PLAN_EVENT_DRIVEN_TRIGGERS.md` (Trigger WF-VIDEO in WF-GEN, Trigger WF-ASSEMBLE in WF-VIDEO).

No workflows were modified and no deployment was performed during this validation.
