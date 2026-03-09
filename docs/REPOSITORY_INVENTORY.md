# KLIPORA — Full Repository Inventory & Architecture Comparison

**Authority:** `docs/KLIPORA_SYSTEM_BRAIN.md` and `docs/STRATEGIC_BRAIN.md`.

**Refactor:** Experimental/local modules moved to `archive/`; file-based topic memory removed (used_topics is Redis-only). See `archive/README.md`.

---

## 1. Complete Project Structure

```
KLIPORA/
├── archive/
│   ├── README.md
│   ├── ai_brain.py
│   ├── media_agent.py
│   ├── task_manager.py
│   ├── klipora_controller.py
│   ├── setup_agent.py
│   └── run_company.py.py
├── .cursor/
│   ├── rules/
│   │   ├── klipora-carry-on.mdc
│   │   └── klipora-architecture-lock.mdc
│   └── settings.json
├── .github/
│   └── workflows/
│       └── run-klipora-cycle.yml
├── .vscode/
│   └── launch.json
├── Agents/
│   ├── ceo_agent.py
│   ├── cto_agent.py
│   ├── finance_agent.py
│   ├── growth_agent.py
│   ├── operations_agent.py
│   └── opportunity_engine.py
├── Automation/
│   ├── WF-ASSEMBLE.json
│   ├── WF-CTRL.json
│   ├── WF-GEN.json
│   ├── WF-TREND.json
│   └── WF-VIDEO.json
├── Command_Center/
│   ├── company_brain.py
│   ├── dashboard_api.py
│   ├── event_bus.py
│   ├── KLIPORA_CREWAI_HANDOFF.md.txt
│   ├── New Python Script.py
│   ├── pipeline_monitor.py
│   ├── system_guardian.py
│   ├── telegram_command_center.py
│   └── workflow_controller.py
├── Datasets/
│   └── topic_dataset.json
├── docs/
│   ├── FACELESS_VIDEO_UI_ANALYSIS.md
│   ├── KLIPORA_SYSTEM_BRAIN.md
│   ├── STRATEGIC_BRAIN.md
│   └── WORKFLOW_AND_BACKEND_ANALYSIS.md
├── Infrastructure/
│   ├── api_clients.py
│   ├── config.example.json
│   └── redis_client.py
├── Media_Factory/          (empty — no files)
├── Reports/
│   └── system_report.txt
├── project2/
│   ├── Automation/
│   │   ├── WF-ASSEMBLE-P2.json
│   │   ├── WF-GEN-P2.json
│   │   └── WF-VIDEO-P2.json
│   ├── CREDENTIALS_NEEDED.md
│   ├── KEY=value.env.project2.example
│   ├── OPEN_THESE_URLS.md
│   ├── README.md
│   ├── run_bot.ps1
│   ├── run_setup_p2.ps1
│   ├── SETUP_STEPS.md
│   ├── setup_redis_p2.py
│   └── START_HERE.md
├── scripts/
│   ├── check_telegram_env.py
│   ├── check_telegram_token.py
│   ├── deactivate_n8n_scheduled_workflows.py
│   ├── list_railway_services.ps1
│   ├── ORGANIZE_DRIVE_README.md
│   ├── organize_drive.py
│   ├── reset_telegram_webhook.py
│   └── upload_wf_assemble.py
├── .env.example
├── .gitignore
├── ARCHITECTURE.md
├── ARCHITECTURE_STABILITY.md
├── APPLY_SCHEDULE_NOW.md
├── AUTOMATION_SETUP.md
├── BROWSER_SETUP_SUMMARY.md
├── company_config.json.txt
├── company_memory.md
├── COMPLETE_SETUP_TAKEOVER.md
├── DEPLOY_NOW.md
├── DEPLOYMENT.md
├── Dockerfile
├── GET_ONLINE.md
├── IMMEDIATE_FIX_APPLIED.md
├── KEY=value.env
├── N8N_GROQ_KEY.md
├── N8N_REVIEW_FLOW.md
├── N8N_VIDEO_SCHEDULE.md
├── N8N_WAVESPEED_ACTIVITY.md
├── PIPELINE_FLOW.md
├── pause_automation.py
├── RAILWAY_5_PROJECTS_MAP.md
├── RAILWAY_ACCOUNT_ANALYSIS.md
├── requirements.txt
├── run_company.py
├── run_company.py.py
├── run_telegram_bot.ps1
├── RUN_UPLOAD_WORKFLOW.ps1
├── setup_redis.py
├── start_api.py
├── SETUP_COMPLETE.md
├── STOP_CONTINUOUS_N8N_RUNS.md
├── unpause_automation.py
├── VIDEO_GENERATION_SETUP.md
├── WAVESPEED_AND_RENDER_FIX.md
└── WHY_NOT_COMPLETE.md
```

