"""
KLIPORA Telegram Mission Console — Live control terminal for the AI company.

Command-based panels with real-time refresh (edit_message_text).
/start, /status, /videos, /experiments, /opportunities, /finance, /automation.
Owner-only. State: telegram:wizard:{chat_id}
Env: TELEGRAM_BOT_TOKEN, MISSION_CONTROL_URL, OWNER_TELEGRAM_ID (or TELEGRAM_CHAT_ID)
Run: python -m Command_Center.telegram_command_center
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone, timedelta
import threading
import time

import requests

# Add repo root for imports
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)


def _looks_like_telegram_token(s: str) -> bool:
    """Real Telegram tokens: digits:alphanumeric, ~45 chars; reject only obvious placeholder (xxx)."""
    if not s or len(s) < 40:
        return False
    if ":" not in s:
        return False
    left, _, right = s.partition(":")
    if left.isdigit() and len(right) >= 30:
        if right.endswith("xxxx") or "xxxxxxxx" in right:
            return False
        return True
    return False

# Example/placeholder owner IDs that must never override a real ID in KEY=value.env
_OWNER_ID_PLACEHOLDERS = frozenset({
    "123456789", "987654321", "111111111", "12345678", "000000000",
    "1234567", "999999999", "123456", "654321", "111111", "999999",
})

def _looks_like_real_owner_id(s: str) -> bool:
    """True if s looks like a real Telegram user ID (numeric, 8+ digits, not a known placeholder)."""
    if not s or not isinstance(s, str):
        return False
    s = str(s).strip()
    if not s.isdigit() or len(s) < 8:
        return False
    return s not in _OWNER_ID_PLACEHOLDERS

def _load_env_file() -> None:
    """Load KEY=value.env and .env (both if present). .env is loaded after KEY=value.env so it overrides.
    Owner/chat IDs: only set if value is real (never overwrite with placeholder).
    Token: only from line with key TELEGRAM_BOT_TOKEN/BOT_TOKEN (never overwrite with token found in comments)."""
    token_keys = ("TELEGRAM_BOT_TOKEN", "BOT_TOKEN", "telegram_bot_token")
    owner_id_keys = ("OWNER_TELEGRAM_ID", "TELEGRAM_CHAT_ID", "telegram_chat_id", "owner_telegram_id")
    for name in ("KEY=value.env", ".env"):
        path = os.path.join(_ROOT, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line and not line.startswith("="):
                        key, _, value = line.partition("=")
                        key = key.strip().lstrip("|").strip()
                        value = value.strip().strip('"').strip("'").rstrip("|").strip()
                        if not key:
                            continue
                        # Token: only set from explicit TELEGRAM_BOT_TOKEN/BOT_TOKEN line (avoid overwriting with token from comments/other keys)
                        if key in token_keys:
                            if value:
                                os.environ["TELEGRAM_BOT_TOKEN"] = value
                            continue
                        # Never set owner/chat ID from a placeholder (e.g. 123456789); first real ID wins
                        if key in owner_id_keys:
                            if value and _looks_like_real_owner_id(value):
                                os.environ[key] = value
                        else:
                            os.environ[key] = value
        except Exception:
            pass


_load_env_file()

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from Command_Center.telegram_services.diagnostics import (
    check_mission_control_connectivity,
    run_system_diagnostics,
)

# ── Config ─────────────────────────────────────────────────────────────────
_raw_url = (
    os.environ.get("MISSION_CONTROL_URL")
    or os.environ.get("mission_control_url")
    or ""
).strip().rstrip("/")
# Default if nothing set or empty (user can override in KEY=value.env)
MISSION_CONTROL_URL = _raw_url or "https://domainbuddy7-web-klipora-production.up.railway.app"
if not _raw_url:
    # Env did not provide a URL – we are falling back to the default.
    print("WARNING: MISSION_CONTROL_URL is empty. Falling back to default Railway URL.", flush=True)
if not MISSION_CONTROL_URL:
    print("WARNING: MISSION_CONTROL_URL is empty. Add it to KEY=value.env or .env and restart.", flush=True)
else:
    print(f"MISSION_CONTROL_URL loaded: {MISSION_CONTROL_URL}", flush=True)

TELEGRAM_BOT_TOKEN = (
    os.environ.get("TELEGRAM_BOT_TOKEN")
    or os.environ.get("BOT_TOKEN")
    or os.environ.get("telegram_bot_token")
)
# Resolve owner: prefer first real ID; never use placeholder (123456789 etc.)
_raw_owner = (
    os.environ.get("OWNER_TELEGRAM_ID")
    or os.environ.get("TELEGRAM_CHAT_ID")
    or os.environ.get("telegram_chat_id")
    or ""
)
OWNER_TELEGRAM_ID = _raw_owner if _looks_like_real_owner_id(_raw_owner) else None

try:
    from Infrastructure.redis_client import get_redis_client
    redis = get_redis_client()
except Exception:
    redis = None

def _redis_key(chat_id: int) -> str:
    return f"telegram:wizard:{chat_id}"

def _get_state(chat_id: int) -> dict:
    if not redis:
        return {}
    raw = redis.get(_redis_key(chat_id))
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except Exception:
        return {}

def _set_state(chat_id: int, state: dict) -> None:
    if not redis:
        return
    redis.set(_redis_key(chat_id), json.dumps(state))


def _topic_settings_key(chat_id: int) -> str:
    return f"telegram:topic_settings:{chat_id}"


def _get_topic_settings(chat_id: int) -> dict:
    """Return topic_mode (popular|custom), topic (label or null), custom_prompt (str or null)."""
    if not redis:
        return {"topic_mode": "popular", "topic": None, "custom_prompt": None}
    raw = redis.get(_topic_settings_key(chat_id))
    if not raw:
        return {"topic_mode": "popular", "topic": None, "custom_prompt": None}
    try:
        data = json.loads(raw)
        return {
            "topic_mode": data.get("topic_mode", "popular"),
            "topic": data.get("topic"),
            "custom_prompt": data.get("custom_prompt"),
        }
    except Exception:
        return {"topic_mode": "popular", "topic": None, "custom_prompt": None}


def _set_topic_settings(chat_id: int, data: dict) -> None:
    if not redis:
        return
    redis.set(_topic_settings_key(chat_id), json.dumps(data))


def _get_system_visual_style() -> str | None:
    """Return Redis system:visual_style (preset key e.g. ghibli, creepytoon) or None."""
    if not redis:
        return None
    return redis.get("system:visual_style") or None


def _set_system_visual_style(value: str) -> None:
    """Store system:visual_style in Redis."""
    if not redis:
        return
    redis.set("system:visual_style", value)


def _api_get(path: str) -> dict:
    """
    GET Mission Control; strict version used by diagnostics and panels.

    Requirements:
    - If MISSION_CONTROL_URL is empty → RuntimeError
    - If HTTP request fails → propagate exception
    - If HTTP status != 200 → raise error with status code
    - On HTTP 200: always attempt r.json() regardless of Content-Type.
      Return parsed JSON when possible; return {} only if JSON parsing fails.
    """
    if not MISSION_CONTROL_URL:
        raise RuntimeError("MISSION_CONTROL_URL is empty")
    url = f"{MISSION_CONTROL_URL}{path}"
    try:
        r = requests.get(url, timeout=15)
    except Exception as exc:
        raise RuntimeError(f"Request to {url} failed: {exc!s}") from exc

    if r.status_code != 200:
        # Include short body snippet (if any) for easier diagnostics.
        snippet = ""
        try:
            text = r.text or ""
            snippet = f" body={text[:200]!r}" if text else ""
        except Exception:
            snippet = ""
        raise RuntimeError(f"HTTP {r.status_code} from {url}{snippet}")

    try:
        return r.json()
    except Exception:
        # Valid 200 but non-JSON body; treat as empty JSON per specification.
        return {}

def _api_post(path: str, json_body: dict | None = None) -> dict:
    if not MISSION_CONTROL_URL:
        return {}
    try:
        r = requests.post(f"{MISSION_CONTROL_URL}{path}", json=json_body or {}, timeout=15)
        if r.ok:
            return r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        try:
            body = r.json()
            if isinstance(body, dict) and ("detail" in body or "message" in body):
                return body
            return {"detail": body if isinstance(body, str) else f"HTTP {r.status_code}"}
        except Exception:
            return {"detail": f"HTTP {r.status_code}"}
    except Exception:
        return {}


def _api_patch(path: str, json_body: dict | None = None) -> dict:
    if not MISSION_CONTROL_URL:
        return {}
    try:
        r = requests.patch(f"{MISSION_CONTROL_URL}{path}", json=json_body or {}, timeout=15)
        return r.json() if r.ok else {}
    except Exception:
        return {}


def _send_telegram_alert(text: str) -> None:
    """Best-effort Telegram alert to the owner chat."""
    token = TELEGRAM_BOT_TOKEN
    chat_id = (
        (str(OWNER_TELEGRAM_ID).strip() if OWNER_TELEGRAM_ID else "")
        or os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        or os.environ.get("OWNER_TELEGRAM_ID", "").strip()
    )
    if not token or not chat_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
    except Exception:
        # Alerts are best-effort; never crash the bot because of this.
        pass


def mission_control_health_loop() -> None:
    """
    Background health monitor for Mission Control.

    Every 60 seconds:
    - GET {MISSION_CONTROL_URL}/health
    - On 200: print 'Mission Control OK' and reset failure counter.
    - On failure (exception or non-200 via _api_get): print 'Mission Control unreachable'.
    - After 5 consecutive failures: send Telegram alert to the owner.
    """
    failures = 0
    while True:
        time.sleep(60)
        try:
            if not MISSION_CONTROL_URL:
                print("Mission Control unreachable (MISSION_CONTROL_URL empty).", flush=True)
                failures += 1
            else:
                # Use the strict helper so non-200 becomes an error as well.
                _ = _api_get("/health")
                print("Mission Control OK", flush=True)
                failures = 0
        except Exception as exc:
            print(f"Mission Control unreachable: {exc!s}", flush=True)
            failures += 1

        if failures >= 5:
            _send_telegram_alert(
                "🚨 KLIPORA ALERT\n"
                "Mission Control API unreachable.\n"
                "Check Railway deployment or network connectivity."
            )
            # Do not spam continuously; alert again only after another streak.
            failures = 0


def _format_mission_control_for_ui(mc: dict) -> str:
    """Format Mission Control connectivity result (from diagnostics service) for Telegram HTML."""
    lines = []
    url = (mc.get("url") or "").strip()
    if not url:
        lines.append("❌ <b>MISSION_CONTROL_URL</b> is not set.")
        lines.append("Add it in KEY=value.env and restart the bot.")
        return "\n".join(lines)
    lines.append(f"📍 <b>MISSION_CONTROL_URL</b>\n<code>{_escape_html(url)}</code>")
    if not mc.get("reachable"):
        lines.append("\n❌ <b>Mission Control API offline</b>")
        lines.append("Check Railway deployment or MISSION_CONTROL_URL.")
        lines.append(f"\n<code>/health</code> → {_escape_html(mc.get('message', '')[:120])}")
        return "\n".join(lines)
    if mc.get("config_ok") is not True:
        lines.append("\n⚠️ API reachable but config missing (Redis/n8n env on Railway).")
    else:
        lines.append("\n✅ API <code>/health</code> OK")
    return "\n".join(lines)


def _format_full_diagnostics_for_ui(summary: dict, system_diagnostics: dict | None) -> str:
    """Format run_system_diagnostics() result and optional system-diagnostics payload for Telegram."""
    mc = summary.get("mission_control", {})
    n8n = summary.get("n8n", {})
    red = summary.get("redis", {})
    lines = [
        "🔍 <b>Connectivity diagnostics</b>\n" + _SEP + "\n",
        _format_mission_control_for_ui(mc),
        "",
        f"<b>n8n</b> {n8n.get('message', '—')}",
        f"<b>Redis</b> {red.get('message', '—')}",
    ]
    if system_diagnostics and not system_diagnostics.get("_error"):
        q = system_diagnostics.get("queues", {})
        stalled = system_diagnostics.get("stalled_jobs", [])
        lines.extend([
            "",
            f"<b>Queues</b> script={q.get('script_queue', 0)} render={q.get('render_queue', 0)} "
            f"publish={q.get('publish_queue', 0)} failed={q.get('failed_queue', 0)}",
            f"<b>Stalled jobs</b> {len(stalled)}",
        ])
    return "\n".join(lines)


def _owner_only(update: Update) -> bool:
    if not OWNER_TELEGRAM_ID:
        return True
    user_id = str(update.effective_user.id) if update.effective_user else None
    chat_id = str(update.effective_chat.id) if update.effective_chat else None
    owner = str(OWNER_TELEGRAM_ID).strip()
    return user_id == owner or chat_id == owner


def _unauthorized_message(update: Update) -> str:
    """Message when owner check fails; include user ID so they can add it to env."""
    uid = update.effective_user.id if update.effective_user else None
    cid = update.effective_chat.id if update.effective_chat else None
    msg = "⛔ Unauthorized. Only the owner can use this bot."
    if uid is not None:
        msg += f"\n\nYour Telegram ID: <code>{uid}</code>\nAdd to KEY=value.env:\nOWNER_TELEGRAM_ID={uid}\nThen restart the bot."
    return msg


def _next_run_uae() -> str:
    """Next scheduled run: 12:00 or 20:00 UAE (08:00 or 16:00 UTC)."""
    now = datetime.now(timezone.utc).time()
    eight = datetime(2000, 1, 1, 8, 0, tzinfo=timezone.utc).time()
    sixteen = datetime(2000, 1, 1, 16, 0, tzinfo=timezone.utc).time()
    if now < eight:
        return "12:00 UAE"
    if now < sixteen:
        return "20:00 UAE"
    return "12:00 UAE (tomorrow)"


# ── Mission Console: panel content builders (live data) ───────────────────────
def _build_status_panel() -> tuple[str, InlineKeyboardMarkup]:
    """System Control Panel: /status. Returns (text, keyboard)."""
    h = _api_get("/health/system")
    rev = _api_get("/finance/revenue")
    bud = _api_get("/finance/budget")
    failed = not h or h.get("_error")
    if failed:
        url_hint = ""
        if not MISSION_CONTROL_URL:
            url_hint = "\n\nAdd to KEY=value.env:\nMISSION_CONTROL_URL=https://domainbuddy7-web-klipora-production.up.railway.app"
        else:
            url_hint = f"\n\nCurrent URL: <code>{MISSION_CONTROL_URL}</code>\nIf wrong, fix in KEY=value.env and restart the bot."
        reason = ""
        if h and h.get("_error"):
            err = h["_error"]
            code = h.get("_code")
            if code == 503:
                reason = " (API returned 503 — check Railway env: UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN, N8N_URL, then redeploy)"
            elif err == "timeout":
                reason = " (timeout — try again or check if this machine can reach Railway; firewall/VPN may block)"
            elif err == "connection failed":
                reason = " (connection failed — bot cannot reach Railway from this network; try same URL in browser from this PC)"
            elif err.startswith("HTTP "):
                reason = f" ({err})"
            else:
                reason = f" ({err})"
        # If /health/system failed, check whether we can reach the API at all (e.g. /health works in browser)
        reach = _api_get("/health")
        if reach and not reach.get("_error") and reach.get("config_ok") is True:
            return (
                f"📊 <b>SYSTEM STATUS</b>\n{_SEP}\n⚠️ Health check failed"
                + reason
                + ", but the API root is reachable (config_ok: true). Try Refresh again or check Railway logs."
                + url_hint,
                _status_panel_keyboard(),
            )
        return (
            f"📊 <b>SYSTEM STATUS</b>\n{_SEP}\n⚠️ Cannot reach Mission Control"
            + reason
            + "."
            + url_hint
            + "\n\nThen restart the bot.",
            _status_panel_keyboard(),
        )
    status = h.get("status", "?")
    flags = h.get("flags", {})
    queues = h.get("queues", {})
    failures = h.get("n8n_failures", {})
    n8n_ok = sum(failures.values()) < 5 if isinstance(failures, dict) else True
    redis_ok = status != "config_missing"
    sc = "✅" if redis_ok else "❌"
    nc = "✅" if n8n_ok else "⚠️"
    msg = (
        "📊 <b>SYSTEM STATUS</b>\n"
        f"{_SEP}\n"
        f"{sc} Redis   {nc} n8n\n\n"
        "📈 <b>Production</b>\n"
        f"   Today: {flags.get('daily_count', 0)} / {flags.get('videos_per_day', 2)} videos\n"
        f"   ⏱ Next run: {_next_run_uae()}\n\n"
        "📦 <b>Queues</b>\n"
        f"   Script {queues.get('script_queue', 0)} → Render {queues.get('render_queue', 0)} → Publish {queues.get('publish_queue', 0)}\n\n"
    )
    if bud:
        msg += f"<b>Budget</b> ${bud.get('remaining', 0):.2f} left\n"
    if rev:
        msg += f"Revenue today ${rev.get('today', 0):.2f}\n"
    return msg.strip(), _status_panel_keyboard()


def _build_videos_panel() -> tuple[str, InlineKeyboardMarkup]:
    """Video Factory Panel: /videos. Shows production stats and actions."""
    prod = _api_get("/production")
    if not prod or prod.get("_error"):
        mc = check_mission_control_connectivity(_api_get, MISSION_CONTROL_URL)
        diag = _format_mission_control_for_ui(mc)
        return (
            f"🎬 <b>VIDEO FACTORY</b>\n{_SEP}\n"
            "❌ <b>Mission Control API offline</b>\n\n"
            f"{diag}",
            _videos_panel_keyboard(),
        )
    q = prod.get("queues", {})
    today = prod.get("videos_generated_today", 0)
    cap = prod.get("target_videos_per_day", 2)
    script_q = q.get("script_queue", 0) or 0
    render_q = q.get("render_queue", 0) or 0
    publish_q = q.get("publish_queue", 0) or 0
    msg = (
        "🎬 <b>VIDEO FACTORY</b>\n"
        f"{_SEP}\n\n"
        "📊 <b>Today's production</b>\n"
        f"   Videos created: <b>{today}</b> / {cap}\n\n"
        "📋 <b>Queues</b>\n"
        f"   Script: {script_q} → Render: {render_q} → Publish: {publish_q}\n\n"
        "⏱ <b>Next scheduled run</b>\n"
        f"   {_next_run_uae()}\n\n"
        "5 scenes · 9:16 · 20–50s · Review in Telegram when ready."
    )
    return msg, _videos_panel_keyboard()


def _build_experiments_panel() -> tuple[str, InlineKeyboardMarkup]:
    """Experiment Lab Panel: /experiments. Max 3 active; each shows revenue, cost, conversion, duration."""
    e = _api_get("/experiments")
    exps = e.get("experiments", []) if e else []
    if not exps:
        msg = f"🧪 <b>EXPERIMENT LAB</b>\n{_SEP}\nNo active experiments.\n\nMax 3 at a time."
        return msg, _experiments_panel_keyboard(exps)
    lines = []
    for i, x in enumerate(exps[:5], 1):
        title = x.get("title", x.get("id", "?"))
        roi = x.get("roi", x.get("status", "—"))
        rev = x.get("revenue", x.get("revenue_today", "—"))
        cost = x.get("cost", x.get("spent", "—"))
        conv = x.get("conversion_rate", "—")
        dur = x.get("duration", x.get("duration_days", "—"))
        lines.append(f"{i}️⃣ {title}\n   ROI {roi} · Rev {rev} · Cost {cost} · Conv {conv} · {dur}")
    msg = f"🧪 <b>EXPERIMENT LAB</b>\n{_SEP}\n" + "\n\n".join(lines)
    return msg, _experiments_panel_keyboard(exps)


def _experiments_panel_keyboard(exps: list | None = None) -> InlineKeyboardMarkup:
    """Keyboard with Terminate per experiment (callback_data max 64 bytes: terminate_exp_0, 1, 2)."""
    rows = []
    if exps:
        for i in range(min(len(exps), 3)):
            rows.append([InlineKeyboardButton(f"❌ Terminate {i + 1}", callback_data=f"terminate_exp_{i}")])
    rows.append([InlineKeyboardButton("🔄 Refresh", callback_data="refresh_experiments")])
    rows.append([InlineKeyboardButton("🏠 Main dashboard", callback_data="panel_home")])
    return InlineKeyboardMarkup(rows)


def _build_opportunities_panel() -> tuple[str, InlineKeyboardMarkup]:
    """Opportunity Radar Panel: /opportunities."""
    o = _api_get("/opportunities")
    opps = o.get("opportunities", []) if o else []
    if not opps:
        msg = f"📡 <b>OPPORTUNITY RADAR</b>\n{_SEP}\nNo pending opportunities."
    else:
        opp = opps[0]
        msg = (
            f"📡 <b>OPPORTUNITY RADAR</b>\n{_SEP}\n"
            f"<b>{opp.get('title', '?')}</b>\n\n"
            f"📶 Signal: {opp.get('demand', opp.get('score', '—'))}\n"
            f"💵 Cost: ${opp.get('estimated_cost', opp.get('cost', '?'))}\n"
            f"📈 Revenue: {opp.get('estimated_revenue', '—')}\n\n"
            "Approve or reject below."
        )
    return msg, _opportunities_panel_keyboard()


def _build_finance_panel() -> tuple[str, InlineKeyboardMarkup]:
    """Finance Dashboard: /finance."""
    bud = _api_get("/finance/budget")
    rev = _api_get("/finance/revenue")
    if not bud or (isinstance(bud, dict) and bud.get("_error")):
        err = "Mission Control unreachable or no budget data." if (not bud or bud.get("_error")) else "No budget data."
        return (
            f"💰 <b>FINANCE DASHBOARD</b>\n{_SEP}\n⚠️ " + err + "\n\nCheck MISSION_CONTROL_URL and that the API is running.",
            _finance_panel_keyboard(),
        )
    rev = rev if isinstance(rev, dict) and not rev.get("_error") else {}
    msg = (
        f"💰 <b>FINANCE DASHBOARD</b>\n{_SEP}\n"
        f"💼 Capital  ${bud.get('capital_initial', 440):.2f}\n"
        f"📤 Spent    ${bud.get('spent', 0):.2f}\n"
        f"✅ <b>Left    ${bud.get('remaining', 0):.2f}</b>\n\n"
        f"📈 Today  ${rev.get('today', 0):.2f}   Month  ${rev.get('month', 0):.2f}"
    )
    return msg, _finance_panel_keyboard()


def _build_automation_panel() -> tuple[str, InlineKeyboardMarkup]:
    """Automation Control Panel: /automation."""
    a = _api_get("/automation")
    wfs = a.get("workflows", []) if isinstance(a, dict) and not a.get("_error") else []
    if not wfs:
        return (
            f"⚙️ <b>AUTOMATION CONTROL</b>\n{_SEP}\n"
            "⚠️ <b>Cannot fetch n8n workflows</b>\n\n"
            "Check N8N_API_URL and N8N_API_KEY (Mission Control / Railway).",
            _automation_panel_keyboard(),
        )
    lines = []
    for w in wfs[:10]:
        name = (w.get("name") or w.get("id") or "?").replace("WF-", "")
        state = "🟢" if w.get("active") else "⚪"
        lines.append(f"  {state} {name}")
    msg = f"⚙️ <b>AUTOMATION</b>\n{_SEP}\n" + "\n".join(lines)
    return msg, _automation_panel_keyboard()


# ── Mission Console: panel keyboards (Refresh + actions) ─────────────────────
_SEP = "────────────────────────────"

# Visual style presets (display label, Redis value for system:visual_style)
VISUAL_STYLE_PRESETS = [
    ("👻 CreepyToon", "creepytoon"),
    ("🌿 Ghibli Style", "ghibli"),
    ("🧠 Analog Horror", "analog_horror"),
    ("🛰 Sci-Fi Documentary", "sci_fi_documentary"),
    ("🎭 Dark Mystery", "dark_mystery"),
]

# Popular topics: (display label, callback_data key suffix)
POPULAR_TOPICS = [
    ("Bible Stories", "bible_stories"),
    ("Random AI Story", "random_ai_story"),
    ("Travel Destinations", "travel_destinations"),
    ("What If?", "what_if"),
    ("Scary Stories", "scary_stories"),
    ("Bedtime Stories", "bedtime_stories"),
    ("Interesting History", "interesting_history"),
    ("Urban Legends", "urban_legends"),
    ("Motivational", "motivational"),
    ("Fun Facts", "fun_facts"),
    ("Long Form Jokes", "long_form_jokes"),
    ("Life Pro Tips", "life_pro_tips"),
    ("ELI5", "eli5"),
    ("Philosophy", "philosophy"),
    ("Product Marketing", "product_marketing"),
    ("UGC Hook", "ugc_hook"),
    ("Fake Text Message", "fake_text_message"),
    ("Engagement Bait", "engagement_bait"),
    ("Web Search", "web_search"),
]


def _console_home_keyboard() -> InlineKeyboardMarkup:
    """Main dashboard: structured layout to all panels."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 System Status", callback_data="panel_status")],
        [InlineKeyboardButton("🎬 Video Factory", callback_data="panel_videos")],
        [InlineKeyboardButton("🧪 Experiment Lab", callback_data="panel_experiments")],
        [InlineKeyboardButton("📡 Opportunity Radar", callback_data="panel_opportunities")],
        [InlineKeyboardButton("💰 Finance Dashboard", callback_data="panel_finance")],
        [InlineKeyboardButton("⚙ Automation Control", callback_data="panel_automation")],
        [InlineKeyboardButton("🎨 Visual Styles", callback_data="panel_visual_styles")],
        [InlineKeyboardButton("🛠 Settings", callback_data="menu_settings")],
    ])


