# KLIPORA — Workflow, nodes & backend analysis

Thorough check of pipelines, Redis keys, API ↔ n8n contract, and Telegram flow. Use this to verify everything is in proper condition.

---

## 1. Pipeline overview

| Step | Component | Redis / API | Next |
|------|-----------|-------------|------|
| 1 | User or Operations triggers generate | Mission Control `POST /commands/generate-video` | WorkflowController calls n8n WF-GEN webhook |
| 2 | WF-GEN (n8n) | Reads `system:paused`, `used_topics`; writes `job:<id>`, `lpush script_queue` | Script ready; job ID in script_queue |
| 3 | WF-VIDEO (n8n, schedule or triggered) | `rpop script_queue`, `get job:<id>`, Wavespeed API, `lpush render_queue` (package) | Render package in render_queue |
| 4 | WF-ASSEMBLE (n8n, schedule) | `rpop render_queue`, poll Wavespeed, `SETEX pending_approve:<id>`, POST Mission Control `/internal/notify-preview` | Telegram preview message |
| 5 | User in Telegram | Approve / Regenerate / Discard | Mission Control `approve-publish` or `regenerate-job` or `discard-job` |
| 6 | Mission Control | Railway Render (FFmpeg), `rpush publish_queue`, `del pending_approve:<id>` | Video to Telegram |

**Queues (backend & guardian):** `script_queue`, `render_queue`, `publish_queue`, `failed_queue`. Names are consistent across dashboard_api, system_guardian, workflow_controller, and telegram panels.

---

## 2. WF-GEN (Content Generation)

