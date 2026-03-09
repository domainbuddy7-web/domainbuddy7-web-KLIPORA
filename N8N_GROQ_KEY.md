# Fix "Invalid API Key" in WF-GEN (Content Generation)

Videos don't generate because **WF-GEN** fails at the **Generate Script** node with:

- `401 - Invalid API Key`
- `Authorization failed - please check your credentials`

That node calls **Groq** (LLM for script writing). The workflow was exported with a placeholder key; you must set your **real Groq API key** in n8n.

---

## Steps in n8n

1. Open **n8n** → **Workflows** → **Klipora WF-GEN — Content Generation V2**.
2. Open the node named **"Generate Script"** (HTTP Request to `api.groq.com`).
3. In **Headers** (or **Authentication**), find **Authorization**.
4. Replace the value with your real key:
   - **Format:** `Bearer gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
   - Get the key: [console.groq.com](https://console.groq.com) → API Keys → Create or copy.
5. **Save** the workflow.

After saving, trigger a video again from the Telegram bot. WF-GEN should pass and script → video → assembly will run.

---

## Summary

| Issue | Fix |
|-------|-----|
| WF-GEN "Generate Script" 401 | In n8n, open that node and set **Authorization** to `Bearer YOUR_GROQ_API_KEY` (from Groq console). |
| Mission Control "Could not reach" in Telegram | Set **MISSION_CONTROL_URL** in KEY=value.env to your Railway API URL. |
