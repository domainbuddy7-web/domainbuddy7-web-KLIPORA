# Connect n8n to the video review flow

So that when a video is ready, you get a Telegram message with **Approve & Publish / Regenerate / Edit Metadata / Discard** buttons.

---

## In n8n: WF-ASSEMBLE

1. Open your **WF-ASSEMBLE** workflow (the one that finishes rendering and saves the preview).

2. After the node that **saves to Redis** as `pending_approve:{job_id}` (with `job_id`, `topic`, `video_url`, etc.), add an **HTTP Request** node.

3. Configure the HTTP Request node:

   - **Method:** POST  
   - **URL:** `https://domainbuddy7-web-klipora-production.up.railway.app/internal/notify-preview`  
   - **Body Content Type:** JSON  
   - **Specify Body:** Yes  
   - **Body:**
     ```json
     {
       "job_id": "{{ $json.job_id }}"
     }
     ```
     (If your previous node uses a different field for the job ID, replace `$json.job_id` with that, e.g. `$json.id`.)

4. Save the workflow. When this node runs, the Mission Control API will send the review message to Telegram (to the chat set in Railway’s `TELEGRAM_CHAT_ID`). The Telegram bot (running on your PC with `run_telegram_bot.ps1`) will handle the button presses.

---

## Summary

| Step | What to do |
|------|------------|
| 1 | In WF-ASSEMBLE, add an HTTP Request node after “save preview to Redis”. |
| 2 | Set Method = POST, URL = `.../internal/notify-preview`, Body = `{"job_id": "{{ $json.job_id }}"}`. |
| 3 | Save and test by running a full pipeline until the video is ready for review. |

You only need to do this once in n8n; after that, every finished video will trigger the review message.
