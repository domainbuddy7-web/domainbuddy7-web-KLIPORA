# Mission Control "Could not reach" — Source and Fix Report

**Date:** 2026-03-09  
**Issue:** System shows "❌ Could not reach Mission Control API. Check MISSION_CONTROL_URL in KEY=value.env and that the API is running." while GET /health returns HTTP 200 and `{"status":"ok","config_ok":true}`.

---

## STEP 1 — Source of the error

The **exact phrase** "Could not reach Mission Control API" does not appear as a single string in code. The user sees a **combination** of lines that the UI builds from:

| Source | Text |
|--------|------|
| **diagnostics** | "Mission Control API offline. /health → {err}. Check Railway deployment or MISSION_CONTROL_URL." |
| **telegram_command_center** | "❌ Mission Control API offline", "Check MISSION_CONTROL_URL in KEY=value.env and that the API is running.", "⚠️ Cannot reach Mission Control" |

**File:** `Command_Center/telegram_command_center.py`  
**Supporting file:** `Command_Center/telegram_services/diagnostics.py`

**Code blocks:**

1. **diagnostics.py** — `check_mission_control_connectivity()` (lines 18–62):

```python
def check_mission_control_connectivity(api_get, base_url):
    url = (base_url or "").strip()
    if not url:
        return {"reachable": False, "message": "MISSION_CONTROL_URL is not set. Add it in KEY=value.env and restart the bot.", ...}
    health = api_get("/health")
    if not health or health.get("_error"):
        err = health.get("_error", "request failed") if health else "no response"
        return {"reachable": False, "message": f"Mission Control API offline. /health → {err}. Check Railway deployment or MISSION_CONTROL_URL.", ...}
```

2. **telegram_command_center.py** — `_format_mission_control_for_ui()` (lines 238–254) and panel builders that call `check_mission_control_connectivity()` and then format the result (e.g. status panel ~348–354, videos panel ~389–394, finance panel ~474, pipeline callback ~1139–1144).

---

## STEP 2 — API check logic

| Item | Detail |
|------|--------|
| **HTTP request** | GET `{MISSION_CONTROL_URL}/health` |
| **Library** | `requests` (`requests.get(...)`) |
| **Function** | `_api_get(path)` in `telegram_command_center.py` (lines 195–209) |
| **URL** | `f"{MISSION_CONTROL_URL}{path}"` with `path="/health"`; URL is stripped of trailing slash, so no double slash. |
| **Condition that triggers "unreachable"** | `check_mission_control_connectivity` treats the API as unreachable when either: (1) `base_url` is empty, or (2) `health = api_get("/health")` is falsy or has `health.get("_error")`. |

**_api_get** returns:

- `{}` if `not MISSION_CONTROL_URL`
- `{"_error": "timeout", "_code": 0}` on `requests.exceptions.Timeout`
- `{"_error": "connection failed", "_code": 0}` on `requests.exceptions.ConnectionError`
- `{"_error": "HTTP {code}", "_code": code}` when `not r.ok`
- On 200 OK: previously only returned `r.json()` when `Content-Type` started with `application/json`, otherwise `{}`. So a 200 response with JSON body but wrong/missing Content-Type was treated as "no response" and triggered the error.

---

## STEP 3 — Environment variable loading

| Where read | `telegram_command_center.py` lines 100–107: `os.environ.get("MISSION_CONTROL_URL")` (and `mission_control_url`), then default if empty. |
| Loader | `_load_env_file()` in the same file (runs at import, before config). |
| Files loaded | **Both** `KEY=value.env` and `.env` are iterated; for each file that exists, KEY=value lines are parsed and set in `os.environ`. Order: `KEY=value.env` then `.env`, so `.env` overrides. No `dotenv`; no `process.env` (this is Python). |

Previously, a `break` after the first existing file meant only one of the two files was ever loaded. If the loaded file didn’t set `MISSION_CONTROL_URL`, the variable could be missing at runtime and the default would be used only when the code path allowed it; in other cases the process could see `MISSION_CONTROL_URL` as empty and report unreachable.

---

## STEP 4 — Runtime value of MISSION_CONTROL_URL

At startup the bot now logs:

- `MISSION_CONTROL_URL loaded: https://domainbuddy7-web-klipora-production.up.railway.app` (or first 50 chars + `...`), or  
- `WARNING: MISSION_CONTROL_URL is empty. Add it to KEY=value.env or .env and restart.`

So the runtime value can be confirmed in the console. It is expected to be `https://domainbuddy7-web-klipora-production.up.railway.app` (no trailing slash), not `None`, empty string, localhost, or another domain.

---

## STEP 5 — Actual request

- **Request:** `GET {MISSION_CONTROL_URL}/health` with `requests.get(..., timeout=15)`.
- **TLS:** Default `requests` behavior (verification on). Scheme is `https://` when URL is set correctly.
- **Edge case fixed:** If the server returned 200 with a JSON body but Content-Type was not `application/json`, the code returned `{}`, so `check_mission_control_connectivity` treated it as "no response" and showed the error. The code was updated to try parsing JSON on 200 even when Content-Type is not `application/json`, so a successful JSON response is no longer misclassified.

---

## STEP 6 — Fix applied (environment loading)

**Change:** In `Command_Center/telegram_command_center.py`, `_load_env_file()` was updated so that **both** env files are loaded:

- Loop over `("KEY=value.env", ".env")` with **no `break`** after the first file.
- Both files that exist are read; `.env` is loaded second and overrides.
- `run_telegram_bot.ps1` was also updated to load both files before starting the bot.

So `MISSION_CONTROL_URL` is read from whichever of `KEY=value.env` or `.env` defines it.

---

## STEP 7 — Verification

After the fix:

1. Restart the bot (`.\run_telegram_bot.ps1` or `python -m Command_Center.telegram_command_center`).
2. In the console, confirm: `MISSION_CONTROL_URL loaded: https://domainbuddy7-web-klipora-production.up.railway.app`.
3. In Telegram, open Status / Videos / Finance or trigger the pipeline; the "Could not reach Mission Control API" / "Mission Control API offline" message should not appear when the API is healthy.
4. `/internal/notify-preview` and other Mission Control endpoints should work when called by the workflows.

---

## Summary

| Item | Result |
|------|--------|
| **File where error originates** | `Command_Center/telegram_command_center.py` (panel/callback text); **logic** in `Command_Center/telegram_services/diagnostics.py` (`check_mission_control_connectivity`). |
| **Function producing the message** | `check_mission_control_connectivity()` (diagnostics) plus `_format_mission_control_for_ui()` and panel builders (telegram_command_center). |
| **Runtime value of MISSION_CONTROL_URL** | Logged at startup (masked). Resolved from env; default `https://domainbuddy7-web-klipora-production.up.railway.app` if unset. |
| **Root cause** | (1) Only one of `KEY=value.env` or `.env` was loaded, so `MISSION_CONTROL_URL` could be missing. (2) A 200 response with JSON but non-`application/json` Content-Type made `_api_get` return `{}`, so the health check was treated as "no response" and the system reported the API as unreachable. |
| **Code changes** | (1) Load both `KEY=value.env` and `.env` in `_load_env_file()` (removed `break`). (2) Startup log of `MISSION_CONTROL_URL`. (3) `run_telegram_bot.ps1` loads both env files. (4) `_api_get()` now tries to parse JSON on 200 even when Content-Type is not `application/json`, so a valid JSON health response is not misclassified as failure. |
