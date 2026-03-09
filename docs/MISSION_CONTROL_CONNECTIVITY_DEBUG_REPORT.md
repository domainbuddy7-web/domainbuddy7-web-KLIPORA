# Mission Control "Could not reach" — Debug Report

**Date:** 2026-03-09  
**Issue:** System repeatedly shows "Could not reach Mission Control API. Check MISSION_CONTROL_URL in KEY=value.env and that the API is running." while external tests confirm Mission Control is reachable (GET /health → 200).

---

## STEP 1 — Error source

| Item | Value |
|------|--------|
| **Exact string** | The UI shows combinations of: "Mission Control API offline", "Check MISSION_CONTROL_URL in KEY=value.env", "Check Railway deployment or MISSION_CONTROL_URL", "Check MISSION_CONTROL_URL and that the API is running." |
| **Primary file** | `Command_Center/telegram_command_center.py` |
| **Supporting file** | `Command_Center/telegram_services/diagnostics.py` |

**Code paths that produce the failure:**

1. **diagnostics.py** — `check_mission_control_connectivity(api_get, base_url)`  
   - If `base_url` is empty → returns `reachable: False`, message: *"MISSION_CONTROL_URL is not set. Add it in KEY=value.env and restart the bot."*  
   - If `api_get("/health")` returns a dict with `_error` (or falsy) → returns `reachable: False`, message: *"Mission Control API offline. /health → {err}. Check Railway deployment or MISSION_CONTROL_URL."*

2. **telegram_command_center.py** — `_api_get(path)`  
   - Used for all Mission Control calls. Returns `{}` if `not MISSION_CONTROL_URL`.  
   - On `requests.get(..., timeout=15)`: Timeout → `{"_error": "timeout"}`; ConnectionError → `{"_error": "connection failed"}`; non-OK response → `{"_error": "HTTP {code}"}`.

3. **telegram_command_center.py** — Call sites that show the error:  
   - `_build_status_panel()` (status panel): uses `check_mission_control_connectivity` and formats with `_format_mission_control_for_ui()` → "⚠️ Cannot reach Mission Control" + url_hint.  
   - `_build_videos_panel()`: "❌ Mission Control API offline" + diag.  
   - `_build_finance_panel()`: "Mission Control unreachable or no budget data." + "Check MISSION_CONTROL_URL and that the API is running."  
   - Pipeline start callback (`elif not result`): "❌ Mission Control API offline" + "Check Railway deployment or MISSION_CONTROL_URL." + diag.

So the message the user sees is built from **diagnostics** (reachable + message) and **telegram_command_center** (HTML lines). The **failure condition** is either (a) `MISSION_CONTROL_URL` empty at runtime, or (b) `_api_get("/health")` returning something with `_error` (timeout, connection failed, HTTP error).

---

## STEP 2 — API call and failure condition

| Where URL is read | `telegram_command_center.py` lines 99–105: `_raw_url = os.environ.get("MISSION_CONTROL_URL") or os.environ.get("mission_control_url") or ""` then `MISSION_CONTROL_URL = _raw_url or "https://domainbuddy7-web-klipora-production.up.railway.app"` |
| How request is made | `_api_get("/health")` → `requests.get(f"{MISSION_CONTROL_URL}{path}", timeout=15)` |
| Failure triggers | (1) `not MISSION_CONTROL_URL` → return `{}`; (2) `requests.exceptions.Timeout` → `{"_error": "timeout"}`; (3) `requests.exceptions.ConnectionError` → `{"_error": "connection failed"}`; (4) non-OK status → `{"_error": "HTTP {code}"}`. |

So the system believes the API is unreachable when either the URL is missing (so no request is sent) or the request fails (timeout/connection/HTTP error).

---

## STEP 3 — Environment variable loading (root cause)

| Mechanism | `_load_env_file()` in `telegram_command_center.py` (runs at import). |
| Files | It iterates `("KEY=value.env", ".env")` and for **each** file that exists, parses KEY=value lines and sets `os.environ[key] = value`. |

