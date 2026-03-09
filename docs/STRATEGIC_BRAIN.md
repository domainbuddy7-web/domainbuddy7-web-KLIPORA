# Strategic Brain

This layer represents **external reasoning intelligence** used to guide the system (e.g. ChatGPT or similar tools used by the system owner).

---

## Responsibilities

- **System architecture decisions** — Design and evolution of the KLIPORA stack, agents, and automation  
- **Growth experiments** — What to test, which topics/formats to prioritize  
- **Pipeline optimization** — How to improve throughput, quality, and reliability  
- **Business opportunity discovery** — New channels, formats, or revenue opportunities  
- **Long-term planning** — Phases (2 → 20 → 100 → 1000 videos/day), milestones, and strategy  

**Operational agents execute tasks. Strategic Brain decides direction.**

---

## How Strategic Brain Interacts with the System

Strategic Brain interacts with KLIPORA through:

- **Mission Control API** — Run-cycle, health, queues, pause/unpause, internal endpoints  
- **Telegram Command Center** — Status, queues, topic/genre, generate video, approve/publish, experiments, opportunities, settings  
- **company_config.json** — Configuration and policy that agents and automation respect  

---

## Relationship to Other Layers

| Layer              | Role                          |
|--------------------|-------------------------------|
| **Strategic Brain**| Decides direction and strategy|
| **Company Core**   | CEO, CTO, Growth, Ops, Finance agents execute within that direction |
| **Automation Engine** | n8n workflows run the production pipeline |
| **Control Interface** | Mission Control + Telegram expose control and visibility to the owner (and thus to Strategic Brain) |

---

## Full system memory

For complete architecture, Redis schema, automation flow, agents, and key files, see **`docs/KLIPORA_SYSTEM_BRAIN.md`**. Cursor must read that file before modifying the architecture.