---

## 2. Focus Directories — File Descriptions

### Agents/

| File | Purpose |
|------|--------|
| **ceo_agent.py** | CEO Agent: aligns daily production limits with company config, sets system knobs (e.g. videos_per_day). Uses Redis + EventBus. |
| **cto_agent.py** | CTO Agent: runs health checks via SystemGuardian/PipelineMonitor, surfaces issues via Event Bus. |
| **growth_agent.py** | Growth Agent: selects high-potential topics using trend signals and CompanyBrain (topic memory). Does not generate content. |
| **operations_agent.py** | Operations Agent: translates production targets into video jobs, uses WorkflowController and Redis queues. Intended to be called from scheduler (cron/n8n). |
| **finance_agent.py** | Finance Agent: tracks spend/revenue in Redis (finance:* keys), enforces budget cap ($440). |
| **opportunity_engine.py** | Opportunity scoring engine: structures/scores business opportunities, persists in Redis (opportunities:*), emits to Event Bus. |
| **ai_brain.py** | **Local script:** calls `ollama run llama3` via subprocess to generate a YouTube script. Not part of architecture (architecture uses WF-GEN + Groq). |
| *(archived)* media_agent.py | Moved to `archive/`. Was local/file-based topic picker; production uses Redis + WF-GEN. |
| **task_manager.py** | **Local execution:** runs controller → media_agent → ai_brain in sequence via subprocess; implements a local “task cycle” outside n8n. |
| **klipora_controller.py** | **Local script:** scans folder existence (Agents, Automation, etc.) and prints “initialization complete.” No Redis or workflow trigger. |
| **setup_agent.py** | **Local/config:** loads `Infrastructure/config.json`, tests Upstash connection; setup/diagnostic helper. |

### Command_Center/

| File | Purpose |
|------|--------|
| **dashboard_api.py** | Mission Control API (FastAPI): Redis, queues, pause/resume, generate-video, run-cycle, experiments, opportunities, health. Key file per architecture. |
| **workflow_controller.py** | Bridge to n8n: builds job payloads, triggers WF-GEN webhook; Redis job contract and queue names. Key file per architecture. |
| **telegram_command_center.py** | Telegram bot: /start, /status, /videos, /experiments, /opportunities, /finance, /automation; owner-only; talks to Mission Control. Key file per architecture. |
| **system_guardian.py** | Monitoring: Redis queues, n8n failures; back-pressure (pause); used by CTO Agent. |
| **pipeline_monitor.py** | Read-only n8n view: list workflows, recent executions; used by SystemGuardian. |
| **event_bus.py** | Redis-backed event bus (events:stream, events:&lt;category&gt;) for agent/dashboard coordination. |
| **company_brain.py** | Topic memory and deduplication (used_topics set), job tracking; Redis-backed. GrowthAgent uses it. |
| **New Python Script.py** | Empty placeholder. |
| **KLIPORA_CREWAI_HANDOFF.md.txt** | Handoff/notes document (CrewAI reference). |

### Automation/