def _status_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh_status"),
            InlineKeyboardButton("🔍 Diagnostics", callback_data="action_diagnostics"),
        ],
        [InlineKeyboardButton("⏸ Pause System", callback_data="action_pause")],
        [InlineKeyboardButton("🏠 Main dashboard", callback_data="panel_home")],
    ])


def _videos_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Generate Video", callback_data="menu_generate")],
        [
            InlineKeyboardButton("📋 Review Pending", callback_data="panel_videos"),
            InlineKeyboardButton("🔄 Run Production Cycle", callback_data="action_run_cycle"),
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="panel_videos"),
            InlineKeyboardButton("🏠 Main dashboard", callback_data="panel_home"),
        ],
    ])




def _opportunities_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data="action_approve_opp"),
            InlineKeyboardButton("❌ Reject", callback_data="action_reject_opp"),
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh_opportunities"),
            InlineKeyboardButton("🏠 Main dashboard", callback_data="panel_home"),
        ],
    ])


def _finance_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_finance")],
        [InlineKeyboardButton("🏠 Main dashboard", callback_data="panel_home")],
    ])


def _automation_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Run production cycle", callback_data="action_run_cycle")],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="refresh_automation"),
            InlineKeyboardButton("🔍 Diagnostics", callback_data="action_diagnostics"),
        ],
        [InlineKeyboardButton("🏠 Main dashboard", callback_data="panel_home")],
    ])


