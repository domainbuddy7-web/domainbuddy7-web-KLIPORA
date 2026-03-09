# KLIPORA architecture and stability

Summary of the current architecture and stability measures.

---

## Architecture (high level)

- **Mission Control API** (Railway): FastAPI in `Command_Center/dashboard_api.py`. Reads/writes Redis, calls n8n, runs agents (CEO/CTO/Ops) on run-cycle.
- **Telegram bot** (local): `Command_Center/telegram_command_center.py`. Polling; owner-only; talks to Mission Control for status, generate-video, run-cycle.
- **n8n workflows** (Railway): WF-GEN (script), WF-VIDEO (Wavespeed), WF-ASSEMBLE (poll + notify), WF-CTRL (optional Telegram webhook).
- **Redis** (Upstash): Queues (`script_queue`, `render_queue`, `publish_queue`, `failed_queue`), job store (`job:<id>`), flags (`system:paused`, etc.), events (`events:stream`, `events:<category>`).
- **Agents**: CEO (daily limit), CTO (health), Operations (production cycle). Used by `/commands/run-cycle`.

---

## Stability measures

### Workflow controller

- **`start_generation_job`**: Calls n8n WF-GEN webhook with **one retry** on timeout/connection error. On final failure: job is marked **failed**, pushed to **failed_queue**, and **`WorkflowTriggerError`** is raised so the API can return **503** instead of 500.
- **`WorkflowTriggerError`**: Raised when n8n webhook is unreachable; dashboard and callers catch it and return a clear message.

### Dashboard API

- **`/commands/generate-video`**: Catches **`WorkflowTriggerError`** and returns **503** with message `n8n webhook unreachable; job not started`.
- **`/commands/run-cycle`**: Full cycle (CEO → CTO → Ops) wrapped in **try/except**. On any exception: Telegram alert with error, then **503** with detail so the API does not 500.
- **`/commands/approve-publish`**: Wrapped in **try/except**; on success and when render is called, records **$0.50 api_usage** via finance agent; on failure returns **503**.
- **`/commands/regenerate-job`**: Catches **`WorkflowTriggerError`** and returns **503** if n8n unreachable.
- **`/commands/discard-job`** and **`/commands/update-job-metadata`**: Wrapped in **try/except**; return **503** on unexpected errors.
- **`/internal/notify-preview`**: Never raises; on Telegram send failure returns 200 with `sent: false` so n8n does not get 500.
- **`/health/ready`**: Readiness probe; **200** if Redis reachable, **503** otherwise (whitelisted in middleware).
- **`/health/system`**: Already hardened: guardian checks (queues, flags, n8n failures) never raise; on exception returns 200 with **DEGRADED** and minimal payload.
- **Lifespan**: FastAPI **lifespan** context for startup/shutdown (extensible for cleanup).

### Event bus

- **`publish`**: **No-op on Redis failure** so callers (dashboard, agents) never crash when the event stream is down.

### System guardian

- **`detect_stalled_jobs`**: **Defensive per queue and per job**: `lrange` and `load_job` in try/except so one bad key or malformed job does not break the rest.
- **`check_queues`** / **`check_system_flags`**: Already defensive (safe int parsing, fallback defaults).

### Redis client

- **`command`**: **One retry** on `OSError`, `TimeoutError`, `URLError` for transient network blips before returning `None`.

### Pipeline monitor

- **`summarize_failures`**: **try/except** around n8n call; returns `{}` on failure so `/health/system` does not 500.

---

## Error flow

| Component        | On failure behaviour |
|-----------------|----------------------|
| n8n webhook     | Retry once → mark job failed, push to failed_queue, 503 from API |
| Redis (event bus) | Publish no-op; caller continues |
| Redis (guardian)  | Safe defaults / skip bad item |
| Redis (command)   | Retry once → return None |
| run-cycle agents | Catch all → Telegram alert + 503 |
| /health/system   | Catch all → 200 DEGRADED + minimal payload |
| approve-publish  | try/except → 503; record $0.50 spend when render called |
| regenerate-job   | WorkflowTriggerError → 503 |
| discard-job / update-job-metadata | try/except → 503 |
| notify-preview   | try/except → 200 with sent: false on failure |
| /health/ready   | 503 if Redis unreachable or not configured |

---

## Files touched for stability

- `Command_Center/workflow_controller.py` — WorkflowTriggerError, retry, failed job handling
- `Command_Center/dashboard_api.py` — generate_video 503, run-cycle try/except, lifespan
- `Command_Center/event_bus.py` — publish no-op on error
- `Command_Center/system_guardian.py` — detect_stalled_jobs defensive
- `Infrastructure/redis_client.py` — command() retry once
