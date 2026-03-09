# KLIPORA AI BOOTSTRAP

Every development session **must** load the architecture and state files **before** making any changes. This ensures decisions and edits stay aligned with the system design and current runtime state.

---

## Architecture documents to load

Load these documents at the start of each session:

* **docs/KLIPORA_SYSTEM_BRAIN.md**
* **docs/STRATEGIC_BRAIN.md**
* **docs/WORKFLOW_AND_BACKEND_ANALYSIS.md**
* **docs/TELEGRAM_DASHBOARD_ARCHITECTURE_DESIGN.md**

Also load:

* **docs/SYSTEM_STATE.json**

---

## Rules for the system

* **Redis is the only runtime memory.** All queues, job store, flags, and pipeline state live in Redis (Upstash). No file-based or other memory systems for pipeline state.
* **n8n workflows are the only automation execution layer.** WF-TREND, WF-GEN, WF-VIDEO, WF-ASSEMBLE (and P2 equivalents) are the automation engine. No alternative workflow runners or execution layers.
* **Telegram UI must remain modular.** Structure and components must stay separated and composable.
* **UI must not directly perform API or Redis operations.** All external calls and Redis access go through the services layer only.
* **Any architectural change must be reflected in the docs.** Update the authoritative docs when design or architecture changes.

---

## BROWSER AUTOMATION CAPABILITY

The KLIPORA system includes **Browserbase** integration, which allows the AI to use an embedded browser to interact with web interfaces when API access is unavailable.

### Primary control order

1. Mission Control API  
2. Redis  
3. n8n API  
4. Browserbase automation  

Browserbase should only be used when:

* API endpoints are unavailable  
* configuration must be done through a web UI  
* debugging requires inspecting the web interface  
* workflows must be activated or inspected in n8n UI  

### Examples of allowed browser automation tasks

* Opening the n8n dashboard  
* Verifying workflow activation  
* Inspecting workflow execution logs  
* Checking Telegram webhook configuration  
* Debugging UI-based system errors  

### Warning

**Browser automation must not modify system architecture directly unless the same change cannot be made via APIs or repository updates.**

---

## Before modifying code

**Always summarize the current system state before modifying code.**