def _build_visual_styles_panel() -> tuple[str, InlineKeyboardMarkup]:
    """Visual Styles panel: presets stored in Redis system:visual_style."""
    current = _get_system_visual_style()
    current_label = next((label for label, key in VISUAL_STYLE_PRESETS if key == current), None)
    line = f"Current: <b>{_escape_html(current_label or 'Default (wizard)')}</b>" if current_label or current else "Current: <b>Default (wizard)</b>"
    msg = (
        f"🎨 <b>Visual Styles</b>\n{_SEP}\n"
        "Choose a preset look for generated videos.\n"
        "Stored in <code>system:visual_style</code> and sent with Generate Video.\n\n"
        f"{line}"
    )
    return msg, _visual_styles_keyboard(current)


def _visual_styles_keyboard(current_key: str | None) -> InlineKeyboardMarkup:
    rows = []
    for label, key in VISUAL_STYLE_PRESETS:
        prefix = "✅ " if key == current_key else ""
        rows.append([InlineKeyboardButton(f"{prefix}{label}", callback_data=f"visual_preset_{key}")])
    rows.append([InlineKeyboardButton("🏠 Main dashboard", callback_data="panel_home")])
    return InlineKeyboardMarkup(rows)


# ── Topic / Genre menu ───────────────────────────────────────────────────────
def _topic_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ Custom Topic", callback_data="panel_topic_custom")],
        [InlineKeyboardButton("🔥 Popular Topics", callback_data="panel_topic_popular")],
        [InlineKeyboardButton("📊 View Current Topic", callback_data="panel_topic_view")],
        [InlineKeyboardButton("🏠 Main dashboard", callback_data="panel_home")],
    ])