| File | Purpose |
|------|--------|
| **WF-GEN.json** | n8n: content generation (topic, script) → script_queue. Per architecture. |
| **WF-VIDEO.json** | n8n: 5-scene video + voice (Wavespeed) → render_queue. Per architecture. |
| **WF-ASSEMBLE.json** | n8n: assembly, poll Wavespeed, notify Telegram, publish/render. Per architecture. |
| **WF-TREND.json** | n8n: daily trend discovery. Per architecture. |
| **WF-CTRL.json** | n8n: “Telegram Command Center V2” — Telegram trigger + HTTP to load wizard state. Alternative Telegram-by-webhook path; architecture says Python bot is primary. |

### Infrastructure/

| File | Purpose |
|------|--------|
| **redis_client.py** | Upstash Redis REST client; single place for Redis access. Key file per architecture. |
| **api_clients.py** | HTTP clients for n8n (workflow list, execute, etc.). Used by Command Center. |
| **config.example.json** | Example config (n8n_url, upstash, telegram, etc.) for local/copy. |

### Datasets/

| File | Purpose |
|------|--------|
| **topic_dataset.json** | Static topic seed data (e.g. 1000 topics by genre). Used by legacy media_agent; architecture uses Redis trend/topic memory and WF-GEN topic selection. |
| **used_topics.json** | *(removed)* File-based topic memory removed; topic memory is Redis-only `used_topics` SET). |
| *(removed)* used_topics_RESET.json | Removed; topic memory is Redis-only. |

### Media_Factory/

| Item | Purpose |
|------|--------|
| *(directory exists, no files)* | Empty; not referenced in architecture. |

### scripts/

| File | Purpose |
|------|--------|
| **upload_wf_assemble.py** | One-off: upload WF-ASSEMBLE.json to n8n via API. Repo sync / deployment helper; does not run pipeline. |
| **reset_telegram_webhook.py** | Clear Telegram webhook so Python bot can use long polling. Setup/maintenance. |
| **check_telegram_token.py** | Diagnostic: print token source/length (masked). No pipeline execution. |
| **check_telegram_env.py** | Diagnostic: print TELEGRAM_BOT_TOKEN and OWNER_TELEGRAM_ID (masked). No pipeline execution. |
| **deactivate_n8n_scheduled_workflows.py** | Deactivate WF-VIDEO and WF-ASSEMBLE schedules in n8n. Operational/maintenance. |
| **list_railway_services.ps1** | List Railway projects/services via CLI; account analysis. Diagnostic. |
| **organize_drive.py** | E: drive organizer (junk, duplicates, images). General utility; not part of KLIPORA pipeline. |
| **ORGANIZE_DRIVE_README.md** | Docs for organize_drive.py. |

### docs/

| File | Purpose |
|------|--------|
| **KLIPORA_SYSTEM_BRAIN.md** | **Authoritative:** system architecture, Redis schema, automation flow, agents, key files. |
| **STRATEGIC_BRAIN.md** | **Authoritative:** Strategic Brain layer and interaction with the system. |
| **WORKFLOW_AND_BACKEND_ANALYSIS.md** | Pipeline, nodes, Redis/API contract, Telegram flow; reference only. |
| **FACELESS_VIDEO_UI_ANALYSIS.md** | Gap analysis: spec (web UI, series) vs current KLIPORA (Telegram, job); implementation notes. |

### project2/

