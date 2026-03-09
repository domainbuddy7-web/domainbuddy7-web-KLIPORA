# Telegram Dashboard — Modular Architecture Design

**Status:** Design + diagnostics service implemented (first refactor step).  
**Source:** Audit of `Command_Center/telegram_command_center.py` (~1,420 lines).

---

## 1. Current-State Audit

### 1.1 Menu Rendering Structure

- **Single entry point:** One `button()` handler receives all `callback_query.data` and branches with ~50+ `if data ==` / `if data.startswith()` checks.
- **Panel builders:** Each main panel has a `_build_*_panel()` that returns `(text: str, keyboard: InlineKeyboardMarkup)`. Builders live in the same file and call `_api_get()`, `_api_post()`, `_connectivity_diagnostics()`, and Redis helpers directly.
- **Dashboard home:** Rendered in two places—`start()` and `button()` for `panel_home` / `menu_main`—with duplicated title and subtitle text.
- **Wizard (Generate Video):** Multi-step flow (genre → visual → narration → duration → aspect → confirm) is implemented as a long linear block inside `button()` with state in `telegram:wizard:{chat_id}`. No dedicated “wizard” abstraction.
- **Topic/Genre:** Sub-panels (custom, popular, view) and their keyboards are in the same file; topic state lives in `telegram:topic_settings:{chat_id}`.

**Issues:** No separation between “which panel to show” and “how to fetch data”; home text duplicated; wizard and topic flows are hard to follow and extend.

### 1.2 Panel Handlers (Summary)

