# KLIPORA System Brain — Permanent Memory

**This file is the permanent memory of the KLIPORA system. Cursor must always read this file before modifying the architecture.**

---

## AI SESSION INITIALIZATION

Every AI development session **must** begin by reading **docs/AI_BOOTSTRAP.md**.

The bootstrap file instructs the AI to load:

* **Architecture documentation** — System design, pipeline, and authoritative docs (including this file).
* **Structured project state** — **docs/SYSTEM_STATE.json** (current phase, pipeline status, refactor progress, next step).
* **Development roadmap** — Context on what is done and what comes next.

This system provides **persistent context across AI sessions**, so any session can quickly understand the development stage and rules without re-reading all documentation.

---

## SYSTEM NAME

**KLIPORA** — Autonomous AI Media Factory

---

## MISSION

Build a fully autonomous AI media company that generates viral faceless videos and scales to hundreds of videos per day.

---

## GOAL

- **Phase 1:** Stable pipeline producing 2 videos/day  
- **Phase 2:** 20 videos/day  
- **Phase 3:** 100 videos/day  
- **Phase 4:** 1000 videos/day  

---

## CORE ARCHITECTURE

### Strategic Brain

External reasoning intelligence used by the owner (e.g. ChatGPT).

### Company Core

- **CEOAgent** — Sets production limits and strategy  
- **CTOAgent** — Monitors infrastructure health  
- **GrowthAgent** — Selects viral topics  
- **OperationsAgent** — Creates production jobs  
- **FinanceAgent** — Tracks spending and revenue  

### Automation Engine

n8n workflows:

- **WF-TREND** — Daily trend discovery  
- **WF-GEN** — Content generation (topic, script, push to script_queue)  
- **WF-VIDEO** — 5-scene video + voice (Wavespeed), push to render_queue  
- **WF-ASSEMBLE** — Assembly, preview, notify Telegram, push to publish/render  

### Infrastructure

- **Railway** — Mission Control API, n8n, FFmpeg render  
- **Upstash Redis** — Queues, job store, system flags, finance, opportunities  
- **Wavespeed AI** — Scene video + TTS  
- **FFmpeg render service** — Final assembly to MP4  

### Control Interface

- **Telegram Command Center** — User commands, topic/genre, generate video, approve/publish, status  
- **Mission Control API** — Run-cycle, health, queues, pause/unpause, internal webhooks  
- **company_config.json** — Configuration and policy that agents and automation respect (Strategic Brain touchpoint)  

### Production Pipeline

1. **Topic Discovery** (WF-TREND / Telegram topic menu)  
2. **Script Generation** (WF-GEN, Groq)  
3. **Scene Generation** (WF-VIDEO, Wavespeed)  
4. **Video Generation** (Wavespeed clips + voice)  
5. **Assembly** (WF-ASSEMBLE, poll Wavespeed, build package)  
6. **Preview** (Telegram: Approve / Regenerate / Edit / Discard)  
7. **Publish** (Render service → final MP4 → Telegram)  

---

## REDIS MEMORY STRUCTURE

### Queues

- `script_queue` — Job IDs ready for WF-VIDEO  
- `render_queue` — Packages for assembly/render  
- `publish_queue` — Jobs approved for final render  
- `failed_queue` — Failed jobs  

### System Flags

- `system:paused` — When set, WF-GEN / WF-VIDEO / WF-ASSEMBLE no-op at start  
- `system:videos_per_day` — Limit (e.g. 2)  
- `system:daily_count:<date>` — Count of videos generated per day  
- `system:voice_style`, `system:active_genre`, `system:brand_name`  

### Job Storage

- `job:<id>` — Full job payload (script, scenes, metadata)  
- `pending_approve:<id>` — Package awaiting Telegram approve/reject  

### Trend Memory

- `trend:topics:<date>` — Discovered topics for the day  

### Topic Memory (Telegram)

- `telegram:topic_settings:<chat_id>` — topic_mode, topic, custom_prompt (for WF-GEN request body)  
- `used_topics` (SET) — Topics already used for script generation (WF-GEN picks unique)  

### Finance Memory

- `finance:capital_initial`  
- `finance:spent_total`  
- `finance:remaining`  
- `finance:revenue:today`  
- `finance:revenue:month`  
- `finance:spend:category:*`  