| File | Purpose |
|------|--------|
| **setup_redis_p2.py** | Initialize p2: Redis keys (videos_per_day, voice_style, etc.) using `Infrastructure.redis_client` with prefix `p2:`. Aligned with architecture (Project 2, same Redis, prefix). |
| **run_bot.ps1** | Load project2 env (KEY=value.env.project2), set PROJECT_ID=p2, run Telegram bot. Entry for P2 bot. |
| **run_setup_p2.ps1** | Run setup_redis_p2.py once. Setup helper. |
| **KEY=value.env.project2.example** | Example env for P2 (Upstash, Telegram, n8n, etc.). |
| **Automation/WF-GEN-P2.json** | P2 variant of WF-GEN. Per architecture. |
| **Automation/WF-VIDEO-P2.json** | P2 variant of WF-VIDEO. Per architecture. |
| **Automation/WF-ASSEMBLE-P2.json** | P2 variant of WF-ASSEMBLE. Per architecture. |
| **README.md, START_HERE.md, SETUP_STEPS.md, CREDENTIALS_NEEDED.md, OPEN_THESE_URLS.md** | Project 2 setup and usage documentation. |

### Root (selected)

| File | Purpose |
|------|--------|
| **setup_redis.py** | One-off: initialize Redis keys/queues from config.json. Referenced in architecture. |
| **pause_automation.py** | Set Redis `system:paused`. Referenced in architecture. |
| **unpause_automation.py** | Clear Redis `system:paused`. Referenced in architecture. |
| **start_api.py** | Start Mission Control API (uvicorn) for Docker/Railway. Aligned. |
| **run_company.py** | **Orchestrator:** one coordination cycle (CEO → CTO → Operations). Designed to be called by scheduler (cron/n8n), not a standalone local pipeline runner. |
| *(archived)* run_company.py.py | Moved to `archive/`. Was legacy script (company_config.json, no Redis/workflows). |
| **run_telegram_bot.ps1** | Wrapper to run Telegram bot with env from repo root. Entry script. |
| **RUN_UPLOAD_WORKFLOW.ps1** | Wrapper to run scripts/upload_wf_assemble.py. Deployment/sync helper. |
| **company_memory.md** | Human-readable company rules/budget; “optional layer” per CompanyBrain; not primary memory (Redis is). |
| **company_config.json.txt** | Likely example or backup of company_config.json. |
| **.github/workflows/run-klipora-cycle.yml** | GitHub Actions: cron 2×/day + manual; POST Mission Control `/commands/run-cycle`. Aligned (schedule triggers API, no local execution). |

---

## 3. Comparison vs docs/KLIPORA_SYSTEM_BRAIN.md

### 3.1 Files that align with the architecture

- **Command_Center:** `dashboard_api.py`, `workflow_controller.py`, `telegram_command_center.py`, `system_guardian.py`, `pipeline_monitor.py`, `event_bus.py`, `company_brain.py`
- **Infrastructure:** `redis_client.py`, `api_clients.py`
- **Agents (architecture-named):** `ceo_agent.py`, `cto_agent.py`, `growth_agent.py`, `operations_agent.py`, `finance_agent.py`; `opportunity_engine.py` (opportunities:* in Redis)
- **Automation:** `WF-GEN.json`, `WF-VIDEO.json`, `WF-ASSEMBLE.json`, `WF-TREND.json`
- **project2:** `setup_redis_p2.py`, `run_bot.ps1`, `run_setup_p2.ps1`, `Automation/WF-GEN-P2.json`, `WF-VIDEO-P2.json`, `WF-ASSEMBLE-P2.json`
- **Root:** `setup_redis.py`, `pause_automation.py`, `unpause_automation.py`, `start_api.py`, `run_company.py` (when invoked by scheduler/API, not as local pipeline)
- **scripts (non-execution):** `upload_wf_assemble.py`, `reset_telegram_webhook.py`, `check_telegram_token.py`, `check_telegram_env.py`, `deactivate_n8n_scheduled_workflows.py`, `list_railway_services.ps1`
- **CI:** `.github/workflows/run-klipora-cycle.yml`
- **docs:** `KLIPORA_SYSTEM_BRAIN.md`, `STRATEGIC_BRAIN.md`, `WORKFLOW_AND_BACKEND_ANALYSIS.md`

### 3.2 Files that appear experimental or local-only

