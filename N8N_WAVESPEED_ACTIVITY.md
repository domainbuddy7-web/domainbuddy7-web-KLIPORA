# Why Wavespeed Might Show No Activity

Wavespeed requests are made **only by the n8n workflow WF-VIDEO** (and WF-ASSEMBLE when polling). If you don’t see activity in your Wavespeed dashboard, check the following.

---

## TL;DR — “Video and prompt not reaching Wavespeed”

- **Yes, we have the Wavespeed API:** WF-VIDEO uses `api.wavespeed.ai` (wan-2.2/t2v + qwen3-tts) with a Bearer token. Your History shows completed runs when requests do go through.
- **Most likely reason:** WF-VIDEO runs **only at 12:00 and 20:00 UAE** (and only if in window + daily count &lt; 2). So after “Script Ready” the job sits in `script_queue` until the **next** scheduled run. If you triggered at 22:33, nothing is sent to Wavespeed until the next noon or 8 PM UAE.
- **Simple fix for testing:** Temporarily set the **Queue Poller** in WF-VIDEO to run **every 5 minutes** (e.g. cron `*/5 * * * *` or “Every 5 minutes”). Save and Activate. Trigger “Generate Video” from Telegram again; within 5 minutes WF-VIDEO will pop the job and send 5 scenes + voice to Wavespeed. Check History again. Then set the trigger back to `0 8,16 * * 0-6` for production.

## 1. Where the calls come from

- **WF-VIDEO** (at 12:00 and 20:00 UAE when conditions pass):
  - Submits **5 video** requests (wan-2.2/t2v-480p-ultra-fast)
  - Submits **1 TTS** request (qwen3-tts/text-to-speech)
- **WF-ASSEMBLE** (after WF-VIDEO):
  - **GET** requests to `.../predictions/{id}` to poll status (these may or may not show as “requests” in Wavespeed depending on how the dashboard counts them).

So “no activity” usually means either WF-VIDEO isn’t running, or it’s not sending requests (conditions not met or no job in queue).

---

## 2. WF-VIDEO only runs when all of these are true

1. **Workflow is active**  
   In n8n, **WF-VIDEO** must be **Active** (toggle on). If it’s off, nothing runs.

2. **Time window (UTC+4)**  
   The workflow only processes the queue when **local hour is between 12:00 and 20:00** (12–8 PM in that timezone). Outside that window it does nothing.

3. **Daily limit**  
   It only runs if **fewer than 2 videos** have been generated **today** (date key in Redis). After 2, it skips until the next day.

4. **Queue has a job**  
   WF-GEN must have finished and **pushed a job ID** to Redis list `script_queue`. If WF-GEN never completes (e.g. missing Groq API key) or the queue is empty, WF-VIDEO has nothing to pop and never calls Wavespeed.

5. **Job data in Redis**  
   The job must be stored in Redis under `job:<jobId>`. WF-VIDEO RPOPs the ID, then GETs that key; if the key is missing or invalid, it won’t reach the “Submit Scene 1” etc. nodes.

So: **no activity** can simply mean you’re outside the time window, over the daily limit, or the queue is empty / job missing.

---

## 3. API key vs dashboard account

Wavespeed shows requests **per API key / account**. In the repo:

- **WF-VIDEO** and **WF-ASSEMBLE** use a **hardcoded** Wavespeed Bearer key in the workflow JSON.
- **Infrastructure/config.json** has a `wavespeed_api` value (used elsewhere, e.g. Mission Control).

If the key in **WF-VIDEO** is different from the key for the Wavespeed account you’re logged into, you’ll see “no activity” in **your** dashboard even though the workflow is calling Wavespeed with the other key.

**What to do:** In Wavespeed, confirm which API key your account uses. In n8n, open WF-VIDEO (and WF-ASSEMBLE) and check the **Authorization** header on the nodes that call `api.wavespeed.ai`. Make sure that Bearer token is the same as your Wavespeed account’s key so that usage appears under “your” account.

---

## 4. Quick checks

| Check | Where |
|--------|--------|
| WF-VIDEO is **Active** | n8n → WF-VIDEO → toggle |
| Current time is 12:00–20:00 UTC+4 | Your clock / timezone |
| Daily count &lt; 2 | Redis key `system:daily_count:YYYY-MM-DD` (optional) |
| Jobs in queue | Redis list `script_queue` (optional) |
| WF-GEN completes and pushes to queue | n8n runs of WF-GEN, Groq key set |
| Same API key in workflow as in dashboard | n8n WF-VIDEO/WF-ASSEMBLE vs Wavespeed account |

---

## 5. Optional: relax time window or limit (for testing)

To see Wavespeed activity more easily you can temporarily:

- In **WF-VIDEO**, in the **Check Time Window** node, change the condition so `inTimeWindow` is always `true` (e.g. `localHour >= 0 && localHour < 24`), **or**
- In **Evaluate Limits**, allow more than 2 runs per day (e.g. `count < 99`).

Revert after testing so production behavior stays as intended.