- **Trigger:** POST webhook `/webhook/wf-gen` (Mission Control calls this).
- **Nodes (summary):** Gen Webhook → Check Paused (GET `system:paused`) → IF Not Paused → Parse Job Params → Get Used Topics (`SMEMBERS used_topics`) → Topic Uniqueness Gate → IF Topic Reject → [Reject branch] or [Accept: Mark Topic Used (`SADD used_topics`) → Generate Script (Groq) → Parse Script → Store Job in Redis (`set job:<jobId>`) → Push to script_queue (`lpush script_queue <jobId>`) → Notify Script Ready (Telegram).
- **Topic Uniqueness Gate:** All topics (seed, trend, Telegram, dashboard, GrowthAgent) pass through the same Redis validation. Redis key: **used_topics** (SET). WF-GEN runs **SMEMBERS used_topics**; request topics already in the set are rejected unless `force_reuse` is true; seed topics are picked only from the unused set. Every accepted topic is immediately stored with **SADD used_topics** before script generation.
- **WF-GEN rejection (HTTP 400):** When a topic already exists in `used_topics`, WF-GEN returns HTTP 400 with body: `{ "accepted": false, "reason": "topic_already_used", "message": "...", "topic": "..." }`. This is not treated as a webhook failure.
- **WorkflowController and TopicRejectedError:** On HTTP 400, the controller reads `resp.json()`, extracts `message` and `topic`, and raises **TopicRejectedError(message, topic)**. It does not retry, does not push the job to `failed_queue`, and does not treat the response as webhook failure. **5xx or network errors** are still treated as webhook failures (retry once, then mark job failed and raise WorkflowTriggerError).
- **WF-GEN response contract:** Success: HTTP 200, body `{ "accepted": true, "job_id": "...", "topic": "..." }`. Reject (topic already in used_topics): HTTP 400, body `{ "accepted": false, "reason": "topic_already_used", "message": "...", "topic": "..." }`.
- **Webhook body contract:** `topic`, `genre`, `job_id`, `chat_id`, `duration`, `aspect_ratio`, **`vstyle`**, **`nstyle`**, optional **`force_reuse`** (Parse Job Params reads `body.vstyle` / `body.nstyle`; defaults `dark_cinematic`, `dramatic`).
- **Backend fix applied:** WorkflowController now sends both `visual_style`/`narration_style` and **`vstyle`**/**`nstyle`** (normalized to lowercase underscore) and **`aspect_ratio`** as `9x16` (colon normalized to `x`) so WF-GEN receives the expected keys.
- **Credentials in workflow JSON:** WF-GEN contains hardcoded Upstash URL/token and Groq “YOUR_GROQ_API_KEY”. In production, replace with n8n credentials or env (see N8N_GROQ_KEY.md). WF-GEN “Notify Script Ready” uses a hardcoded bot token; should use n8n credential or env for the bot that sends to the user.

---

## 3. WF-VIDEO (5-scene + voice)

- **Trigger:** Schedule (e.g. 12:00 & 20:00 UAE) or manual; pops from script_queue.
- **Redis:** `rpop script_queue` → job_id; `get job:<id>`; after Wavespeed, `lpush render_queue` (render package JSON). Daily cap: `get/set/incr/expire system:daily_count:YYYY-MM-DD`.
- **Render package:** Must include `job_id`, `chatId`, `clip_urls`, `voice_url`, `genre`, `vstyle`/`nstyle`, etc., so WF-ASSEMBLE and Mission Control can use them.

---

## 4. WF-ASSEMBLE (Assembly & notify)

- **Trigger:** Schedule (e.g. every 3 min or after WF-VIDEO).
- **Redis:** `rpop render_queue` → package; on all complete → `SETEX pending_approve:<jobId> 7200 <json>`; POST to Mission Control `/internal/notify-preview` with `job_id` (and `project_id` for P2).
- **Save pending_approve:** Code node builds JSON with `job_id`, `topic`, `genre`, `clip_urls`, `voice_url`, `music_url`, `chatId`, etc. Key: `pending_approve:<jobId>`.

---

## 5. Mission Control API ↔ workflows

| API | Purpose | Redis / n8n |
|-----|---------|-------------|
| `POST /commands/generate-video` | Start a job | Creates `job:<id>`, calls WF-GEN webhook; payload includes `vstyle`, `nstyle`, `aspect_ratio` (9x16) |
| `POST /internal/notify-preview` | Called by WF-ASSEMBLE | Reads `pending_approve:<id>` (or `p2:pending_approve:<id>`), sends Telegram with Approve/Regenerate/Discard |
| `POST /commands/approve-publish` | User approved | Reads pending job, calls Railway Render, `rpush publish_queue`, deletes pending |
| `POST /commands/regenerate-job` | User regenerate | Re-triggers WF-GEN (same topic), deletes pending |
| `POST /commands/discard-job` | User discard | Deletes pending, no render |

**Project 2:** When request has `project_id: "p2"`, API uses `redis_p2` (prefix `p2:`) and `controller_p2` (webhook `/webhook/wf-gen-p2`). Same queue names and key patterns, with prefix.

---

## 6. System guardian & health

- **check_queues:** `script_queue`, `render_queue`, `publish_queue`, `failed_queue` via `llen` (consistent with workflows).
- **check_system_flags:** `system:paused`, `system:videos_per_day`, `system:daily_count:<date>` (WF-VIDEO uses same daily_count key).
- **detect_stalled_jobs:** Reads script_queue, render_queue, publish_queue; loads `job:<id>`; no dependency on `pending_approve` keys.
- **/health/system:** Returns queues, flags, n8n_failures; never raises (DEGRADED on error).
- **/health/ready:** 503 if Redis unreachable or not configured.

---

## 7. Telegram bot (original architecture)

- **Owner-only:** OWNER_TELEGRAM_ID or TELEGRAM_CHAT_ID; others get “Unauthorized” and their ID to add to env.
- **State:** `telegram:wizard:<chat_id>` (Redis) for generate-video wizard (genre, visual_style, narration_style, duration, aspect_ratio).
- **Generate flow:** Step 1–5 (genre → visual → narration → duration → aspect) → Confirm → `POST /commands/generate-video` with `topic`, `genre`, `visual_style`, `narration_style`, `duration`, `aspect_ratio`, `chat_id` (+ `project_id` for P2). Backend normalizes to `vstyle`/`nstyle` and `aspect_ratio` 9x16 for WF-GEN.
- **Review flow:** Preview message comes from Mission Control (notify_preview); buttons Approve & Publish / Regenerate / Discard call approve-publish, regenerate-job, discard-job with `job_id` (+ `project_id` for P2).

---

## 8. Checklist — everything in proper condition

| Item | Status |
|------|--------|
| Queue names match (script_queue, render_queue, publish_queue, failed_queue) | ✅ Consistent |
| WF-GEN webhook payload has vstyle, nstyle, aspect_ratio (9x16) | ✅ Fixed in WorkflowController |
| Job key format job:<id> and pending_approve:<id> (p2: prefix for P2) | ✅ Consistent |
| notify-preview and approve/regenerate/discard use same Redis/project_id | ✅ Correct |
| Guardian and /health/system use same queue list | ✅ Correct |
| Telegram wizard sends chat_id and optional project_id | ✅ Correct |
| WF-GEN Store Job overwrites job:<id> with script output (vstyle/nstyle in job) | ✅ Downstream gets style |
| WF-ASSEMBLE SETEX 7200 for pending_approve | ✅ 2h TTL |

---

## 9. Optional / follow-up

- **WF-GEN “Notify Script Ready”:** Replace hardcoded Telegram bot token with n8n credential or variable.
- **WF-GEN Groq key:** Ensure set in n8n (Generate Script node) per N8N_GROQ_KEY.md.
- **WF-VIDEO / WF-ASSEMBLE schedules:** Align with desired run times (e.g. 12:00 & 20:00 UAE).
- **Project 2:** Same structure; all keys and webhooks use `p2:` and `/webhook/wf-gen-p2` as designed.
