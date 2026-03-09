# Video pipeline flow — job → Wavespeed → FFmpeg → Telegram

End-to-end flow so the job goes to Wavespeed, clips + audio + music go to FFmpeg for rendering, and the final result is pushed to Telegram for viewing, approving, and posting.

---

## 1. Job → Wavespeed (WF-VIDEO)

| Step | What happens |
|------|----------------|
| **Queue Poller** | Runs 2×/day (12:00 & 20:00 UAE). Pops from `script_queue`. |
| **Decode Job** | Loads job (topic, script, 5 scenes, narration). |
| **Submit Scene 1–5** | Each scene sent to **Wavespeed** T2V API. |
| **Submit Voice Job** | Full narration sent to **Wavespeed** TTS API. |
| **Build Render Package** | Package with `scene_pred_ids`, `voice_pred_id`, optional `music_url`. Pushed to `render_queue`. |

Result: job is in Wavespeed; a render package (with prediction IDs) is in Redis `render_queue`.

---

## 2. Clips + audio + music → FFmpeg (WF-ASSEMBLE + Mission Control)

| Step | What happens |
|------|----------------|
| **Assembly Poller** | Runs 2×/day (12:30 & 20:30 UAE). Pops from `render_queue`. |
| **Poll All Scenes + Voice** | Polls Wavespeed until all 5 clips + 1 voice are **completed**. |
| **Check All Complete** | Collects `clip_urls` and `voice_url` from Wavespeed outputs. |
| **IF All Complete = true** | **Save pending_approve to Redis** (clip_urls, voice_url, music_url, chatId, job_id, etc.). |
| | **Notify Preview (Mission Control)** | POST `/internal/notify-preview` → Mission Control sends **Telegram** message with preview and buttons: **Approve & Publish** / Regenerate / Edit / Discard. |
| **User taps Approve & Publish** | Mission Control `POST /commands/approve-publish` → **\_call_railway_render(job)**. |
| **Railway Render service** | Receives `clips`, `voiceover`, optional `music`. Runs **FFmpeg** to combine clips + voice (+ music if provided). |
| | Renders final MP4 and **sends it to Telegram** (chatId + botToken). |

Result: clips, audio, and (optional) music go to FFmpeg; final video is pushed to Telegram.

---

## 3. Telegram: viewing, approving, posting

| Step | What happens |
|------|----------------|
| **Preview** | You get a Telegram message with topic, genre, and buttons (Approve & Publish / Regenerate / Edit / Discard). |
| **Approve & Publish** | Mission Control calls Railway Render → FFmpeg → **final video sent to Telegram**. Job is moved to `publish_queue` for any downstream posting. |
| **Regenerate** | Same topic sent back to WF-GEN for a new script/clips. |
| **Discard** | Job removed from pending; topic can be reused later. |

---

## Summary

1. **Job → Wavespeed:** WF-VIDEO sends 5 scenes + voice to Wavespeed; build render package (with optional `music_url`), push to `render_queue`.
2. **Clips + audio + music → FFmpeg:** WF-ASSEMBLE polls until ready, saves to `pending_approve`, notifies Telegram. On **Approve**, Mission Control calls Railway Render with clips, voiceover, and optional music; FFmpeg assembles and sends the final MP4 to Telegram.
3. **Final result in Telegram:** You view the video, approve (or regenerate/discard), and can post from there.

---

## Where music is set

- **WF-VIDEO** (Build Render Package): `music_url: job.music_url || job.music || null`. Set `music_url` or `music` on the job (e.g. from WF-GEN or a default track URL) to pass background music to FFmpeg.
- **Mission Control** (`_call_railway_render`): Sends `music` in the payload to Railway Render when present.
- **Railway Render service:** Should accept optional `music` URL and mix it with clips + voice in FFmpeg.
