# Apply daily 2x video schedule — do this now

Videos should run **every day** at **12:00 and 20:00 UAE**. If your Queue Poller only runs on Sunday, the schedule in **n8n** is wrong. Fix it with one of these two options.

---

## Option A: Re-import (fastest, recommended)

1. Open your **n8n** instance (e.g. Railway or cloud URL).
2. Go to **Workflows**.
3. **Import from file** (or menu → Import).
4. Select **both** files from this repo:
   - `Automation/WF-VIDEO.json`
   - `Automation/WF-ASSEMBLE.json`
5. When asked, **overwrite** the existing workflows with the same names.
6. Open **WF-VIDEO** → **Save** (Ctrl+S).
7. Open **WF-ASSEMBLE** → **Save** (Ctrl+S).
8. **Activate** both workflows (toggle to Active).
9. **Publish** both workflows (Schedule triggers only run when the workflow is published).

Done. The trigger is set to run **every day** (cron `0 8,16 * * 0-6` = 12:00 and 20:00 UAE, Sun–Sat).

---

## Option B: Fix manually (if you can’t re-import)

1. Open **WF-VIDEO** in n8n.
2. Click the **Queue Poller** node (first node, Schedule Trigger).
3. Set **Trigger Interval** to **Custom (Cron)** — not "Minutes", **not "Weeks"** (that can default to Sunday only).
4. In **Cron Expression** enter exactly:  
   `0 8,16 * * 0-6`
5. **Save** the workflow.
6. Repeat for **WF-ASSEMBLE**: open **Assembly Poller** → **Custom (Cron)** → `30 8,16 * * 0-6` → **Save**.
7. **Activate** and **Publish** both workflows.

---

## Check

- **WF-VIDEO** runs at **12:00** and **20:00 UAE** (08:00 and 16:00 UTC), **every day**.
- **WF-ASSEMBLE** runs at **12:30** and **20:30 UAE**, **every day**.

If the trigger was "Weeks" with only Sunday selected, that’s why you only got runs on Sunday. The cron above fixes it.