def _topic_custom_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Custom Prompt", callback_data="action_custom_prompt")],
        [InlineKeyboardButton("◀️ Back", callback_data="panel_topic")],
    ])


def _topic_popular_keyboard(selected_key: str | None) -> InlineKeyboardMarkup:
    """Popular topics list; selected_key is the callback suffix (e.g. urban_legends)."""
    rows = []
    for label, key in POPULAR_TOPICS:
        prefix = "✅ " if key == selected_key else ""
        rows.append([InlineKeyboardButton(f"{prefix}{label}", callback_data=f"topic_popular_{key}")])
    rows.append([InlineKeyboardButton("◀️ Back", callback_data="panel_topic")])
    return InlineKeyboardMarkup(rows)


def _escape_html(s: str) -> str:
    if not s:
        return ""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _build_topic_view_message(chat_id: int) -> str:
    ts = _get_topic_settings(chat_id)
    if ts.get("topic_mode") == "custom":
        prompt = ts.get("custom_prompt") or "(none set)"
        safe = _escape_html(prompt[:200]) + ("…" if len(prompt) > 200 else "")
        return (
            f"📊 <b>Current Topic Configuration</b>\n{_SEP}\n"
            "Mode: <b>Custom Prompt</b>\n"
            f"Prompt: <i>{safe}</i>"
        )
    topic = _escape_html(ts.get("topic") or "(none selected)")
    return (
        f"📊 <b>Current Topic Configuration</b>\n{_SEP}\n"
        "Mode: <b>Popular Topic</b>\n"
        f"Selected: <b>{topic}</b>"
    )


