# Archive — Experimental / local-only modules

These modules were moved here to align the repository with the architecture in `docs/KLIPORA_SYSTEM_BRAIN.md`. They are **archived for reference**, not deleted.

**Architecture rules:** n8n workflows are the only automation execution layer; Redis is the only memory system. These modules conflict with those rules.

## Classification

| File | Original location | Classification | Reason |
|------|-------------------|----------------|--------|
| **ai_brain.py** | Agents/ | Experimental / local execution | Script generation via local Ollama; production uses WF-GEN (n8n + Groq). |
| **media_agent.py** | Agents/ | Experimental / local + file memory | File-based topic picker (Datasets/used_topics.json); production uses Redis `used_topics` set and WF-GEN. |
| **task_manager.py** | Agents/ | Local execution | Runs a “task cycle” (controller → media_agent → ai_brain) via subprocess; bypasses n8n. |
| **klipora_controller.py** | Agents/ | Local-only diagnostic | Folder existence scan only; no Redis or workflow. |
| **setup_agent.py** | Agents/ | Local setup/diagnostic | Config load and Upstash/n8n connectivity tests; not part of production pipeline. |
| **run_company.py.py** | repo root | Legacy / local | Prints company_config.json; no Redis or workflows. |

## Production architecture (unchanged)

- **Agents/** — CEO, CTO, Growth, Operations, Finance agents; opportunity_engine.
- **Command_Center/** — Mission Control API, WorkflowController, Telegram bot, SystemGuardian, PipelineMonitor, EventBus, CompanyBrain.
- **Automation/** — WF-GEN, WF-VIDEO, WF-ASSEMBLE, WF-TREND (n8n).
- **Infrastructure/** — redis_client, api_clients.

Topic memory in production: Redis key `used_topics` (SET) only. No file-based topic state.