**Bug (fixed):** The loop had a **`break`** after the first file that existed. So only **one** of the two files was ever loaded. If `KEY=value.env` existed but did not contain a valid `MISSION_CONTROL_URL` line (e.g. template, or key only in a code block that wasn’t parsed as expected), and the real value was in `.env`, the variable was never set. The fallback default URL was still applied, so the only way to get “unreachable” without a wrong URL would be a failed request (timeout/connection). Loading only one file also increased the chance of missing the variable when only one of the two files had it.

---

## STEP 4 — Runtime value

- **Before fix:** Depending on which file was loaded and whether it contained `MISSION_CONTROL_URL`, the value could be missing (then default used) or wrong.
- **After fix:** Both `KEY=value.env` and `.env` are loaded; `.env` is loaded second and overrides. So if either file sets `MISSION_CONTROL_URL`, it will be present. A **startup log** was added: the bot prints `MISSION_CONTROL_URL loaded: <first 50 chars>...` (or a warning if empty) so you can confirm the resolved value at runtime.

---

## STEP 5 — HTTP request

- **Library:** `requests` (GET).
- **URL:** `{MISSION_CONTROL_URL}/health` (no double slash; URL is stripped of trailing slash).
- **Timeout:** 15 seconds.
- **TLS:** Default `requests` behavior (verification on). No special handling for scheme; correct `https://` is used when URL is set correctly.

If the bot runs in an environment that cannot reach the API (e.g. different network, firewall, proxy), you will see `_error`: "timeout" or "connection failed" in the diagnostics message.

---

## STEP 6 — Fix applied

1. **Load both env files**  
   In `Command_Center/telegram_command_center.py`, **removed the `break`** in `_load_env_file()` so that **both** `KEY=value.env` and `.env` are processed (in that order). Variables from `.env` override those from `KEY=value.env`, so either file can define `MISSION_CONTROL_URL` and it will be used.

2. **Startup log**  
   After resolving `MISSION_CONTROL_URL`, the bot now prints either  
   `MISSION_CONTROL_URL loaded: <masked URL>` or  
   `WARNING: MISSION_CONTROL_URL is empty. Add it to KEY=value.env or .env and restart.`  
   so you can confirm the runtime value.

3. **PowerShell launcher**  
   In `run_telegram_bot.ps1`, the script now loads **both** `KEY=value.env` and `.env` (in that order), so when the bot is started via the script, env vars from both files are set and `.env` overrides.

---

## STEP 7 — Confirmation

After the fix:

1. **Restart the Telegram bot** (e.g. `.\run_telegram_bot.ps1` or `python -m Command_Center.telegram_command_center`).
2. Check the console for `MISSION_CONTROL_URL loaded: https://domainbuddy7-web-klipora-production.up.railway.app` (or your URL).
3. In Telegram, open the status/panels that call Mission Control; you should no longer see "Could not reach Mission Control API" / "Mission Control API offline" when the API is actually reachable.
4. If you still see an error, the diagnostics message will include the reason (e.g. "timeout", "connection failed", "HTTP 503"). In that case, the problem is network/environment from the machine running the bot, not env loading.

---

## Summary

| Item | Result |
|------|--------|
| **File where error is produced** | `Command_Center/telegram_command_center.py` (panels and pipeline callback); **diagnostics** in `Command_Center/telegram_services/diagnostics.py`. |
| **Function that drives the message** | `check_mission_control_connectivity()` (diagnostics) + `_format_mission_control_for_ui()` and panel builders (telegram_command_center). |
| **Runtime value of MISSION_CONTROL_URL** | Now logged at startup (masked). Resolved from env; default `https://domainbuddy7-web-klipora-production.up.railway.app` if unset. |
| **Root cause** | Only one of `KEY=value.env` or `.env` was loaded (break after first file). If the loaded file didn’t set `MISSION_CONTROL_URL`, or the bot was run without the PowerShell script that sets env, the variable could be missing or wrong, or requests could fail (timeout/connection), leading to "Mission Control API offline" / "Could not reach" messaging. |
| **Fix** | Load both `KEY=value.env` and `.env` in Python and in the PowerShell launcher; add startup log of `MISSION_CONTROL_URL`. |