# ── Keyboards (wizard + legacy menu) ─────────────────────────────────────────
GENRES = [
    "Mystery", "Horror", "Space", "Ancient Civilizations", "Conspiracies",
    "Psychology", "Science Mysteries", "Hidden History", "Wealth & Power", "Future & Technology",
    "True Crime", "Nature", "Philosophy", "Art & Culture", "Sports", "Health & Wellness",
    "Unexplained Phenomena", "Lost Treasures", "Famous Disappearances", "Curses & Legends",
]
VISUAL_STYLES = [
    "Dark Cinematic", "Bright Vivid", "Foggy Mystery", "High Energy", "Epic Historical", "Colorful",
    "Noir", "Vintage Film", "Minimalist", "Surreal", "Documentary Style", "Cinematic B-Roll",
    "Neon Cyberpunk", "Natural Light", "Moody Shadows", "Golden Hour",
]
NARRATION_STYLES = [
    "Dramatic", "Calm Deep", "High Energy", "Mysterious", "Documentary",
    "Whisper", "Storyteller", "News Anchor", "Conversational", "Epic Trailer",
    "Suspenseful", "Warm & Friendly", "Authoritative", "Intimate",
]
DURATIONS = ["20", "30", "40", "50"]
ASPECTS = [("9:16", "Shorts"), ("16:9", "YouTube"), ("1:1", "Instagram")]

def main_menu_keyboard():
    """Legacy: full menu. Console uses _console_home_keyboard() for /start."""
    return _console_home_keyboard()

def genre_keyboard():
    row = []
    k = []
    for i, g in enumerate(GENRES):
        row.append(InlineKeyboardButton(g, callback_data=f"genre_{i}"))
        if len(row) == 2:
            k.append(row)
            row = []
    if row:
        k.append(row)
    k.append([InlineKeyboardButton("◀️ Back", callback_data="panel_home")])
    return InlineKeyboardMarkup(k)

def visual_keyboard():
    k = [[InlineKeyboardButton(s, callback_data=f"vstyle_{s.replace(' ', '_').lower()}")] for s in VISUAL_STYLES]
    k.append([InlineKeyboardButton("◀️ Back", callback_data="menu_generate")])
    return InlineKeyboardMarkup(k)

def narration_keyboard():
    k = [[InlineKeyboardButton(s, callback_data=f"nstyle_{s.replace(' ', '_').lower()}")] for s in NARRATION_STYLES]
    k.append([InlineKeyboardButton("◀️ Back", callback_data="genre_back")])
    return InlineKeyboardMarkup(k)

def duration_keyboard():
    k = [[InlineKeyboardButton(f"{d} sec", callback_data=f"duration_{d}")] for d in DURATIONS]
    k.append([InlineKeyboardButton("◀️ Back", callback_data="nstyle_back")])
    return InlineKeyboardMarkup(k)

def aspect_keyboard():
    k = [[InlineKeyboardButton(f"{label}", callback_data=f"aspect_{val}")] for val, label in [("9x16", "9:16 (Shorts)"), ("16x9", "16:9 (YouTube)"), ("1x1", "1:1 (Instagram)")]]
    k.append([InlineKeyboardButton("◀️ Back", callback_data="aspect_back")])
    return InlineKeyboardMarkup(k)

def confirm_video_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Generate Video", callback_data="action_confirm_video")],
        [
            InlineKeyboardButton("✏️ Change", callback_data="menu_generate"),
            InlineKeyboardButton("❌ Cancel", callback_data="panel_home")],
    ])

def automation_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Run production cycle", callback_data="action_run_cycle")],
        [
            InlineKeyboardButton("⏸ Pause", callback_data="action_pause"),
            InlineKeyboardButton("▶️ Resume", callback_data="action_resume")],
        [InlineKeyboardButton("🔍 Diagnostics", callback_data="action_diagnostics")],
        [InlineKeyboardButton("🏠 Main dashboard", callback_data="panel_home")],
    ])