- **archive/** — ai_brain.py, media_agent.py, task_manager.py, klipora_controller.py, setup_agent.py, run_company.py.py (moved; see archive/README.md).
- *(was)* Agents/ai_brain.py — Local Ollama script generation; pipeline uses WF-GEN + Groq.
- **Agents/media_agent.py** — File-based topic picker (Datasets/*.json), hardcoded path; duplicates Redis + WF-GEN.
- **Agents/task_manager.py** — Local “task cycle” (controller → media_agent → ai_brain) via subprocess; bypasses n8n.
- **Agents/klipora_controller.py** — Folder scan only; no Redis or workflow; local diagnostic.
- **Agents/setup_agent.py** — Local config test (config.json, Upstash ping); setup/diagnostic only.
- **run_company.py.py** — Legacy script; prints config, no Redis or workflows.
- **Command_Center/New Python Script.py** — Empty placeholder.
- **scripts/organize_drive.py** + **ORGANIZE_DRIVE_README.md** — General E: drive utility; not part of KLIPORA pipeline.
- **Datasets:** file-based used_topics removed; only `topic_dataset.json` remains (seed data). Runtime topic memory: Redis `used_topics` only.
- **Datasets/topic_dataset.json** — Static seed data; can be reference/import source but architecture uses Redis + WF-GEN for topic selection.
- **Media_Factory/** — Empty directory; not in architecture.
- **Reports/system_report.txt** — Generated report; content is minimal/outdated; not part of architecture.

### 3.3 Files that might conflict with the architecture

| File / area | Conflict / note |
|-------------|------------------|
| **Agents/task_manager.py** | **Local execution script.** Runs a “cycle” locally (controller, media_agent, ai_brain). Architecture: n8n is the only automation execution layer; no local pipeline runners. |
| **Agents/media_agent.py** | **Dual memory:** reads/writes `Datasets/used_topics.json`. Architecture: Redis is the only memory system; `used_topics` is a Redis set. |
| **Agents/ai_brain.py** | **Alternative execution path:** script generation via Ollama. Architecture: script generation is WF-GEN (n8n + Groq). |
| **Datasets/used_topics.json**, **used_topics_RESET.json** | **File-based memory** for “used topics.” Architecture: `used_topics` is a Redis set; no file-based pipeline state. |
| **Automation/WF-CTRL.json** | Optional n8n Telegram webhook flow. Architecture lists WF-TREND, WF-GEN, WF-VIDEO, WF-ASSEMBLE and Python Telegram bot as Control Interface. WF-CTRL is an alternative Telegram path; clarify whether it is “allowed” or deprecated. |
| **run_company.py** | **Context-dependent.** Aligned when invoked by cron/GitHub Actions/Mission Control. If run as a standalone local “run the pipeline” script, it blurs the line (it only runs one agent cycle and does not replace n8n; architecture says run-cycle is triggered via API). |
| **company_memory.md** | CompanyBrain docstring mentions “optional human-readable layer.” Acceptable as long as Redis remains the single source of truth for pipeline and topic state. |

---

## 4. Summary

- **Aligned:** Command_Center (Mission Control, Telegram, WorkflowController, Guardian, EventBus, CompanyBrain), Infrastructure (Redis, n8n client), architecture-named agents (CEO, CTO, Growth, Ops, Finance, Opportunity Engine), all four main n8n workflows + P2 variants, setup/pause/unpause scripts, run_company (when triggered by schedule/API), and CI workflow.
- **Experimental / local-only (archived):** ai_brain, media_agent, task_manager, klipora_controller, setup_agent, run_company.py.py → `archive/`. Other: New Python Script.py, organize_drive, empty Media_Factory, Reports. File-based used_topics removed.
- **Resolved by refactor:** task_manager, media_agent, ai_brain, setup_agent, klipora_controller, run_company.py.py → archived; file-based used_topics removed. **Remaining to clarify:** WF-CTRL (optional vs canonical Telegram), run_company.py context (scheduler vs local).