| Panel / flow        | Builder / entry              | Refresh / actions callback_data              | API/Redis used in UI code                          |
|---------------------|-----------------------------|----------------------------------------------|----------------------------------------------------|
| Home                | Inline in start/button      | —                                            | None                                               |
| System Status       | `_build_status_panel`       | refresh_status, action_diagnostics, action_pause | /health/system, /health, /finance/*, _connectivity_diagnostics |
| Video Factory       | `_build_videos_panel`       | panel_videos, action_run_cycle, menu_generate | /production, _connectivity_diagnostics             |
| Experiment Lab      | `_build_experiments_panel`  | refresh_experiments, terminate_exp_{i}        | /experiments                                       |
| Opportunity Radar   | `_build_opportunities_panel`| refresh_*, action_approve_opp, action_reject_opp, approve_opp_*, reject_opp_* | /opportunities, /commands/approve-opportunity, /commands/reject-opportunity |
| Finance Dashboard   | `_build_finance_panel`      | refresh_finance                               | /finance/budget, /finance/revenue                 |
| Automation Control  | `_build_automation_panel`   | refresh_automation, action_run_cycle, action_diagnostics | /automation                                        |
| Visual Styles       | `_build_visual_styles_panel`| visual_preset_{key}                           | Redis system:visual_style (get/set)                 |
| Topic / Genre       | Inline + _build_topic_view_message | panel_topic_*, topic_popular_*, action_custom_prompt | Redis telegram:topic_settings:{chat_id}            |
| Generate Video wizard| Inline in button()         | menu_generate, genre_*, vstyle_*, nstyle_*, duration_*, aspect_*, action_confirm_video | _get_state, _set_state, _get_topic_settings, _get_system_visual_style, _api_post(/commands/generate-video) |
| Settings            | Inline in button()         | menu_settings → home keyboard                 | None                                               |
| Diagnostics         | Inline in action_diagnostics| —                                            | _connectivity_diagnostics, /commands/system-diagnostics |
| Review actions      | N/A (message from MC)      | approve_publish_*, regenerate_*, discard_*, edit_meta_* | /commands/approve-publish, regenerate-job, discard-job, /commands/update-job-metadata |

All of the above are implemented in one file with no module boundaries.

### 1.3 Navigation Routing

- **Routing model:** Single `CallbackQueryHandler(button)`; routing is a long if/elif chain on `query.data`. No registry or map of `callback_data` → handler.
- **Patterns:**
  - **panel_*** → show panel (build content + keyboard, edit_message_text).
  - **refresh_*** → same as panel_* for that panel.
  - **action_*** → perform API/Redis action, then show a panel or message.
  - **menu_*** → either show a sub-menu (e.g. menu_generate → wizard step 1) or alias to panel (menu_status → status panel).
  - **Prefix handlers:** e.g. `visual_preset_*`, `topic_popular_*`, `genre_*`, `approve_publish_*`, `regenerate_*`, `discard_*`, `edit_meta_*`, `terminate_exp_*`, `approve_opp_*`, `reject_opp_*`.
- **Back navigation:** “Main dashboard” → `panel_home`. “◀️ Back” in wizards/topic → previous step or parent panel. No central navigation graph; each keyboard hardcodes callback_data.

**Issues:** Adding a panel or action requires editing the monolithic `button()`. No single place that defines “all routes” or “panel → possible next panels”.

### 1.4 Diagnostics System

- **Connectivity:** `_connectivity_diagnostics()` builds a string (MISSION_CONTROL_URL, /health, config_ok). Used from:
  - Generate-video failure (“API offline”).
  - Video Factory when /production fails.
  - `action_diagnostics` (combined with system-diagnostics).
- **System diagnostics:** `action_diagnostics` calls `_api_get("/commands/system-diagnostics")` and merges queues + stalled jobs with connectivity text. Rendered inline in `button()`.
- **n8n message:** Automation panel builder shows “Cannot fetch n8n workflows” + N8N_API_URL/N8N_API_KEY hint when /automation fails.

**Issues:** Diagnostics logic is mixed with UI (which panel/keyboard to show). No dedicated “diagnostics service” or “diagnostics view” module; hard to reuse or test.

### 1.5 API and Redis Access Inside UI Code

- **API:** All panels and actions call `_api_get()`, `_api_post()`, `_api_patch()` directly from panel builders and from inside `button()`. Base URL from `MISSION_CONTROL_URL` (module-level).
- **Redis:** Direct use of module-level `redis` and helpers: `_get_state`, `_set_state`, `_get_topic_settings`, `_set_topic_settings`, `_get_system_visual_style`, `_set_system_visual_style`, `_redis_key`, `_topic_settings_key`. No abstraction layer; keys and shapes are implicit.

**Issues:** UI code is tightly coupled to HTTP and Redis. Adding caching, retries, or a different backend would require touching many builders and handlers.

### 1.6 Button and Keyboard Creation

- **Keyboards:** One function per panel (e.g. `_status_panel_keyboard()`, `_videos_panel_keyboard()`) plus wizard keyboards (`genre_keyboard()`, `visual_keyboard()`, …), topic keyboards, and one-off `InlineKeyboardMarkup([[...]])` in handlers.
- **Reuse:** “Main dashboard” and “🔄 Refresh” are repeated in many keyboards with no shared component. Section separator `_SEP` and formatting (e.g. HTML) are ad hoc.
- **Constants:** GENRES, VISUAL_STYLES, NARRATION_STYLES, DURATIONS, ASPECTS, POPULAR_TOPICS, VISUAL_STYLE_PRESETS live in the same file as handlers.

**Issues:** No shared “nav row” or “standard buttons”; adding a new panel means copying the same pattern. Callback_data strings are magic strings (no single registry).

### 1.7 Dead Links and Unused Handlers

- **Unused keyboard:** `automation_keyboard()` is defined and returns a keyboard with action_run_cycle, action_pause, action_resume, action_diagnostics, panel_home. It is **never used**; the Automation panel uses `_automation_panel_keyboard()` instead. So `automation_keyboard()` is dead.
- **Aliases:** `menu_main` and `panel_home` both go to home (intentional). `menu_status`, `menu_finance`, `menu_experiments`, `menu_opportunities`, `menu_automation` duplicate panel_* (redundant but wired).
- **Review actions:** `approve_publish_*`, `regenerate_*`, `discard_*`, `edit_meta_*` are triggered from inline keyboards on the **review message** sent by Mission Control (not from a panel in this file). They are valid and must remain in the routing layer.
- **All other callback_data** used in the file have a corresponding branch in `button()`; no other dead links identified.

---

## 2. Proposed Module Structure

```
Command_Center/
  telegram_command_center.py   # Thin entry: config, bot setup, owner check, single router
  telegram_ui/                 # UI layer: panels and navigation
    __init__.py
    router.py                  # Callback routing registry and dispatcher
    home.py                    # Home dashboard view
    panels/
      __init__.py
      status.py               # System Status panel
      videos.py               # Video Factory panel
      experiments.py          # Experiment Lab panel
      opportunities.py        # Opportunity Radar panel
      finance.py              # Finance Dashboard panel
      automation.py           # Automation Control panel
      visual_styles.py        # Visual Styles panel
      topic.py                # Topic / Genre panel and sub-views
      settings.py             # Settings view
    wizard/
      __init__.py
      generate_video.py       # Generate Video 5-step wizard
    review_actions.py         # approve_publish, regenerate, discard, edit_meta (from MC message)
  telegram_components/        # Reusable UI building blocks
    __init__.py
    keyboards.py              # Shared keyboard factory (nav row, refresh, back, buttons)
    formatting.py             # _SEP, escape_html, section headers
    constants.py              # GENRES, VISUAL_STYLES, POPULAR_TOPICS, etc.
  telegram_services/          # Data and side effects (no Telegram types)
    __init__.py
    api.py                    # Mission Control API client (get/post/patch, base URL)
    redis_state.py            # Wizard state, topic settings, system:visual_style
    diagnostics.py            # Connectivity + system diagnostics (return structured or string)
```

---

## 3. Responsibilities by Module

### 3.1 `telegram_services/`

- **api.py**
  - Hold `MISSION_CONTROL_URL` (injected or from env).
  - Expose `api_get(path)`, `api_post(path, body)`, `api_patch(path, body)` returning decoded JSON or a canonical error shape (e.g. `{_error, _code}` / `{detail}`). No Telegram types.
  - Used by panels and by diagnostics.

- **redis_state.py**
  - Wizard state: get/set by `chat_id` (keys like `telegram:wizard:{chat_id}`).
  - Topic settings: get/set by `chat_id` (`telegram:topic_settings:{chat_id}`).
  - System visual style: get/set `system:visual_style`.
  - All Redis keys and value shapes live here; no raw Redis in UI.

- **diagnostics.py**
  - `connectivity_diagnostics(api_client) -> str`: URL check + /health, human-readable message (Mission Control offline / OK).
  - `system_diagnostics(api_client) -> dict | None`: call /commands/system-diagnostics, return queues + stalled_jobs or None.
  - Optional: `format_diagnostics_message(conn_str, system_dict) -> str` for the full diagnostics view. No keyboard or Update; pure data → text.

### 3.2 `telegram_components/`

- **keyboards.py**
  - `nav_row_home()` → list of buttons (e.g. one “🏠 Main dashboard” with `panel_home`).
  - `refresh_row(panel_refresh_callback_data)` → e.g. [Refresh].
  - `standard_panel_keyboard(rows, include_home=True)` → build InlineKeyboardMarkup from list of rows + optional home row.
  - Optional: `button(text, callback_data)` wrapper for consistent construction. All callback_data used by the app should be defined as constants (e.g. in constants.py) and referenced here and in panels.

- **formatting.py**
  - `SEP` (section separator).
  - `escape_html(s) -> str`.
  - Helpers like `section_title(title)` if needed for consistent headers.

- **constants.py**
  - GENRES, VISUAL_STYLES (wizard), NARRATION_STYLES, DURATIONS, ASPECTS.
  - POPULAR_TOPICS, VISUAL_STYLE_PRESETS.
  - Callback_data constants: e.g. `PANEL_HOME`, `PANEL_STATUS`, `REFRESH_STATUS`, `ACTION_DIAGNOSTICS`, … so routing and keyboards share one source of truth.

### 3.3 `telegram_ui/`

- **router.py**
  - Registry: map `callback_data` (exact or prefix) → handler function. Handlers have signature like `async def handler(update, context, chat_id, data) -> bool`; return True if handled.
  - Single `async def handle_callback(update, context)` that gets `query.data`, looks up handler(s) (e.g. exact match then prefix match), calls handler, returns. Fallback: show home or “Select an option” with main menu.
  - Registration: each panel/wizard/review module registers its callback_data and handler. No 50-branch if/elif in one function.

- **home.py**
  - `build_home_content() -> (text, keyboard)`: title “🏭 KLIPORA AI MEDIA FACTORY”, subtitle, and main dashboard keyboard (one place for home text).
  - Uses `telegram_components.keyboards` for the dashboard buttons (panels + settings).

- **panels/*.py (one file per panel)**
  - Each panel module exposes:
    - `build(chat_id, api_client, redis_state, diagnostics_service) -> (text, keyboard)`.
    - Optional: `handle_refresh(data) -> bool` and action handlers that perform API/Redis and return (text, keyboard) or redirect to another panel.
  - **status.py:** Uses api: /health/system, /health, /finance/budget, /finance/revenue; diagnostics for failure message; keyboard: Refresh, Diagnostics, Pause, Main dashboard.
  - **videos.py:** Uses api: /production; diagnostics on failure; keyboard: Generate Video, Review Pending, Run Production Cycle, Refresh, Main dashboard.
  - **experiments.py:** Uses api: /experiments; keyboard: Terminate 1/2/3, Refresh, Main dashboard.
  - **opportunities.py:** Uses api: /opportunities and approve/reject endpoints; keyboard: Approve, Reject, Refresh, Main dashboard.
  - **finance.py:** Uses api: /finance/budget, /finance/revenue; keyboard: Refresh, Main dashboard.
  - **automation.py:** Uses api: /automation; keyboard: Run production cycle, Refresh, Diagnostics, Main dashboard.
  - **visual_styles.py:** Uses redis_state for system:visual_style; keyboard: preset buttons, Main dashboard.
  - **topic.py:** Uses redis_state for topic_settings; sub-views: main topic menu, custom, popular list, view current; keyboards for each.
  - **settings.py:** Static text + main dashboard keyboard only.

- **wizard/generate_video.py**
  - State machine: steps genre → visual → narration → duration → aspect → confirm. State in redis_state (wizard state).
  - For each step: `build_step(chat_id, step_name, state, redis_state) -> (text, keyboard)`. Actions (e.g. genre_0, vstyle_dark_cinematic) update state and return next step or confirm.
  - On confirm: call api_client.post(/commands/generate-video) with body built from state + topic_settings + system visual_style; handle topic_already_used and API-offline via diagnostics; return success/failure message + main menu keyboard.
  - All wizard callback_data (genre_*, vstyle_*, nstyle_*, duration_*, aspect_*, aspect_back, etc.) registered and handled in this module; router dispatches to wizard when data matches.

- **review_actions.py**
  - Handlers for `approve_publish_{job_id}`, `regenerate_{job_id}`, `discard_{job_id}`, `edit_meta_{job_id}`. Call API; then edit message to success/error (and for edit_meta, set wizard state and ask for text reply). No panel build; pure action + message update.

### 3.4 `Command_Center/telegram_command_center.py` (entry point)

- Load env (_load_env_file), resolve MISSION_CONTROL_URL, TELEGRAM_BOT_TOKEN, OWNER_TELEGRAM_ID.
- Initialize redis client (or None); create api client, redis_state, diagnostics service.
- Owner check: _owner_only(update), _unauthorized_message(update).
- Command handlers: /start → home.build_home_content(); /status, /videos, … → corresponding panel.build(...). All use same api/redis_state/diagnostics instances.
- Message handler: handle_message for custom topic prompt and edit_meta reply; uses redis_state and api; may delegate to topic panel or review_actions for “what to show next”.
- Callback handler: single entry that calls `telegram_ui.router.handle_callback(update, context, api_client, redis_state, diagnostics)`.
- main(): build Application, add handlers, run_polling.

No panel logic or long if-chains in this file; only wiring and ownership.

---

## 4. Navigation Flow Between Panels

- **Explicit graph (conceptual):**
  - **Home** → System Status | Video Factory | Experiment Lab | Opportunity Radar | Finance | Automation | Visual Styles | Settings.
  - Each panel has: **Refresh** (same panel), **Main dashboard** (→ Home), and panel-specific actions (e.g. Video Factory → Generate Video → Wizard; Automation → Run production cycle; Status → Diagnostics / Pause).
  - **Wizard:** Entry from Video Factory (menu_generate). Steps: genre → visual → narration → duration → aspect → confirm. From any step, “Back” goes to previous step; “Cancel” (confirm screen) → Home. On confirm → API call then Home or error message + Home.
  - **Topic:** Entry from Topic/Genre (not from home in current design; could be linked from Video Factory or home). Sub-views: main → Custom | Popular | View current; Custom → prompt input; Popular → list; Back from each → Topic main or previous step.
  - **Review actions:** Not panels; triggered from review message (approve_publish_*, regenerate_*, discard_*, edit_meta_*). After action, message is updated in place; no panel transition.

- **Routing table (to be implemented in router.py):**
  - Exact: panel_home, menu_main, panel_status, panel_videos, … panel_visual_styles, menu_settings, refresh_status, … refresh_automation, action_diagnostics, action_pause, action_resume, action_run_cycle, action_confirm_video, action_approve_opp, action_reject_opp, menu_generate, menu_status, menu_finance, menu_experiments, menu_opportunities, menu_automation, panel_topic, panel_topic_custom, action_custom_prompt, panel_topic_popular, panel_topic_view.
  - Prefix: visual_preset_, topic_popular_, genre_, vstyle_, nstyle_, duration_, aspect_, approve_publish_, regenerate_, discard_, edit_meta_, terminate_exp_, approve_opp_, reject_opp_.

- **Registration:** Each panel/wizard/review module registers (callback_data or prefix, handler). Router looks up and dispatches; no single 500-line if/elif.

---

## 5. Keyboard/Button Component Reuse

- **Standard rows (in telegram_components/keyboards.py):**
  - `main_dashboard_button()` → one button “🏠 Main dashboard”, `panel_home`.
  - `refresh_button(callback_data)` → “🔄 Refresh” with given callback.
  - `row(*buttons)` → one row of InlineKeyboardButton.
  - `panel_footer(include_refresh: bool, refresh_data: str | None)` → e.g. [Refresh, Main dashboard] or [Main dashboard].

- **Panel keyboards:** Each panel builds its action rows (e.g. Status: [Refresh, Diagnostics], [Pause], [Main dashboard]) by composing these helpers plus panel-specific buttons (e.g. Terminate 1/2/3 from constants and a loop). No copy-paste of “Main dashboard” or “Refresh” strings.

- **Callback_data:** All values come from constants (e.g. CALLBACK_PANEL_HOME, CALLBACK_REFRESH_STATUS). Keyboards and router both import the same constants; no magic strings in the middle of handlers.

---

## 6. Diagnostics System Separation

- **Service (telegram_services/diagnostics.py):**
  - Input: API client (or URL + get function).
  - Output: strings or dicts, no Telegram types.
  - `connectivity_diagnostics() -> str`: for “API unreachable” or “n8n workflows unreachable” messages.
  - `system_diagnostics() -> dict | None`: raw system-diagnostics payload.
  - Optional: `format_full_diagnostics(conn_str, system_dict) -> str` for the Diagnostics panel body.

- **Usage in UI:**
  - Status panel: on /health/system failure, use connectivity_diagnostics() for the message body.
  - Video Factory: on /production failure, use same.
  - Generate-video failure: use connectivity_diagnostics() in the error message.
  - action_diagnostics: call connectivity_diagnostics() and system_diagnostics(); if system_diagnostics is None, show connectivity only; else show format_full_diagnostics(...). Keyboard is always status_panel_keyboard (or a shared “back to status” keyboard).

- **n8n-specific message:** “Cannot fetch n8n workflows … N8N_API_URL and N8N_API_KEY” can live in automation panel builder as a string constant or a small helper in diagnostics (e.g. `n8n_unavailable_message() -> str`) so automation panel only composes text, not logic.

Result: all “what to say when something is wrong” and “what to fetch for diagnostics” live in telegram_services; panels only decide “show this text with this keyboard”.

---

## DIAGNOSTICS SERVICE IMPLEMENTATION

**Implemented.** Diagnostics logic has been moved out of the monolithic Telegram file into the service layer.

### Location

- **From:** `Command_Center/telegram_command_center.py` (previously: `_connectivity_diagnostics()` and inline diagnostics in panels and `action_diagnostics`).
- **To:** `Command_Center/telegram_services/diagnostics.py`.

### Diagnostics service API

The diagnostics service provides:

| Function | Purpose |
|----------|---------|
| `check_mission_control_connectivity(api_get, base_url)` | Verifies base URL is set and calls Mission Control `/health`. Returns `{ "url", "reachable", "message", "config_ok" }`. |
| `check_n8n_connectivity(api_get)` | Calls Mission Control `/automation` (n8n workflow fetch). Returns `{ "reachable", "message", "workflow_count" }`. |
| `check_redis_connectivity(redis)` | Pings Redis (e.g. one read). Returns `{ "reachable", "message" }`. |
| `run_system_diagnostics(api_get, base_url, redis)` | Runs all three checks. Returns `{ "mission_control", "n8n", "redis" }` (each value is the respective function's result). |

All functions return **structured dictionaries** only; no Telegram types or HTML.

### Responsibilities

**Diagnostics service (`telegram_services/diagnostics.py`):**

- Performs connectivity checks (Mission Control, n8n via MC, Redis).
- Communicates with API and Redis (receives `api_get` callable and redis client; does not hold config).
- Returns structured dictionaries (e.g. `reachable`, `message`, optional counts/config).

**Telegram UI (`telegram_command_center.py`):**

- Calls the diagnostics service and receives the structured result.
- Formats diagnostics output for display (e.g. `_format_mission_control_for_ui()`, `_format_full_diagnostics_for_ui()`).
- Displays formatted messages to users (same panels and keyboards as before).
- Does **not** perform connectivity logic; it only formats and shows what the service returns.

This keeps connectivity and data-fetching in the service layer and keeps the UI focused on presentation and user interaction.

---

## 7. Summary Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│  telegram_command_center.py (entry)                                      │
│  - Config, env, owner check                                              │
│  - CommandHandler(/start, /status, …) → home / panel.build()              │
│  - MessageHandler → handle_message (topic prompt, edit_meta)              │
│  - CallbackQueryHandler → router.handle_callback()                       │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  telegram_ui/router.py                                                   │
│  - Registry: callback_data → handler                                     │
│  - handle_callback(update, context, api, redis_state, diagnostics)       │
│  - Dispatch to panel / wizard / review_actions handlers                   │
└─────────────────────────────────────────────────────────────────────────┘
         │                    │                          │
         ▼                    ▼                          ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐
│  telegram_ui/   │  │  telegram_ui/   │  │  telegram_ui/                │
│  home.py        │  │  panels/*.py    │  │  wizard/, review_actions.py  │
│  panels/*.py    │  │  (build +       │  │  (build step / do action)    │
│  (build content │  │   register      │  │                              │
│   + keyboard)   │  │   routes)       │  │                              │
└────────┬────────┘  └────────┬────────┘  └──────────────┬────────────────┘
         │                   │                          │
         └───────────────────┼──────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐
│  telegram_      │  │  telegram_      │  │  telegram_services/         │
│  components/    │  │  services/      │  │  diagnostics.py             │
│  keyboards.py   │  │  api.py         │  │  (connectivity + system     │
│  formatting.py  │  │  redis_state.py │  │   diagnostics strings)       │
│  constants.py   │  │                 │  │                              │
└─────────────────┘  └─────────────────┘  └─────────────────────────────┘
```

---

## 8. Migration Notes (for future refactor)

- **Order of extraction:** (1) constants + formatting, (2) api + redis_state + diagnostics, (3) keyboards, (4) one panel at a time (e.g. home, then status, videos, …), (5) wizard, (6) review_actions, (7) router and removal of branches from telegram_command_center.
- **Backward compatibility:** Keep callback_data strings identical so existing review messages and saved states still work.
- **Remove dead code:** Drop `automation_keyboard()` when Automation panel is fully served by panels/automation.py.
- **Testing:** Services (api, redis_state, diagnostics) and components (keyboards, formatting) can be unit-tested without Telegram; panel build() can be tested with mock api/redis_state/diagnostics.

No code has been refactored in this step; this document is the architecture design only.
