# n8n Workflow Execution Triggers — Audit Report

**Date:** 2025-03-09  
**Scope:** WF-TREND, WF-GEN, WF-VIDEO, WF-ASSEMBLE (Automation/*.json)  
**No workflows were modified.**

---

## 1. WF-TREND (Daily Trend Discovery)

| Item | Result |
|------|--------|
| **Trigger type** | **Schedule (cron)** |
| **Execution schedule** | `0 8 * * *` — once daily at **08:00 UTC** |
| **Continuous execution risk** | **No.** Single daily run; no high-frequency interval. |
| **Redis queue check before expensive work** | **N/A.** Workflow is not queue-driven. It runs Reddit fetch → Groq analysis → Redis write → Telegram on each trigger. No `script_queue` / `render_queue` involved. |

**Notes:** First node is "Daily Trigger" (scheduleTrigger). No gate on Redis queues; expensive steps (HTTP to Reddit, Groq) run every time the cron fires (once per day). This is by design for trend discovery.

---

## 2. WF-GEN (Content Generation)

| Item | Result |
|------|--------|
| **Trigger type** | **Webhook only** |
| **Execution schedule** | N/A (no schedule) |
| **Continuous execution risk** | **No.** Runs only when Mission Control (or caller) POSTs to `/webhook/wf-gen`. |
| **Redis queue check before expensive work** | **Yes (topic gate).** Before Groq "Generate Script", workflow: Check Paused → Parse Params → Get Used Topics (Redis SMEMBERS) → Topic Uniqueness Gate → Mark Topic Used → Generate Script. Expensive work (Groq) runs only after topic validation. No `script_queue` read (this workflow *pushes* to `script_queue`). |

**Verification:** **WF-GEN is webhook-only.** Single trigger node: "Gen Webhook" (webhook, path `wf-gen`, POST). No schedule or cron node.

---

## 3. WF-VIDEO (5-Scene Video & Voice)

| Item | Result |
|------|--------|
| **Trigger type** | **Schedule (cron)** |
| **Execution schedule** | `0 8,16 * * 0-6` — **08:00 and 16:00 UTC**, every day (0–6 = all days of week). |
| **Continuous execution risk** | **No.** Two fixed times per day; no sub-minute or high-frequency trigger. |
| **Redis queue check before expensive work** | **Yes.** Flow: Check Paused → Check Time Window → GET Daily Count → Evaluate Limits → **IF OK to Generate** → **RPOP script_queue** → **IF Queue Not Empty** → Load Job → Wavespeed (expensive). Expensive path (Load Job, Wavespeed API, etc.) runs only when RPOP returns a job ID (`result` isNotEmpty). |

**Verification:** **WF-VIDEO only processes when script_queue has items.** It does not "peek" then process; it RPOPs once per run. If queue is empty, RPOP result is empty, "IF Queue Not Empty" fails, and Load Job / Wavespeed are not executed. One job per execution when queue is non-empty and limits (paused, time window, daily count) allow.

---

## 4. WF-ASSEMBLE (Assembly & Notify)

| Item | Result |
|------|--------|
| **Trigger type** | **Schedule (cron)** |
| **Execution schedule** | `30 8,16 * * 0-6` — **08:30 and 16:30 UTC**, every day. |
| **Continuous execution risk** | **No.** Two fixed times per day. |
| **Redis queue check before expensive work** | **Yes.** Flow: Check Paused → **RPOP render_queue** → **IF Render Queue Not Empty** → Decode Render Package → Poll Wavespeed (expensive). Expensive path (decode, poll scenes/voice, Mission Control notify) runs only when RPOP returns a package. |

**Verification:** **WF-ASSEMBLE only processes when render_queue has items.** Empty queue → RPOP returns empty → "IF Render Queue Not Empty" fails → no decode/poll/notify. One package per execution when queue is non-empty and not paused.

---

## Summary Table

| Workflow    | Trigger   | Schedule (if cron)     | Continuous risk | Queue gate before expensive work |
|------------|-----------|-------------------------|-----------------|-----------------------------------|
| WF-TREND   | Cron      | 08:00 UTC daily        | No              | N/A (not queue-driven)            |
| WF-GEN     | Webhook   | —                      | No              | Topic/used_topics gate only       |
| WF-VIDEO   | Cron      | 08:00, 16:00 UTC daily | No              | Yes (RPOP script_queue → IF)     |
| WF-ASSEMBLE| Cron      | 08:30, 16:30 UTC daily | No              | Yes (RPOP render_queue → IF)      |

---

## Specific Verifications (as requested)

- **WF-GEN is webhook-only.** Confirmed: only trigger is "Gen Webhook" (POST webhook). No schedule/cron.
- **WF-VIDEO only processes when script_queue has items.** Confirmed: RPOP script_queue then "IF Queue Not Empty"; expensive nodes (Load Job, Wavespeed, etc.) only on the true branch.
- **WF-ASSEMBLE only processes when render_queue has items.** Confirmed: RPOP render_queue then "IF Render Queue Not Empty"; expensive nodes (Decode, Poll Wavespeed, notify) only on the true branch.

No changes were made to any workflow JSON.
