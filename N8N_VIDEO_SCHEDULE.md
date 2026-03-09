# Video pipeline schedule — 2 runs per day (synchronized)

The video flow is scheduled to run **exactly 2 times per day**, with WF-VIDEO and WF-ASSEMBLE **synchronized**.

---

## Schedule (UTC / UAE)

| Workflow      | Cron (UTC)     | UAE time      | Role |
|---------------|-----------------|---------------|------|
| **WF-VIDEO**  | `0 8,16 * * 0-6`  | 12:00, 20:00  | Pops from `script_queue`, sends 5 scenes + voice to Wavespeed (max 2 videos/day). **Every day** (0-6 = Sun–Sat). |
| **WF-ASSEMBLE** | `30 8,16 * * 0-6` | 12:30, 20:30 | Runs **30 min after** VIDEO; polls Wavespeed, pushes to render_queue, notifies Telegram. **Every day**. |

- **WF-VIDEO** runs at **12:00** and **20:00 UAE** (08:00 and 16:00 UTC).
- **WF-ASSEMBLE** runs at **12:30** and **20:30 UAE** (08:30 and 16:30 UTC), so it picks up jobs that VIDEO started 30 minutes earlier (Wavespeed has time to finish).

Both workflows use n8n **Schedule Trigger** with a **cron expression** (no more “every 2 minutes” or “every 3 minutes”).

---

## "Only triggering on Sunday?" fix

If the Queue Poller runs only on **Sunday**, the trigger in n8n is likely **not** using the cron above. Common causes:

1. **"Weeks" or "Weekdays"** is selected instead of **Custom (Cron)**, and only Sunday is checked.
2. **Wrong cron** — e.g. the 5th field is `0` (Sunday only). Use `0-6` or `*` for every day.

**Fix:** Open **WF-VIDEO** → **Queue Poller** node → set trigger to **Custom (Cron)** and enter exactly: `0 8,16 * * 0-6` (0-6 = every day) → **Save**, then **Activate** and **Publish** the workflow.

---

## Applying the change in n8n

**→ Quick path: see [APPLY_SCHEDULE_NOW.md](APPLY_SCHEDULE_NOW.md) for a step-by-step checklist.**

The repo workflows use cron **`0 8,16 * * 0-6`** and **`30 8,16 * * 0-6`** (0-6 = every day of the week). To use them in n8n:

1. **Re-import** (recommended): Import `Automation/WF-VIDEO.json` and `Automation/WF-ASSEMBLE.json` (overwrite existing). **Save**, **Activate**, and **Publish** both (Schedule triggers need Publish).
2. **Edit manually**: WF-VIDEO → Queue Poller → **Custom (Cron)** → `0 8,16 * * 0-6`. WF-ASSEMBLE → Assembly Poller → **Custom (Cron)** → `30 8,16 * * 0-6`. Then **Save**, **Activate**, **Publish**.

---

## When “nothing happens”

- If **WF-GEN** is in **Error** (e.g. missing Groq key), no job is pushed to `script_queue`, so WF-VIDEO has nothing to pop at 12:00/20:00 UAE.
- Fix: set the **Groq API key** in **WF-GEN** → **Generate Script** node (see **N8N_GROQ_KEY.md**).

Manual runs from Telegram (**Generate Video**) still create a job and push to `script_queue`; the **next** scheduled WF-VIDEO run (12:00 or 20:00 UAE) will pick it up.

---

## WF-TREND (unchanged)

**WF-TREND** stays **once per day** at 08:00 UTC (`0 8 * * *`) for daily trend discovery. It is not part of the 2x/day video schedule.