### Opportunity Engine

- `opportunities:pending`  
- `opportunities:approved`  
- `opportunities:rejected`  
- `opportunities:history`  

### Experiments

- `experiments:active` — Active experiment list (e.g. Experiment Lab)

### Project 2 (same Redis, key prefix)

- All keys prefixed with `p2:` (e.g. `p2:script_queue`, `p2:job:<id>`, `p2:system:paused`).  
- Same pipeline; Mission Control and run-cycle use `project_id=p2` and Redis prefix `p2:`.  

---

## AGENT RESPONSIBILITIES

| Agent             | Responsibility                          |
|-------------------|----------------------------------------|
| **CEOAgent**      | Sets production limits and strategy    |
| **CTOAgent**      | Monitors infrastructure health         |
| **GrowthAgent**   | Selects viral topics                   |
| **OperationsAgent** | Creates production jobs            |
| **FinanceAgent**  | Tracks spending and revenue           |

---

## AUTOMATION FLOW

```
User request (Telegram: Generate Video / Run cycle)
  → Mission Control API
  → WorkflowController (builds body: genre, vstyle, nstyle, aspect_ratio, topic, chat_id, job_id)
  → WF-GEN (webhook; Check Paused → … → Store Job → Push script_queue → Trigger WF-VIDEO → Notify)
  → script_queue
  → WF-VIDEO (webhook, triggered by WF-GEN; Check Paused → limits → RPOP script_queue → IF not empty → Load Job → Wavespeed 5 scenes + voice → Push render_queue → Trigger WF-ASSEMBLE)
  → render_queue
  → WF-ASSEMBLE (webhook, triggered by WF-VIDEO; Check Paused → RPOP render_queue → IF not empty → Poll Wavespeed → pending_approve → Notify Telegram)
  → Telegram preview (Approve / Regenerate / Edit / Discard)
  → Render service (FFmpeg)
  → Publish → Telegram
```

**Event-driven chaining:** WF-GEN triggers WF-VIDEO via POST to `/webhook/wf-video` after pushing to `script_queue`. WF-VIDEO triggers WF-ASSEMBLE via POST to `/webhook/wf-assemble` after pushing to `render_queue`. No workflow runs without a job: WF-VIDEO still RPOPs and checks queue not empty; WF-ASSEMBLE still RPOPs and checks render_queue not empty before expensive steps.

---

## N8N EXECUTION SCHEDULE

Verified trigger configuration for the automation workflows. Source of truth: workflow JSON in `Automation/` (see also `docs/N8N_TRIGGERS_AUDIT.md`).

| Workflow | Trigger | Schedule | Notes |
|----------|---------|----------|--------|
| **WF-TREND** | cron | `0 8 * * *` | Runs once daily at **08:00 UTC**. |
| **WF-GEN** | webhook | — | Endpoint: **/webhook/wf-gen**. Invoked by Mission Control or callers. After Push to script_queue, triggers WF-VIDEO. |
| **WF-VIDEO** | webhook | — | Endpoint: **/webhook/wf-video**. Triggered by WF-GEN only. Check Paused → limits → RPOP script_queue (queue safety); then scenes + voice → Push render_queue → triggers WF-ASSEMBLE. |
| **WF-ASSEMBLE** | webhook | — | Endpoint: **/webhook/wf-assemble**. Triggered by WF-VIDEO only. Check Paused → RPOP render_queue (queue safety); then poll Wavespeed, notify, etc. |

### Queue-gated execution (WF-VIDEO, WF-ASSEMBLE)

**WF-VIDEO** and **WF-ASSEMBLE** only execute their expensive steps (Wavespeed API, polling, notify) when their Redis queues contain work. Each run: Check Paused → **RPOP** the queue → **IF** result non-empty → continue; otherwise the run stops. Empty queue therefore causes no downstream API calls or heavy processing.

---

## BROWSER AUTOMATION LAYER

**Browserbase** provides a UI-level automation layer that allows the system to inspect and control web dashboards such as:

* n8n  
* Railway deployments  
* Telegram bot interface  
* monitoring dashboards  

