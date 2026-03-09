# Project 2 — Start here (hands-free as possible)

1. **Open credentials doc**  
   → **[OPEN_THESE_URLS.md](OPEN_THESE_URLS.md)**  
   Open each URL in your browser. When a site asks you to log in, log in. Then copy the value from that page into your env file as shown in the table.

2. **Create your env file**  
   Copy `KEY=value.env.project2.example` to **KEY=value.env.project2** (same folder). Paste each value you copied from step 1 into the right line. Save.

3. **Tell me when that’s done**  
   Say e.g. “I’ve filled the env file” or “I’m on the Upstash page.” I’ll guide the next step (n8n workflows, Railway deploy, or running the bot).

4. **Full setup (after credentials)**  
   Follow **SETUP_STEPS.md**: same Upstash + same Railway; add N8N_WEBHOOK_WF_GEN_P2 in Railway; import project2/Automation workflows in n8n; optionally run `.\project2\run_setup_p2.ps1` once to init P2 Redis keys; then run `.\project2\run_bot.ps1` from repo root.

---

**I can’t open your browser from here.** You open the links in OPEN_THESE_URLS.md; you log in and copy. Once you’ve done that, I can walk you through n8n and Railway so you stay as hands-free as possible.
