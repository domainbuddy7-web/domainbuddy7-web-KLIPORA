# Video generation setup — get clips in one flow

This is the **first** setup to get KLIPORA producing videos end-to-end.

---

## 1. Pipeline flow (order matters)

```
Telegram [Generate] → Mission Control API → WF-GEN (n8n) → script_queue (Redis)
       → WF-VIDEO (n8n) → Wavespeed (5 clips + 1 voice)
       → WF-ASSEMBLE (n8n) → pending_approve → Telegram [Approve/Reject]
       → Railway Render (FFmpeg) → final MP4 to Telegram
```

- **WF-GEN**: Picks topic, calls Groq for script, pushes job to `script_queue`, notifies "Script Ready".
- **WF-VIDEO**: Runs **2 times/day** at **12:00 and 20:00 UAE** (cron `0 8,16 * * *` UTC). Pops from `script_queue`, sends 5 scenes + 1 TTS to Wavespeed (max 2 videos/day).
- **WF-ASSEMBLE**: Runs **2 times/day** at **12:30 and 20:30 UAE** (cron `30 8,16 * * *` UTC), 30 min after VIDEO. Polls Wavespeed, then saves to Redis and sends Telegram review (Approve & Publish / Regenerate / Edit / Discard).

---

## 2. Checklist (do in order)

| # | What | Where |
|---|------|--------|
| 1 | **Mission Control API** live | Railway: `https://domainbuddy7-web-klipora-production.up.railway.app` → open `/health` → `config_ok: true` |
| 2 | **Redis** keys | Run `python setup_redis.py` once (or use Railway env). Ensures `system:videos_per_day=2`, queues, finance keys. |
| 3 | **n8n WF-GEN** Groq key | n8n → WF-GEN → "Generate Script" node → Authorization: Bearer `gsk_...` (see N8N_GROQ_KEY.md) |
| 4 | **n8n WF-VIDEO** active | n8n → WF-VIDEO → toggle **Active**. Schedule: 2 runs/day at 12:00 & 20:00 UAE (cron `0 8,16 * * *`). |
| 5 | **n8n WF-ASSEMBLE** active | n8n → WF-ASSEMBLE → **Active**. Schedule: 2 runs/day at 12:30 & 20:30 UAE (cron `30 8,16 * * *`). Must have "Notify Preview" → POST Mission Control `/internal/notify-preview`. |
| 6 | **Telegram bot** | `KEY=value.env`: `TELEGRAM_BOT_TOKEN`, `MISSION_CONTROL_URL`, `OWNER_TELEGRAM_ID`. Run `.\run_telegram_bot.ps1`. |
| 7 | **One test** | Telegram → Video Factory → Generate Video → pick genre/style/duration → Confirm. Wait for "Script Ready", then (in time window) video pipeline runs; review message appears when ready. |

---

## 3. Keys and URLs (no secrets in this file)

- **Mission Control**: `MISSION_CONTROL_URL` in bot env = Railway API URL.
- **Groq**: Set inside n8n WF-GEN "Generate Script" node (Bearer token).
- **Wavespeed**: Keys are in WF-VIDEO / WF-ASSEMBLE JSON; activity shows in Wavespeed dashboard when jobs run.
- **Redis**: From Upstash; set `UPSTASH_REDIS_REST_URL` and `UPSTASH_REDIS_REST_TOKEN` on Railway for Mission Control.

---

## 4. If no video appears

- **"Script Ready" but no clips**: WF-VIDEO runs only 12:00–20:00 UAE and max 2/day. See N8N_WAVESPEED_ACTIVITY.md.
- **No "Script Ready"**: WF-GEN likely failing on Groq (401) → set Groq API key in n8n (N8N_GROQ_KEY.md).
- **No review message**: WF-ASSEMBLE must call Mission Control `POST /internal/notify-preview` with `job_id`; Mission Control needs `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` to send the message.

---

## 5. Video spec (policy)

- 5 scenes per video  
- 9:16 vertical (1080×1920)  
- 20–50 s duration  
- Captions and narration  
- Preview to Telegram before publish; publish only after Approve.

Once this flow works, use the same bot for Status, Finance, Experiments, and Automation.
