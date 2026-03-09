# Why Wavespeed generation “doesn’t happen” and how to fix it

## Cause

From your n8n execution log, **Klipora WF-GEN — Content Generation V2** is in **Error**. When WF-GEN fails:

1. No script is produced.
2. No job is pushed to Redis `script_queue`.
3. **WF-VIDEO** runs every 2 min but finds `script_queue` empty, so it never calls Wavespeed.
4. No clips → nothing for **WF-ASSEMBLE** to assemble → no render → no video in Telegram.

So **Wavespeed “not happening”** is a consequence of **WF-GEN failing**, not of Wavespeed or FFmpeg being broken.

## Fix

1. **Set the Groq API key in n8n (WF-GEN)**  
   - Open **WF-GEN** → **Generate Script** node.  
   - Set **Authorization** to `Bearer gsk_your_key` (from [console.groq.com](https://console.groq.com)).  
   - Save the workflow.  
   - See **N8N_GROQ_KEY.md**.

2. **Trigger a video again from Telegram**  
   - Video Factory → Generate Video → choose options → Generate.  
   - You should get “Pipeline started” and then (when WF-GEN succeeds) a “Script Ready” message.  
   - In the 12:00–20:00 UAE window (max 2/day), WF-VIDEO will then pick the job, call Wavespeed, and WF-ASSEMBLE will eventually send you a review message (Approve / Discard). Approve triggers FFmpeg render and the final video to Telegram.

## FFmpeg / render

- **Railway Render** is called from:
  - **WF-ASSEMBLE** (“Call Railway Render” node) when a job is fully ready, and/or  
  - **Mission Control** when you tap **Approve & Publish** in Telegram.
- URL: `RAILWAY_RENDER_URL` (default `https://klipora-render-service-production.up.railway.app`) in Railway / n8n env.
- If render never runs, the usual reason is that no job ever reaches the “all clips ready” state (again, because WF-GEN failed earlier). Fix WF-GEN first, then re-test the full pipeline.
