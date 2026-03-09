# Immediate fix for 1,381 executions — applied

## What was done (automatically)

1. **Redis `system:paused` is set to `true`.**  
   WF-GEN, WF-VIDEO, and WF-ASSEMBLE all check this at the start. When it’s set, they **exit immediately** and do no work (no Groq, no Wavespeed, no queues). So:
   - The schedule can still **trigger** (every 2 min in n8n), but each run **stops at the first node** after the trigger.
   - Load on your system and APIs should drop right away.

2. **Pause script is in place.**  
   You can run again anytime:
   ```powershell
   python E:\KLIPORA\pause_automation.py
   ```

---

## What you should do once (in n8n) — stops the trigger completely

**Option A — In the browser (one time):**  
1. Open **https://n8n-production-2762.up.railway.app/** → **Workflows**.  
2. Open **Klipora WF-VIDEO** (double-click) → **Deactivate** or ⋮ → **Unpublish** → confirm.  
3. Open **Klipora WF-ASSEMBLE** → **Deactivate** or **Unpublish** → confirm.

**Option B — Via API (if you have N8N_API_KEY):**  
Set `N8N_URL` and `N8N_API_KEY` in your env (or `.env`), then run:
```powershell
python scripts/deactivate_n8n_scheduled_workflows.py
```
This GETs each workflow and PUTs it back with `active: false`.

After that, the schedule will no longer fire. When you want 2×/day again, re-import `Automation/WF-VIDEO.json` and `Automation/WF-ASSEMBLE.json` (correct cron), then Activate and Publish.

---

## Resume automation later

- **Unpause (allow runs when schedule is fixed):**  
  `python E:\KLIPORA\unpause_automation.py`
- **Fix schedule to 2×/day:**  
  See **STOP_CONTINUOUS_N8N_RUNS.md** (re-import workflows or set cron to `0 8,16 * * 0-6` and `30 8,16 * * 0-6`).