# ── Handlers ───────────────────────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text replies: Edit Metadata (Title|Description|Hashtags) or Custom Topic prompt."""
    if not update.message or not update.message.text:
        return
    if not _owner_only(update):
        return
    chat_id = update.effective_chat.id
    state = _get_state(chat_id)
    text = update.message.text.strip()

    # Custom topic prompt
    if state.get("pending_custom_topic"):
        _set_topic_settings(chat_id, {"topic_mode": "custom", "topic": None, "custom_prompt": text})
        _set_state(chat_id, {})
        safe = _escape_html(text[:150]) + ("…" if len(text) > 150 else "")
        await update.message.reply_text(
            f"✅ <b>Custom topic saved</b>\n{_SEP}\n"
            f"Prompt: <i>{safe}</i>\n\n"
            "It will be used for script generation when you tap <b>Generate Video</b>.",
            reply_markup=_topic_main_keyboard(),
            parse_mode="HTML",
        )
        return

    job_id = state.get("pending_edit_job_id")
    if not job_id:
        return
    parts = [p.strip() if p.strip() != "-" else None for p in text.split("|", 2)]
    title = parts[0] if len(parts) > 0 else None
    description = parts[1] if len(parts) > 1 else None
    hashtags = parts[2] if len(parts) > 2 else None
    if not any((title, description, hashtags)):
        await update.message.reply_text("Send: Title | Description | Hashtags (use - to skip).")
        return
    body = {"job_id": job_id}
    if title is not None:
        body["title"] = title
    if description is not None:
        body["description"] = description
    if hashtags is not None:
        body["hashtags"] = hashtags
    res = _api_patch("/commands/update-job-metadata", body)
    _set_state(chat_id, {})
    if res.get("status") == "ok":
        await update.message.reply_text(f"✅ Metadata updated for job {job_id}. Use <b>Approve & Publish</b> on the review message.", parse_mode="HTML")
    else:
        await update.message.reply_text(f"❌ {res.get('detail', res)}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_only(update):
        await update.message.reply_text(_unauthorized_message(update), parse_mode="HTML")
        return
    await update.message.reply_text(
        "🏭 <b>KLIPORA AI MEDIA FACTORY</b>\n"
        f"{_SEP}\n"
        "Your autonomous video factory at a tap.\n\n"
        "📊 <b>System Status</b> — Health, queues, next run\n"
        "🎬 <b>Video Factory</b> — Create shorts (5 scenes, 9:16)\n"
        "🧪 <b>Experiment Lab</b> — Active experiments\n"
        "📡 <b>Opportunity Radar</b> — Pending opportunities\n"
        "💰 <b>Finance Dashboard</b> — Budget & revenue\n"
        "⚙ <b>Automation Control</b> — Workflows & run cycle\n"
        "🎨 <b>Visual Styles</b> — Preset look & feel\n"
        "🛠 <b>Settings</b> — Limits & config",
        reply_markup=_console_home_keyboard(),
        parse_mode="HTML",
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_only(update):
        return
    text, kb = _build_status_panel()
    await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def cmd_videos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_only(update):
        return
    text, kb = _build_videos_panel()
    await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def cmd_experiments(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_only(update):
        return
    text, kb = _build_experiments_panel()
    await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def cmd_opportunities(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_only(update):
        return
    text, kb = _build_opportunities_panel()
    await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def cmd_finance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_only(update):
        return
    text, kb = _build_finance_panel()
    await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def cmd_automation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_only(update):
        return
    text, kb = _build_automation_panel()
    await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def cmd_topic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _owner_only(update):
        return
    await update.message.reply_text(
        f"🧠 <b>Topic / Genre</b>\n{_SEP}\n"
        "Choose a content category or enter a custom prompt.\n"
        "Used by the script generator when you create videos.",
        reply_markup=_topic_main_keyboard(),
        parse_mode="HTML",
    )


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not _owner_only(update):
        await query.edit_message_text(_unauthorized_message(update), parse_mode="HTML")
        return

    chat_id = update.effective_chat.id
    data = query.data

    if data == "menu_main" or data == "panel_home":
        _set_state(chat_id, {})
        await query.edit_message_text(
            "🏭 <b>KLIPORA AI MEDIA FACTORY</b>\n"
            f"{_SEP}\n"
            "📊 System Status · 🎬 Video Factory · 🧪 Experiment Lab\n"
            "📡 Opportunity Radar · 💰 Finance · ⚙ Automation · 🎨 Visual Styles · 🛠 Settings",
            reply_markup=_console_home_keyboard(),
            parse_mode="HTML",
        )
        return

    # ── Mission Console: live panel navigation (edit in place) ───────────────
    if data == "panel_status":
        text, kb = _build_status_panel()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return
    if data == "panel_videos":
        text, kb = _build_videos_panel()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return
    if data == "panel_experiments":
        text, kb = _build_experiments_panel()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return
    if data == "panel_opportunities":
        text, kb = _build_opportunities_panel()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return
    if data == "panel_finance":
        text, kb = _build_finance_panel()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return
    if data == "panel_automation":
        text, kb = _build_automation_panel()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return
    if data == "panel_visual_styles":
        text, kb = _build_visual_styles_panel()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return
    if data.startswith("visual_preset_"):
        key = data.replace("visual_preset_", "", 1)
        _set_system_visual_style(key)
        await query.answer(f"Visual style set to {key}")
        text, kb = _build_visual_styles_panel()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return
    if data == "refresh_status":
        text, kb = _build_status_panel()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return
    if data == "refresh_experiments":
        text, kb = _build_experiments_panel()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return
    if data == "refresh_opportunities":
        text, kb = _build_opportunities_panel()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return
    if data == "refresh_finance":
        text, kb = _build_finance_panel()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return
    if data == "refresh_automation":
        text, kb = _build_automation_panel()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return

    if data == "menu_generate":
        _set_state(chat_id, {"step": "genre"})
        await query.edit_message_text(
            "🎬 <b>Generate Video</b>\n" + _SEP + "\n<b>Step 1 of 5</b> — Pick a genre:",
            reply_markup=genre_keyboard(),
            parse_mode="HTML",
        )
        return

    if data.startswith("genre_"):
        if data == "genre_back":
            _set_state(chat_id, {"step": "genre"})
            await query.edit_message_text("🎬 <b>Step 1 of 5</b> — Genre:", reply_markup=genre_keyboard(), parse_mode="HTML")
            return
        idx = int(data.split("_")[1])
        state = _get_state(chat_id)
        state["genre"] = GENRES[idx]
        state["step"] = "visual"
        _set_state(chat_id, state)
        await query.edit_message_text(
            f"🎬 <b>Generate Video</b>\n{_SEP}\n<b>Step 2 of 5</b> — Visual style\nGenre: <b>{state['genre']}</b>",
            reply_markup=visual_keyboard(),
            parse_mode="HTML",
        )
        return

    if data.startswith("vstyle_"):
        if data == "vstyle_back":
            state = _get_state(chat_id)
            state["step"] = "genre"
            _set_state(chat_id, state)
            await query.edit_message_text("🎬 <b>Step 1 of 5</b> — Genre:", reply_markup=genre_keyboard(), parse_mode="HTML")
            return
        v = data.replace("vstyle_", "").replace("_", " ").title()
        state = _get_state(chat_id)
        state["visual_style"] = v
        state["step"] = "narration"
        _set_state(chat_id, state)
        await query.edit_message_text(
            "🎬 <b>Step 3 of 5</b> — Narration style:",
            reply_markup=narration_keyboard(),
            parse_mode="HTML",
        )
        return

    if data.startswith("nstyle_"):
        if data == "nstyle_back":
            state = _get_state(chat_id)
            state["step"] = "visual"
            _set_state(chat_id, state)
            await query.edit_message_text("🎬 <b>Step 2 of 5</b> — Visual style:", reply_markup=visual_keyboard(), parse_mode="HTML")
            return
        n = data.replace("nstyle_", "").replace("_", " ").title()
        state = _get_state(chat_id)
        state["narration_style"] = n
        state["step"] = "duration"
        _set_state(chat_id, state)
        await query.edit_message_text(
            "🎬 <b>Step 4 of 5</b> — Duration (seconds):",
            reply_markup=duration_keyboard(),
            parse_mode="HTML",
        )
        return

    if data == "aspect_back":
        state = _get_state(chat_id)
        state["step"] = "duration"
        _set_state(chat_id, state)
        await query.edit_message_text("🎬 <b>Step 4 of 5</b> — Duration:", reply_markup=duration_keyboard(), parse_mode="HTML")
        return

    if data.startswith("duration_"):
        if data == "duration_back":
            state = _get_state(chat_id)
            state["step"] = "narration"
            _set_state(chat_id, state)
            await query.edit_message_text("🎬 <b>Step 3 of 5</b> — Narration:", reply_markup=narration_keyboard(), parse_mode="HTML")
            return
        d = data.replace("duration_", "")
        state = _get_state(chat_id)
        state["duration"] = d
        state["step"] = "aspect"
        _set_state(chat_id, state)
        await query.edit_message_text(
            "🎬 <b>Step 5 of 5</b> — Aspect ratio:",
            reply_markup=aspect_keyboard(),
            parse_mode="HTML",
        )
        return

    if data.startswith("aspect_") and data != "aspect_back":
        state = _get_state(chat_id)
        state["aspect_ratio"] = data.replace("aspect_", "").replace("x", ":")
        state["step"] = "confirm"
        _set_state(chat_id, state)
        g, v, n, dur, asp = state.get("genre"), state.get("visual_style"), state.get("narration_style"), state.get("duration"), state.get("aspect_ratio")
        ts = _get_topic_settings(chat_id)
        if ts.get("topic_mode") == "custom" and ts.get("custom_prompt"):
            topic_line = f"📌 Topic · <b>Custom</b>: <i>{_escape_html(ts['custom_prompt'][:60])}{'…' if len(ts.get('custom_prompt', '')) > 60 else ''}</i>\n"
        elif ts.get("topic_mode") == "popular" and ts.get("topic"):
            topic_line = f"📌 Topic · <b>{_escape_html(ts['topic'])}</b>\n"
        else:
            topic_line = f"📌 Topic · <b>{g} short</b> (from genre)\n"
        await query.edit_message_text(
            f"🎬 <b>Confirm</b>\n{_SEP}\n"
            f"{topic_line}"
            f"🎭 Genre · <b>{g}</b>\n"
            f"🎨 Visual · <b>{v}</b>\n"
            f"🎙 Narration · <b>{n}</b>\n"
            f"⏱ Duration · <b>{dur}s</b> · <b>{asp}</b>\n\n"
            "Tap <b>Generate Video</b> to start the pipeline.",
            reply_markup=confirm_video_keyboard(),
            parse_mode="HTML",
        )
        return

    if data == "action_confirm_video":
        await query.edit_message_text(
            "⏳ <b>Starting pipeline…</b>\n\nChecking Mission Control and triggering script generation.",
            reply_markup=None,
            parse_mode="HTML",
        )
        state = _get_state(chat_id)
        ts = _get_topic_settings(chat_id)
        if ts.get("topic_mode") == "custom" and ts.get("custom_prompt"):
            topic = ts["custom_prompt"]
        elif ts.get("topic_mode") == "popular" and ts.get("topic"):
            topic = ts["topic"]
        else:
            topic = state.get("topic") or f"{state.get('genre', 'General')} short"
        visual_style = _get_system_visual_style() or state.get("visual_style")
        body = {
            "topic": topic,
            "genre": state.get("genre"),
            "visual_style": visual_style,
            "narration_style": state.get("narration_style"),
            "duration": state.get("duration"),
            "aspect_ratio": state.get("aspect_ratio"),
            "chat_id": str(chat_id),
        }
        if os.environ.get("PROJECT_ID"):
            body["project_id"] = os.environ.get("PROJECT_ID")
        result = _api_post("/commands/generate-video", body)
        _set_state(chat_id, {})
        if isinstance(result, dict) and result.get("accepted") is False and result.get("reason") == "topic_already_used":
            msg = result.get("message") or "This topic was already used."
            topic_val = result.get("topic") or ""
            await query.edit_message_text(
                f"⚠️ <b>Topic already used</b>\n\n{_escape_html(msg)}\n\nTopic: <code>{_escape_html(topic_val)}</code>\n\nSend again with <code>force_reuse=true</code> if you want to reuse it.",
                reply_markup=main_menu_keyboard(),
                parse_mode="HTML",
            )
            return
        if result.get("job"):
            job_id = result["job"].get("id", "N/A")
            await query.edit_message_text(
                "✅ <b>Pipeline started</b>\n"
                f"{_SEP}\n"
                f"Job <code>{job_id}</code>\n\n"
                "You’ll get a <b>Script Ready</b> message when the script is done. Then (in 12:00–20:00 UAE, max 2/day) video runs; you’ll get a review message to Approve or Discard.",
                reply_markup=main_menu_keyboard(),
                parse_mode="HTML",
            )
        elif not result and not MISSION_CONTROL_URL:
            await query.edit_message_text(
                "❌ Mission Control URL not set. Add MISSION_CONTROL_URL to KEY=value.env and restart the bot.",
                reply_markup=main_menu_keyboard(),
                parse_mode="HTML",
            )
        elif not result:
            mc = check_mission_control_connectivity(_api_get, MISSION_CONTROL_URL)
            diag = _format_mission_control_for_ui(mc)
            await query.edit_message_text(
                "❌ <b>Mission Control API offline</b>\n\n"
                "Check Railway deployment or MISSION_CONTROL_URL.\n\n"
                f"{diag}",
                reply_markup=main_menu_keyboard(),
                parse_mode="HTML",
            )
        else:
            detail = result.get("detail") or result
            if isinstance(detail, dict):
                detail = detail.get("message", str(detail))
            detail = str(detail)
            if "n8n" in detail.lower() or "webhook" in detail.lower() or "503" in detail:
                detail += "\n\nTip: In n8n, set the Groq API key in WF-GEN → Generate Script node (see N8N_GROQ_KEY.md)."
            await query.edit_message_text(f"❌ Failed: {detail}", reply_markup=main_menu_keyboard(), parse_mode="HTML")
        return

    if data == "menu_status":
        text, kb = _build_status_panel()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return
    if data == "menu_revenue" or data == "menu_finance":
        text, kb = _build_finance_panel()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return
    if data == "menu_experiments":
        text, kb = _build_experiments_panel()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return
    if data == "menu_opportunities":
        text, kb = _build_opportunities_panel()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return
    if data == "menu_automation":
        text, kb = _build_automation_panel()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return

    # ── Topic / Genre menu ───────────────────────────────────────────────────
    if data == "panel_topic":
        await query.edit_message_text(
            f"🧠 <b>Topic / Genre</b>\n{_SEP}\n"
            "Choose a content category or enter a custom prompt.\n"
            "Used by the script generator when you create videos.",
            reply_markup=_topic_main_keyboard(),
            parse_mode="HTML",
        )
        return
    if data == "panel_topic_custom":
        _set_state(chat_id, {})  # clear any pending_custom_topic when entering menu
        await query.edit_message_text(
            f"✨ <b>Custom Topic</b>\n{_SEP}\n"
            "Enter your own topic prompt for script generation.\n\n"
            "Tap <b>Custom Prompt</b> below, then type your prompt in chat.",
            reply_markup=_topic_custom_keyboard(),
            parse_mode="HTML",
        )
        return
    if data == "action_custom_prompt":
        _set_state(chat_id, {"pending_custom_topic": True})
        await query.edit_message_text(
            f"✏️ <b>Custom Prompt</b>\n{_SEP}\n"
            "Enter your custom topic prompt in the next message.\n\n"
            "Example:\n<i>Explain the most mysterious unsolved cases in history</i>\n\n"
            "Or: <i>Top 5 mysterious disappearances</i>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Cancel", callback_data="panel_topic_custom")]]),
            parse_mode="HTML",
        )
        return
    if data == "panel_topic_popular":
        ts = _get_topic_settings(chat_id)
        selected = ts.get("topic")
        # Resolve selected key from label (topic stores display label)
        selected_key = None
        if selected:
            for label, key in POPULAR_TOPICS:
                if label == selected:
                    selected_key = key
                    break
        await query.edit_message_text(
            f"🔥 <b>Popular Topics</b>\n{_SEP}\n"
            "Select a topic. It will be used for script generation.\n"
            "✅ = currently selected.",
            reply_markup=_topic_popular_keyboard(selected_key),
            parse_mode="HTML",
        )
        return
    if data.startswith("topic_popular_"):
        key = data.replace("topic_popular_", "", 1)
        label = None
        for l, k in POPULAR_TOPICS:
            if k == key:
                label = l
                break
        if label is not None:
            _set_topic_settings(chat_id, {"topic_mode": "popular", "topic": label, "custom_prompt": None})
        await query.edit_message_text(
            f"🔥 <b>Popular Topics</b>\n{_SEP}\n"
            "Select a topic. ✅ = currently selected.",
            reply_markup=_topic_popular_keyboard(key),
            parse_mode="HTML",
        )
        return
    if data == "panel_topic_view":
        msg = _build_topic_view_message(chat_id)
        await query.edit_message_text(
            msg,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data="panel_topic")]]),
            parse_mode="HTML",
        )
        return

    if data == "action_run_cycle":
        body = {}
        if os.environ.get("PROJECT_ID"):
            body["project_id"] = os.environ.get("PROJECT_ID")
        result = _api_post("/commands/run-cycle", body if body else None)
        status = result.get("status", "?")
        await query.edit_message_text(
            f"▶️ Run cycle: {status}. Check Telegram for session start/stop alerts.",
            reply_markup=_automation_panel_keyboard(),
            parse_mode="HTML",
        )
        return

    if data == "action_pause":
        _api_post("/commands/pause")
        text, kb = _build_status_panel()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return

    if data == "action_resume":
        _api_post("/commands/resume")
        text, kb = _build_status_panel()
        await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        return

    if data == "action_diagnostics":
        summary = run_system_diagnostics(_api_get, MISSION_CONTROL_URL, redis)
        d = _api_get("/commands/system-diagnostics") if summary.get("mission_control", {}).get("reachable") else None
        if not d or d.get("_error"):
            msg = _format_full_diagnostics_for_ui(summary, None) + "\n\nWhen API is up, system diagnostics (queues, stalled jobs) will appear here."
        else:
            msg = f"🔍 <b>Diagnostics</b>\n{_SEP}\n\n" + _format_full_diagnostics_for_ui(summary, d)
        await query.edit_message_text(msg, reply_markup=_status_panel_keyboard(), parse_mode="HTML")
        return

    if data == "action_approve_opp":
        o = _api_get("/opportunities")
        opps = o.get("opportunities", []) if o else []
        if not opps:
            await query.answer("No pending opportunities.", show_alert=True)
            return
        opp_id = opps[0].get("id")
        if not opp_id:
            await query.answer("Opportunity has no id.", show_alert=True)
            return
        res = _api_post("/commands/approve-opportunity", {"opportunity_id": opp_id})
        if res.get("status") == "ok":
            await query.answer("Opportunity approved.")
            text, kb = _build_opportunities_panel()
            await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        else:
            await query.answer(res.get("detail", "Failed"), show_alert=True)
        return

    if data == "action_reject_opp":
        o = _api_get("/opportunities")
        opps = o.get("opportunities", []) if o else []
        if not opps:
            await query.answer("No pending opportunities.", show_alert=True)
            return
        opp_id = opps[0].get("id")
        if not opp_id:
            await query.answer("Opportunity has no id.", show_alert=True)
            return
        res = _api_post("/commands/reject-opportunity", {"opportunity_id": opp_id, "reason": "Rejected via Telegram"})
        if res.get("status") == "ok":
            await query.answer("Opportunity rejected.")
            text, kb = _build_opportunities_panel()
            await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        else:
            await query.answer(res.get("detail", "Failed"), show_alert=True)
        return

    if data.startswith("approve_opp_"):
        opp_id = data.replace("approve_opp_", "", 1)
        res = _api_post("/commands/approve-opportunity", {"opportunity_id": opp_id})
        if res.get("status") == "ok":
            await query.answer("Opportunity approved.")
            text, kb = _build_opportunities_panel()
            await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        else:
            await query.answer(res.get("detail", "Failed"), show_alert=True)
        return

    if data.startswith("reject_opp_"):
        opp_id = data.replace("reject_opp_", "", 1)
        res = _api_post("/commands/reject-opportunity", {"opportunity_id": opp_id, "reason": "Rejected via Telegram"})
        if res.get("status") == "ok":
            await query.answer("Opportunity rejected.")
            text, kb = _build_opportunities_panel()
            await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        else:
            await query.answer(res.get("detail", "Failed"), show_alert=True)
        return

    if data.startswith("terminate_exp_"):
        try:
            idx = int(data.replace("terminate_exp_", "", 1))
        except ValueError:
            await query.answer("Invalid experiment.", show_alert=True)
            return
        res = _api_post("/commands/terminate-experiment", {"index": idx})
        if res.get("status") == "ok":
            await query.answer("Experiment terminated.")
            text, kb = _build_experiments_panel()
            await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
        else:
            await query.answer(res.get("detail", "Failed"), show_alert=True)
        return

    if data == "menu_settings":
        await query.edit_message_text(
            "🔧 <b>SETTINGS</b>\n"
            f"{_SEP}\n"
            "🎬 Videos · 2/day (12:00 & 20:00 UAE)\n"
            "🧪 Experiments · max 3\n"
            "💰 Budget · $440 cap",
            reply_markup=_console_home_keyboard(),
            parse_mode="HTML",
        )
        return

    # ── Human-in-the-loop: video review approval actions ───────────────────
    if data.startswith("approve_publish_"):
        job_id = data.replace("approve_publish_", "", 1)
        body = {"job_id": job_id}
        if os.environ.get("PROJECT_ID"):
            body["project_id"] = os.environ.get("PROJECT_ID")
        res = _api_post("/commands/approve-publish", body)
        if res.get("status") == "ok":
            await query.edit_message_text(f"✅ <b>Queued for publish</b>\nJob: {job_id}\nPlatform pipeline will upload when ready.", parse_mode="HTML")
        else:
            await query.edit_message_text(f"❌ {res.get('detail', res)}", parse_mode="HTML")
        return

    if data.startswith("regenerate_"):
        job_id = data.replace("regenerate_", "", 1)
        body = {"job_id": job_id}
        if os.environ.get("PROJECT_ID"):
            body["project_id"] = os.environ.get("PROJECT_ID")
        res = _api_post("/commands/regenerate-job", body)
        if res.get("status") == "ok":
            await query.edit_message_text(f"🔄 <b>Regenerating</b>\nJob: {job_id}\nNew script/visuals queued.", parse_mode="HTML")
        else:
            await query.edit_message_text(f"❌ {res.get('detail', res)}", parse_mode="HTML")
        return

    if data.startswith("discard_"):
        job_id = data.replace("discard_", "", 1)
        body = {"job_id": job_id}
        if os.environ.get("PROJECT_ID"):
            body["project_id"] = os.environ.get("PROJECT_ID")
        res = _api_post("/commands/discard-job", body)
        if res.get("status") == "ok":
            await query.edit_message_text(f"❌ <b>Discarded</b>\nJob: {job_id}\nTopic marked used.", parse_mode="HTML")
        else:
            await query.edit_message_text(f"❌ {res.get('detail', res)}", parse_mode="HTML")
        return

    if data.startswith("edit_meta_"):
        job_id = data.replace("edit_meta_", "", 1)
        _set_state(chat_id, {"pending_edit_job_id": job_id})
        await query.edit_message_text(
            f"✏️ <b>Edit metadata</b>\nJob: {job_id}\n\n"
            "Reply with one line in this format:\n<code>Title | Description | Hashtags</code>\n\n"
            "Use a dash - for any part you don't want to change.",
            parse_mode="HTML",
        )
        return

    await query.edit_message_text("Select an option:", reply_markup=main_menu_keyboard(), parse_mode="HTML")


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        print("Set TELEGRAM_BOT_TOKEN and optionally MISSION_CONTROL_URL, OWNER_TELEGRAM_ID (or TELEGRAM_CHAT_ID)")
        return
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Start Mission Control health monitor in the background (non-blocking).
    try:
        threading.Thread(target=mission_control_health_loop, daemon=True).start()
    except Exception:
        # Health monitoring is best-effort; bot should still start if this fails.
        pass

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("videos", cmd_videos))
    app.add_handler(CommandHandler("experiments", cmd_experiments))
    app.add_handler(CommandHandler("opportunities", cmd_opportunities))
    app.add_handler(CommandHandler("finance", cmd_finance))
    app.add_handler(CommandHandler("automation", cmd_automation))
    app.add_handler(CommandHandler("topic", cmd_topic))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
