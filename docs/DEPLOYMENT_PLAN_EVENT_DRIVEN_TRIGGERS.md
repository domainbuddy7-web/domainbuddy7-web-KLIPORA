# KLIPORA deployment plan: event-driven trigger nodes

**Status:** Plan only. No deployment or n8n changes yet.

**Goal:** Align live n8n workflows with repository by adding the two missing HTTP trigger nodes so the pipeline becomes hybrid (event-driven + schedule polling fallback).

---

## 1. Node JSON to insert

### 1.1 WF-GEN: Trigger WF-VIDEO

**Workflow ID (live):** `VCw1KVSRcgRmlujA`

**Node to add** (exact JSON from `Automation/WF-GEN.json`):

```json
{
  "id": "gen-10b",
  "name": "Trigger WF-VIDEO",
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4,
  "position": [2300, 300],
  "parameters": {
    "method": "POST",
    "url": "https://n8n-production-2762.up.railway.app/webhook/wf-video",
    "sendBody": false
  }
}
```

**Note:** If the live workflow already uses different `id` conventions, generate a new unique id (e.g. UUID or `gen-10b`) to avoid collisions. Position `[2300, 300]` can be adjusted so the node fits between "Push to script_queue" and "Notify Script Ready" on the canvas.

---

### 1.2 WF-VIDEO: Trigger WF-ASSEMBLE

**Workflow ID (live):** `jTJnXHXjqo7FwGZV`

**Node to add** (exact JSON from `Automation/WF-VIDEO.json`):

```json
{
  "id": "vid-trigger-asm",
  "name": "Trigger WF-ASSEMBLE",
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4,
  "position": [3250, 400],
  "parameters": {
    "method": "POST",
    "url": "https://n8n-production-2762.up.railway.app/webhook/wf-assemble",
    "sendBody": false
  }
}
```

**Note:** Similarly, ensure `id` is unique in the live workflow; adjust `position` if needed.

---

## 2. Connection JSON to update

### 2.1 WF-GEN (live)

**Current connections (relevant part):**

- `Push to script_queue` → `Notify Script Ready`

**Target connections after patch:**

- `Push to script_queue` → **`Trigger WF-VIDEO`**
- **`Trigger WF-VIDEO`** → `Notify Script Ready`

**Connection changes:**

| Source node           | Current target(s)   | New target(s)      |
|----------------------|---------------------|--------------------|
| Push to script_queue | Notify Script Ready | **Trigger WF-VIDEO** |
| Trigger WF-VIDEO     | *(none)*            | **Notify Script Ready** |

**Exact connection object to add/update in `workflow.connections`:**

```json
"Push to script_queue": { "main": [[{ "node": "Trigger WF-VIDEO", "type": "main", "index": 0 }]] },
"Trigger WF-VIDEO": { "main": [[{ "node": "Notify Script Ready", "type": "main", "index": 0 }]] }
```

All other connections in WF-GEN remain unchanged.

---

### 2.2 WF-VIDEO (live)

**Current connections (relevant part):**

- `Set Count Expiry 24h` → *(no outgoing)*

**Target connections after patch:**

- `Set Count Expiry 24h` → **`Trigger WF-ASSEMBLE`**
- `Trigger WF-ASSEMBLE` → *(no outgoing; end of branch)*

**Connection changes:**

| Source node            | Current target(s) | New target(s)       |
|------------------------|------------------|---------------------|
| Set Count Expiry 24h   | *(none)*         | **Trigger WF-ASSEMBLE** |
| Trigger WF-ASSEMBLE    | *(none)*         | *(none)*            |

**Exact connection object to add/update in `workflow.connections`:**

```json
"Set Count Expiry 24h": { "main": [[{ "node": "Trigger WF-ASSEMBLE", "type": "main", "index": 0 }]] }
```

All other connections in WF-VIDEO remain unchanged.

---

## 3. Insertion point in the workflow graph

### 3.1 WF-GEN

- **Insertion point:** Between **Push to script_queue** and **Notify Script Ready**.
- **Flow before:**  
  … → Store Job in Redis → **Push to script_queue** → **Notify Script Ready** → Format Success Response → Respond Success.
- **Flow after:**  
  … → Store Job in Redis → **Push to script_queue** → **Trigger WF-VIDEO** → **Notify Script Ready** → Format Success Response → Respond Success.

No other paths are changed. Reject branch and all nodes up to Push to script_queue are untouched.

