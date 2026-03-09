# KLIPORA architecture

Single reference for system design, data flow, and where to continue development.

---

## High-level architecture

| Component | Role |
|-----------|------|
| **Mission Control API** (Railway) | FastAPI in `Command_Center/dashboard_api.py`. Reads/writes Redis, calls n8n webhooks, runs agents (CEO/CTO/Ops) on run-cycle. |
| **Telegram bot** (local or cloud) | `Command_Center/telegram_command_center.py`. Polling; owner-only; talks to Mission Control for status, generate-video, approve-publish, run-cycle. |
| **n8n workflows** (Railway) | WF-GEN (script), WF-VIDEO (Wavespeed), WF-ASSEMBLE (poll + notify), WF-CTRL (optional Telegram webhook). |
| **Redis** (Upstash) | Queues (`script_queue`, `render_queue`, `publish_queue`, `failed_queue`), job store (`job:<id>`), flags (`system:paused`, etc.), events (`events:stream`, `events:<category>`). |
| **Agents** | CEO (daily limit), CTO (health), Operations (production cycle). Used by `/commands/run-cycle`. |

Optional: **WF-CTRL** in n8n can handle Telegram via webhook (alternative to the Python bot). The Python bot is the primary path for Mission Control commands.

---

## Pipeline flow

1. **Generate** — User or Operations agent triggers generation → Mission Control calls n8n WF-GEN webhook → WF-GEN picks topic, writes script, pushes to `script_queue`, triggers WF-VIDEO.
2. **Video** — WF-VIDEO submits 5 clips + voice to Wavespeed, pushes render package (prediction IDs) to `render_queue`.
3. **Assemble** — WF-ASSEMBLE polls `render_queue`, polls Wavespeed until complete, saves to `pending_approve:{job_id}`, calls Mission Control `/internal/notify-preview`.
4. **Review** — Mission Control sends Telegram message with Approve / Regenerate / Discard. On Approve → Mission Control calls Railway Render (FFmpeg) → final MP4 to Telegram.

See **PIPELINE_FLOW.md** for the detailed job → Wavespeed → FFmpeg → Telegram flow.

---

## Redis key schema (Project 1)

| Key pattern | Purpose |
|-------------|---------|
| `script_queue` | List of job IDs to be processed by WF-VIDEO |
| `render_queue` | List of render packages (Wavespeed pred IDs) |
| `publish_queue` | List of job IDs approved for publish |
| `failed_queue` | List of failed job IDs |
| `job:<id>` | Job payload (topic, script, scenes, etc.) |
| `pending_approve:<job_id>` | Pending review package (clip_urls, voice_url, chatId, etc.); TTL 7200s |
| `used_topics` | Set of used topic strings |
| `system:paused` | Exists = system paused |
| `system:videos_per_day`, `system:daily_count:YYYY-MM-DD` | Daily cap and counter |

---

## Project 2 (same Upstash + Railway)

- **One Upstash DB, one Railway Mission Control service.** Project 2 uses Redis key prefix **`p2:`** (e.g. `p2:script_queue`, `p2:pending_approve:<id>`). Implemented in `Infrastructure/redis_client.py` via `get_redis_client(prefix="p2:")`.
- **One n8n instance.** Project 2 workflows (in `project2/Automation/`) use webhook path `wf-gen-p2` and all Redis keys prefixed with `p2:`.
- **Mission Control** uses `redis_p2` and `controller_p2` when request body has `project_id: "p2"`. Telegram P2 bot sets `PROJECT_ID=p2` and sends `project_id` on generate/approve/regenerate/discard.
- **New credential for P2:** only a **new Telegram bot**; copy Upstash URL/token, N8N_URL, N8N_API_KEY, MISSION_CONTROL_URL from Project 1 and set **N8N_WEBHOOK_WF_GEN_P2** = `/webhook/wf-gen-p2`.

---

## Key files

| Area | Files |
|------|--------|
| API | `Command_Center/dashboard_api.py` |
| Workflow trigger | `Command_Center/workflow_controller.py` |
| Telegram bot | `Command_Center/telegram_command_center.py` |
| Redis | `Infrastructure/redis_client.py` |
| Health / guardian | `Command_Center/system_guardian.py`, `Command_Center/pipeline_monitor.py` |
| Agents | `Agents/ceo_agent.py`, `Agents/cto_agent.py`, `Agents/operations_agent.py`, `Agents/growth_agent.py` |
| Events | `Command_Center/event_bus.py` |
| Stability details | **ARCHITECTURE_STABILITY.md** (error handling, retries, 503 behaviour) |

---

## Continue development

- **N8N_WEBHOOK_URL** — Set in Railway (n8n service) so n8n can auto-register Telegram webhook on restart. See *KLIPORA_CREWAI_HANDOFF.md.txt* Section 10 (Issue 1).
- **Topic dataset** — Currently 250 topics (25 per genre × 10). Expanding to 1000 requires new content; WF-GEN and GrowthAgent topic sources need to stay in sync.
- **WF-VIDEO chatId** — Ensure `chat_id` is passed through the pipeline so WF-ASSEMBLE and Mission Control send the review message to the correct user (job has `chatId`; Mission Control falls back to `TELEGRAM_CHAT_ID`).
- **Render service body** — Railway Render `/render` must accept the payload sent by Mission Control (clips, voiceover, chatId, botToken, optional music). If the job is stored URL-encoded in Redis, decode before sending.
- **Run-cycle and Project 2** — Run-cycle accepts optional `project_id`; when `project_id=p2`, CEO/CTO/Ops use `redis_p2` and `controller_p2`. P2 bot sends `project_id` on run-cycle.

- **Frontend** — Mission Control is API-only; a React/Next.js dashboard (or similar) can consume the same endpoints for a visual control panel.

---

## References

- **ARCHITECTURE_STABILITY.md** — Stability measures, error flow, files touched for resilience.
- **PIPELINE_FLOW.md** — Job → Wavespeed → FFmpeg → Telegram.
- **Command_Center/KLIPORA_CREWAI_HANDOFF.md.txt** — Full handoff: credentials, n8n workflow IDs, Redis schema, known issues, programmatic workflow update.
- **project2/README.md**, **project2/SETUP_STEPS.md** — Project 2 setup (same Upstash/Railway).