Browserbase is used for **inspection**, **configuration verification**, and **UI debugging**. It is used for KLIPORA system management only when a task **cannot be performed through APIs**.

### Automation priority order

1. **Mission Control API** — Commands, health, queues, generate-video, approve-publish, run-cycle, etc.
2. **Redis commands** — Direct read/write of queues, flags, job store, used_topics (e.g. via Mission Control or Redis client).
3. **n8n API** — List workflows, get/update workflow settings, activate/deactivate, execution history, credentials (where supported).
4. **Browserbase UI automation** — Last resort when the above cannot achieve the goal.

### When to use Browserbase

- Opening the n8n dashboard and navigating workflows.
- Verifying workflow activation state (active/inactive) when API is unclear or unavailable.
- Checking workflow execution logs and run history.
- Inspecting node-level errors and execution details in the UI.
- Enabling or disabling workflows when the n8n API does not support it or fails.
- Verifying Telegram webhook configuration (URL, secret) in n8n or related UIs.
- Observing system state visually (dashboards, queues, status) when API or Redis views are insufficient.

### Rule: Prefer API over browser for changes

**Do not modify workflow logic (nodes, connections, credentials, triggers) through the browser unless the same change cannot be made through the n8n API or by updating workflow JSON in the repo and re-importing.** Use Browserbase for inspection and verification first; use API or repo for mutations whenever possible.

---

## WF-GEN TOPIC UNIQUENESS GATE AND RESPONSES

### 1. Topic Uniqueness Gate

- All topics pass through the same Redis validation in WF-GEN, regardless of source: **seed** (inline genre list), **trend** (`trend:topics:<date>`), **Telegram**, **dashboard**, or **GrowthAgent**.
- **Redis key:** `used_topics` (SET).
- **Validation:** WF-GEN runs **SMEMBERS used_topics** before accepting any topic.
- **On accept:** The accepted topic is immediately stored with **SADD used_topics** (Mark Topic Used node). This applies to every accepted topic (request or seed).

### 2. WF-GEN rejection behavior

When a topic already exists in `used_topics` (and `force_reuse` is not set), WF-GEN returns **HTTP 400** with a JSON body:

```json
{
  "accepted": false,
  "reason": "topic_already_used",
  "message": "...",
  "topic": "..."
}
```

This is **not** a webhook failure; it is a normal business response indicating the topic was rejected.

### 3. WorkflowController behavior

`workflow_controller.py` defines **TopicRejectedError(message, topic)**.

When WF-GEN returns HTTP 400:

- The controller reads **resp.json()** and extracts `message` and `topic`.
- It raises **TopicRejectedError(message, topic)**.
- It does **not** retry the webhook call.
- It does **not** push the job to `failed_queue`.
- It does **not** treat this as a webhook failure (no `failure_reason: "n8n_webhook_unreachable"`).

Only connection errors or 5xx responses are treated as webhook failures.

### 4. 5xx or network errors

These are still treated as webhook failures: the controller retries once, then marks the job failed, pushes to `failed_queue`, and raises **WorkflowTriggerError**.

---

## IMPORTANT RULE

**This file is the permanent memory of the KLIPORA system. Cursor must always read this file before modifying the architecture.**

---

## KEY FILES (reference)

- **Strategic Brain (external reasoning):** `docs/STRATEGIC_BRAIN.md`  
- **Architecture / pipeline:** `docs/ARCHITECTURE.md`, `docs/WORKFLOW_AND_BACKEND_ANALYSIS.md`  
- **Mission Control / API:** `Command_Center/dashboard_api.py`, `Command_Center/workflow_controller.py`  
- **Telegram:** `Command_Center/telegram_command_center.py`  
- **Redis:** `Infrastructure/redis_client.py`, `setup_redis.py`  
- **n8n workflows:** `Automation/WF-GEN.json`, `Automation/WF-VIDEO.json`, `Automation/WF-ASSEMBLE.json`, `Automation/WF-TREND.json`  
- **Pause/unpause:** `pause_automation.py`, `unpause_automation.py`; `STOP_CONTINUOUS_N8N_RUNS.md`  
- **Project 2:** `project2/` (same backend; `p2:` Redis prefix, P2 workflows in `project2/Automation/`).