### 3.2 WF-VIDEO

- **Insertion point:** After **Set Count Expiry 24h** (currently the end of the success path).
- **Flow before:**  
  … → Push to render_queue → INCR Daily Count → **Set Count Expiry 24h** → *(end)*
- **Flow after:**  
  … → Push to render_queue → INCR Daily Count → **Set Count Expiry 24h** → **Trigger WF-ASSEMBLE** → *(end)*

Schedule trigger (Queue Poller), RPOP script_queue, and all scene/voice/render logic are unchanged.

---

## 4. Diff-style deployment plan

| Workflow | Action   | Object / change |
|----------|----------|------------------|
| **WF-GEN** (VCw1KVSRcgRmlujA) | **ADD node** | `Trigger WF-VIDEO` (node JSON above). |
| **WF-GEN** | **EDIT connections** | `Push to script_queue`: target `Notify Script Ready` → `Trigger WF-VIDEO`. **ADD** `Trigger WF-VIDEO` → `Notify Script Ready`. |
| **WF-VIDEO** (jTJnXHXjqo7FwGZV) | **ADD node** | `Trigger WF-ASSEMBLE` (node JSON above). |
| **WF-VIDEO** | **EDIT connections** | `Set Count Expiry 24h`: add outgoing → `Trigger WF-ASSEMBLE`. |

**Implementation options:**

1. **n8n UI:** Open each workflow, add the HTTP Request node with the same name/URL/method, then reconnect: Push to script_queue → Trigger WF-VIDEO → Notify Script Ready; Set Count Expiry 24h → Trigger WF-ASSEMBLE.
2. **n8n API:** GET full workflow JSON, insert the node into `nodes` array and update `connections` as above, then PUT the workflow back (ensure `id` and any version fields are consistent).
3. **Re-import from repo:** Replace live workflow with import from `Automation/WF-GEN.json` and `Automation/WF-VIDEO.json` (will overwrite any live-only changes; use only if live and repo are otherwise aligned).

---

## 5. Schedule-based queue polling unchanged

- **WF-VIDEO** still has:
  - **Queue Poller** (schedule trigger) and **RPOP script_queue**.
  - Same logic: when the schedule runs, it pops from `script_queue`; if empty, the run effectively no-ops.
- **WF-ASSEMBLE** still has:
  - **Assembly Poller** (schedule trigger) and **RPOP render_queue**.
  - Same logic: when the schedule runs, it pops from `render_queue`; if empty, the run no-ops.

Adding the trigger nodes only **adds** an event-driven path: when WF-GEN (or WF-VIDEO) finishes, it POSTs to the next workflow’s webhook so the next run can start immediately. Schedule runs continue to act as a **fallback** if the webhook is not called or fails. No schedule or queue logic is removed or altered.

---

## 6. Result: hybrid pipeline

After applying the patch:

- **Event-driven:**  
  WF-GEN → (POST /webhook/wf-video) → WF-VIDEO → (POST /webhook/wf-assemble) → WF-ASSEMBLE.
- **Fallback:**  
  WF-VIDEO and WF-ASSEMBLE still run on schedule and poll `script_queue` and `render_queue`.

So the result is a **hybrid pipeline**: event-driven triggers for lower latency when the chain runs normally, plus Redis queue polling as fallback.

---

## 7. Checklist before deployment

- [ ] Backup or export current live workflows (n8n UI or API).
- [ ] Confirm n8n base URL for webhooks is correct in node URLs (e.g. `https://n8n-production-2762.up.railway.app`).
- [ ] Apply WF-GEN patch (add node + connection updates).
- [ ] Apply WF-VIDEO patch (add node + connection updates).
- [ ] Test: trigger WF-GEN (e.g. via Mission Control or webhook), verify WF-VIDEO runs without waiting for schedule, then WF-ASSEMBLE runs.
- [ ] Verify schedule runs still work (e.g. let Queue Poller / Assembly Poller run and confirm they still poll queues).

---

**Do not deploy or modify n8n until you are ready to apply this plan.**

---

## 8. Script output

To regenerate the proposed node and connection JSON from the repository, run:

```bash
cd /d E:\KLIPORA
python scripts/verify_klipora_pipeline_links.py
```

The script prints a **PROPOSED WORKFLOW PATCH** section with the exact node JSON to add and the connection lines to add/update for WF-GEN and WF-VIDEO.
