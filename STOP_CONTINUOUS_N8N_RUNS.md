# Stop continuous n8n runs — fix once and for all

If **WF-VIDEO** and **WF-ASSEMBLE** run every ~2 minutes instead of 2× per day, do the following.

---

## Why it happens

The **Schedule Trigger** in your n8n workflows is set to **“Every X minutes”** (e.g. every 2 minutes) instead of the intended **2× per day** cron. That can be from an old import or a manual change.

---

## 1. Stop runs immediately (Redis pause)

All three workflows (**WF-GEN**, **WF-VIDEO**, **WF-ASSEMBLE**) now check Redis `system:paused` at the start. If it’s set, they do nothing.

**Option A — Run the pause script (same config as `setup_redis.py`):**
```powershell
cd E:\KLIPORA
python pause_automation.py
```
This sets `system:paused` in Upstash so every scheduled trigger no-ops until you unpause.

**Option B — Mission Control dashboard:**  
If you have the dashboard deployed, use its **Pause** action (it sets `system:paused`).

**Option C — Upstash / Redis CLI:**  
Set key `system:paused` to `true` or `1` (e.g. in Upstash REST or Redis CLI).

---

## 2. Fix the schedule in n8n (2× per day only)

So that when you **unpause**, runs happen only at **12:00 and 20:00 UAE** (not every 2 minutes):

1. Open **n8n**: https://n8n-production-2762.up.railway.app
2. **Re-import** the workflows from this repo (overwrites the trigger):
   - **Workflows** → **Import from File**
   - Select **`Automation/WF-VIDEO.json`** → replace existing **WF-VIDEO**
   - Select **`Automation/WF-ASSEMBLE.json`** → replace existing **WF-ASSEMBLE**
3. **Save** each workflow (Ctrl+S).
4. **Activate** and **Publish** both (Schedule triggers run only when the workflow is **Published**).

**Or edit by hand:**  
- **WF-VIDEO** → first node **Queue Poller** → set to **Custom (Cron)** → `0 8,16 * * 0-6`  
- **WF-ASSEMBLE** → first node **Assembly Poller** → **Custom (Cron)** → `30 8,16 * * 0-6`

---

## 3. Resume when you want

- **Unpause:** run `python unpause_automation.py` (or clear `system:paused` in dashboard/Redis).
- Scheduled runs will then occur only at 12:00 and 20:00 UAE (if workflows are Active and Published).

---

## Summary

| Goal                    | Action |
|-------------------------|--------|
| Stop runs right now     | Run `python pause_automation.py` or set `system:paused` in Redis. |
| Fix “every 2 min”       | Re-import `WF-VIDEO.json` and `WF-ASSEMBLE.json` in n8n (or set cron as above). |
| No automatic runs at all| After fixing schedule: **Deactivate** WF-VIDEO and WF-ASSEMBLE in n8n. |
| Resume 2×/day           | Run `python unpause_automation.py` and keep workflows Active + Published. |

The repo workflows already include **Check Paused** and **IF Not Paused** at the start of WF-VIDEO and WF-ASSEMBLE (like WF-GEN). Re-import to get that behavior.
