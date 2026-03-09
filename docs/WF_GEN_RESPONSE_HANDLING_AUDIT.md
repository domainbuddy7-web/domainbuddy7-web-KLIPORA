# WF-GEN Response Handling Audit

**Scope:** How Command Center components handle WF-GEN’s two response types (success 200, reject 400).  
**No code was modified.**

---

## WF-GEN response contract (current)

| Outcome   | HTTP | Body |
|----------|------|------|
| **Success** | 200 | `{ "accepted": true, "job_id": "...", "topic": "..." }` |
| **Reject**  | 400 | `{ "accepted": false, "reason": "topic_already_used", "message": "...", "topic": "..." }` |

---

## 1. WorkflowController (`workflow_controller.py`)

**Flow:** `start_generation_job()` creates a job in Redis, builds the payload, calls `n8n.trigger_webhook(path, payload)`, then `resp.raise_for_status()`.

- **Response body:** Never read. The controller does not use `resp.json()`, `resp.status_code`, or `resp.text`.
- **Success (200):** `raise_for_status()` does not raise. Controller updates job status to `script_in_progress` and returns the **locally created** job dict. Outcome is correct (same `job_id` as in the payload); the WF-GEN success body is simply ignored.
- **Reject (400):** `raise_for_status()` raises `requests.HTTPError` (e.g. `400 Client Error`). The exception is caught, retried once, then the job is marked failed with `failure_reason: "n8n_webhook_unreachable"`, pushed to `failed_queue`, and `WorkflowTriggerError(f"n8n webhook unreachable: {last_err}")` is raised. The 400 response body (`accepted: false`, `reason`, `message`, `topic`) is **never read**. Topic rejection is treated the same as a 503 or connection error.

**Verdict:** Success is handled correctly in practice. HTTP 400 (topic rejected) is not distinguished from other failures; WF-GEN’s reject payload is not processed.

---

## 2. Dashboard API (`dashboard_api.py`)

**Endpoints that call WF-GEN:** `POST /commands/generate-video`, `POST /commands/regenerate-job`.

**Behavior:**

- Both call `ctrl.start_generation_job(...)` inside a `try` and catch `WorkflowTriggerError`.
- On success: return `{"job": job}` (generate-video) or `{"status": "ok", "job_id": ...}` (regenerate-job).
- On `WorkflowTriggerError`: raise `HTTPException(status_code=503, detail=f"n8n webhook unreachable; job not started. {e!s}")` (generate-video) or `HTTPException(status_code=503, detail=f"n8n webhook unreachable: {e!s}")` (regenerate-job).

So:

- **Success:** Correctly returned as 200 with job/status; callers get the expected success payload.
- **Topic reject (400 from WF-GEN):** Becomes a **503** from the API with a generic detail string (the exception message, e.g. including "400 Client Error"). The API never returns 400 for topic rejection and never forwards WF-GEN’s `reason` or `message`. Callers cannot tell “topic already used” from “n8n down” or other webhook failures.

**Verdict:** Success is correct. Topic rejection is not surfaced as 400 or with topic-specific messaging; no user-facing feedback that the topic was rejected for reuse.

---

## 3. Telegram Command Center (`telegram_command_center.py`)

**Flow:** Generate-video is triggered from the “Confirm” action (`action_confirm_video`). The bot builds `body` (topic, genre, etc.), calls `_api_post("/commands/generate-video", body)`, then branches on `result`.

**_api_post behavior:**

- Does not raise on HTTP errors. On non-OK response it returns a dict with `"detail"` (from the API’s JSON body) or `"message"` or `"HTTP {code}"`.
- So when the API returns 503, `result` = e.g. `{"detail": "n8n webhook unreachable; job not started. 400 Client Error: ..."}`.

**action_confirm_video handling:**

- `if result.get("job")` → show “Pipeline started” and job id.
- `elif not result and not MISSION_CONTROL_URL` → “Mission Control URL not set”.
- `elif not result` → “Could not reach Mission Control API”.
- `else` → `detail = result.get("detail") or result`, then show `"❌ Failed: {detail}"`. If the string contains “n8n” or “webhook” or “503”, a tip about the Groq API key is appended.

So when WF-GEN returns 400 (topic rejected):

- The API returns 503 with a generic detail.
- The bot shows “❌ Failed: n8n webhook unreachable; job not started. 400 Client Error…” (plus optional tip). The user does **not** see “Topic already used” or “Re-send with force_reuse=true” from the bot’s handling of the API response.
- WF-GEN itself has a **Notify Topic Rejected** node that sends a Telegram message to `chat_id` with “Topic already used. Re-send with force_reuse=true…”. So the user may get that message from the workflow, but it is independent of the bot’s API error handling. If that node fails or `chat_id` is wrong, the user only sees the generic “Failed: n8n webhook unreachable…” from the bot.

**Verdict:** Success is correct (job in result → “Pipeline started”). Topic rejection: the bot does not show topic-specific feedback; feedback depends on WF-GEN’s own Telegram message, which may or may not be received. No use of WF-GEN’s reject body (reason/message) in the bot.

---

## 4. Summary table

| Requirement                          | WorkflowController | Dashboard API | Telegram bot |
|--------------------------------------|--------------------|---------------|--------------|
| **1. Correctly process success**     | ✅ Returns job on 200 (does not read body) | ✅ 200 + job/status | ✅ Shows “Pipeline started” when `result.job` present |
| **2. Correctly handle HTTP 400 reject** | ❌ Treats 400 as generic failure; does not read body | ❌ Returns 503, does not return 400 or forward reject body | ❌ Sees 503 + generic detail only |
| **3. User feedback when topic rejected** | N/A                | ❌ No topic-specific message | ⚠️ Only if WF-GEN “Notify Topic Rejected” succeeds; bot shows generic error |

---

## 5. Conclusions

1. **Success responses** are handled correctly end-to-end: 200 from WF-GEN leads to job return and appropriate UI (dashboard and Telegram).
2. **HTTP 400 (topic rejected)** is not handled specifically: the controller raises on any non-2xx, the API always returns 503, and the reject body is never read or forwarded. No component distinguishes “topic already used” from other webhook failures.
3. **User feedback on topic rejection** is not guaranteed: the only topic-specific text (“Topic already used. Re-send with force_reuse=true”) is sent by WF-GEN’s Telegram node. The bot’s own error path shows a generic “n8n webhook unreachable” style message. To provide consistent, topic-specific feedback, the backend would need to (a) read the 400 response body in the controller, (b) expose a 400 (or 409) with WF-GEN’s message in the API when reason is topic_already_used, and (c) have the Telegram bot display that message (and optionally suggest force_reuse) when the API returns that error.

No code was modified in this audit.
