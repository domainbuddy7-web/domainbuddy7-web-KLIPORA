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

def _load_env_file() -> None:
    """Load KEY=value lines from KEY=value.env or .env into os.environ (no dotenv needed)."""
    token_candidates = []
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
                        if key:
                            os.environ[key] = value
                        if value and _looks_like_telegram_token(value):
                            token_candidates.append(value)
                    for part in line.replace("|", " ").split():
                        part = part.strip("'\"").rstrip(",")
                        if _looks_like_telegram_token(part):
                            token_candidates.append(part)
        except Exception:
            pass
        break
    if token_candidates and not _looks_like_telegram_token(os.environ.get("TELEGRAM_BOT_TOKEN") or ""):
        os.environ["TELEGRAM_BOT_TOKEN"] = token_candidates[-1]


_load_env_file()

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

# ── Config ─────────────────────────────────────────────────────────────────
_raw_url = (
    os.environ.get("MISSION_CONTROL_URL")
    or os.environ.get("mission_control_url")
    or ""
).strip().rstrip("/")
# Default if nothing set or empty (user can override in KEY=value.env)
MISSION_CONTROL_URL = _raw_url or "https://domainbuddy7-web-klipora-production.up.railway.app"
TELEGRAM_BOT_TOKEN = (
    os.environ.get("TELEGRAM_BOT_TOKEN")
    or os.environ.get("BOT_TOKEN")
    or os.environ.get("telegram_bot_token")
)
OWNER_TELEGRAM_ID = os.environ.get("OWNER_TELEGRAM_ID") or os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("telegram_chat_id")

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

def _api_get(path: str) -> dict:
    """GET Mission Control; returns JSON dict or dict with _error, _code for status panel."""
    if not MISSION_CONTROL_URL:
        return {}
    try:
        r = requests.get(f"{MISSION_CONTROL_URL}{path}", timeout=15)
        if r.ok:
            return r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        return {"_error": f"HTTP {r.status_code}", "_code": r.status_code}
    except requests.exceptions.Timeout:
        return {"_error": "timeout", "_code": 0}
    except requests.exceptions.ConnectionError:
        return {"_error": "connection failed", "_code": 0}
    except Exception as e:
        return {"_error": "error", "_code": 0}

def _api_post(path: str, json_body: dict | None = None) -> dict:
    if not MISSION_CONTROL_URL:
        return {}
    try:
        r = requests.post(f"{MISSION_CONTROL_URL}{path}", json=json_body or {}, timeout=15)
        return r.json() if r.ok else {}
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
                "🤖 <b>KLIPORA SYSTEM STATUS</b>\n\n⚠️ System health check failed"
                + reason
                + ", but the API root is reachable (config_ok: true). Try Refresh again or check Railway logs."
                + url_hint,
                _status_panel_keyboard(),
            )
        return (
            "🤖 <b>KLIPORA SYSTEM STATUS</b>\n\n⚠️ Could not reach Mission Control API"
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
    msg = (
        "🤖 <b>KLIPORA SYSTEM STATUS</b>\n\n"
        "<b>Core Systems</b>\n"
        f"Redis: {'✅ Online' if redis_ok else '❌ Offline'}\n"
        f"n8n: {'✅ Running' if n8n_ok else '⚠️ Issues'}\n"
        "Render Engine: —\n"
        "WaveSpeed API: —\n\n"
        "<b>Production</b>\n"
        f"Videos Today: {flags.get('daily_count', 0)} / {flags.get('videos_per_day', 2)}\n"
        f"Next Run: {_next_run_uae()}\n\n"
        "<b>Queues</b>\n"
        f"Script: {queues.get('script_queue', 0)} | Render: {queues.get('render_queue', 0)} | Publish: {queues.get('publish_queue', 0)}\n\n"
    )
    if bud:
        msg += f"<b>Finance</b>\nBudget Remaining: ${bud.get('remaining', 0):.2f}\nSpent Today: —\n"
    if rev:
        msg += f"Revenue Today: ${rev.get('today', 0):.2f}\n"
    return msg.strip(), _status_panel_keyboard()


def _build_videos_panel() -> tuple[str, InlineKeyboardMarkup]:
    """Video Factory Panel: /videos."""
    prod = _api_get("/production")
    if not prod:
        return (
            "🎬 <b>KLIPORA VIDEO FACTORY</b>\n\n⚠️ Could not reach Mission Control.",
            _videos_panel_keyboard(),
        )
    q = prod.get("queues", {})
    pending = q.get("publish_queue", 0) or 0
    msg = (
        "🎬 <b>KLIPORA VIDEO FACTORY</b>\n\n"
        "<b>Today's Production</b>\n"
        f"Videos: {prod.get('videos_generated_today', 0)} / {prod.get('target_videos_per_day', 2)}\n"
        f"Awaiting approval: {pending}\n\n"
        f"<b>Next Scheduled Run</b>\n{_next_run_uae()}"
    )
    return msg, _videos_panel_keyboard()


def _build_experiments_panel() -> tuple[str, InlineKeyboardMarkup]:
    """Experiment Lab Panel: /experiments."""
    e = _api_get("/experiments")
    exps = e.get("experiments", []) if e else []
    if not exps:
        msg = "🧪 <b>KLIPORA EXPERIMENT LAB</b>\n\nNo active experiments."
    else:
        lines = []
        for i, x in enumerate(exps[:5], 1):
            title = x.get("title", x.get("id", "?"))
            roi = x.get("roi", x.get("status", "—"))
            lines.append(f"{i}️⃣ {title}\nROI: {roi}")
        msg = "🧪 <b>KLIPORA EXPERIMENT LAB</b>\n\n<b>Active Experiments</b>\n\n" + "\n\n".join(lines)
    return msg, _experiments_panel_keyboard()


def _build_opportunities_panel() -> tuple[str, InlineKeyboardMarkup]:
    """Opportunity Radar Panel: /opportunities."""
    o = _api_get("/opportunities")
    opps = o.get("opportunities", []) if o else []
    if not opps:
        msg = "📡 <b>KLIPORA OPPORTUNITY RADAR</b>\n\nNo pending opportunities."
    else:
        opp = opps[0]
        msg = (
            "🚀 <b>NEW OPPORTUNITY DETECTED</b>\n\n"
            f"{opp.get('title', '?')}\n\n"
            f"<b>Demand Signal</b>\n{opp.get('demand', opp.get('score', '—'))}\n\n"
            f"<b>Estimated Cost</b>\n${opp.get('estimated_cost', opp.get('cost', '?'))}\n\n"
            f"<b>Estimated Revenue</b>\n{opp.get('estimated_revenue', '—')}"
        )
    return msg, _opportunities_panel_keyboard()


def _build_finance_panel() -> tuple[str, InlineKeyboardMarkup]:
    """Finance Dashboard: /finance."""
    bud = _api_get("/finance/budget")
    rev = _api_get("/finance/revenue")
    if not bud:
        return "💰 <b>KLIPORA FINANCE</b>\n\n⚠️ No budget data.", _finance_panel_keyboard()
    msg = (
        "💰 <b>KLIPORA FINANCE</b>\n\n"
        f"<b>Initial Capital</b>\n${bud.get('capital_initial', 440):.2f}\n\n"
        f"<b>Spent</b>\n${bud.get('spent', 0):.2f}\n\n"
        f"<b>Remaining</b>\n${bud.get('remaining', 0):.2f}\n\n"
        f"<b>Revenue Today</b>\n${rev.get('today', 0):.2f if rev else 0:.2f}\n\n"
        f"<b>Revenue Month</b>\n${rev.get('month', 0):.2f if rev else 0:.2f}"
    )
    return msg, _finance_panel_keyboard()


def _build_automation_panel() -> tuple[str, InlineKeyboardMarkup]:
    """Automation Control Panel: /automation."""
    a = _api_get("/automation")
    wfs = a.get("workflows", []) if a else []
    if not wfs:
        return (
            "⚙️ <b>AUTOMATION STATUS</b>\n\n⚠️ Could not fetch workflows (n8n?).",
            _automation_panel_keyboard(),
        )
    lines = []
    for w in wfs[:10]:
        name = (w.get("name") or w.get("id") or "?").replace("WF-", "")
        state = "Running" if w.get("active") else "Idle"
        lines.append(f"{name}\n{state}")
    msg = "⚙️ <b>AUTOMATION STATUS</b>\n\n" + "\n\n".join(lines)
    return msg, _automation_panel_keyboard()


# ── Mission Console: panel keyboards (Refresh + actions) ─────────────────────
def _console_home_keyboard() -> InlineKeyboardMarkup:
    """Main /start: navigation to all panels."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 System Status", callback_data="panel_status")],
        [InlineKeyboardButton("🎬 Video Factory", callback_data="panel_videos")],
        [InlineKeyboardButton("🧪 Experiment Lab", callback_data="panel_experiments")],
        [InlineKeyboardButton("📡 Opportunity Radar", callback_data="panel_opportunities")],
        [InlineKeyboardButton("💰 Finance Dashboard", callback_data="panel_finance")],
        [InlineKeyboardButton("⚙️ Automation Control", callback_data="panel_automation")],
        [InlineKeyboardButton("🔧 Settings", callback_data="menu_settings")],
    ])


def _status_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_status")],
        [InlineKeyboardButton("⏸ Pause System", callback_data="action_pause")],
        [InlineKeyboardButton("🔍 Diagnostics", callback_data="action_diagnostics")],
        [InlineKeyboardButton("◀️ Command Center", callback_data="panel_home")],
    ])


def _videos_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Generate Video", callback_data="menu_generate")],
        [InlineKeyboardButton("📋 Review Pending", callback_data="panel_videos")],
        [InlineKeyboardButton("◀️ Command Center", callback_data="panel_home")],
    ])


def _experiments_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_experiments")],
        [InlineKeyboardButton("◀️ Command Center", callback_data="panel_home")],
    ])


def _opportunities_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Approve Experiment", callback_data="action_approve_opp")],
        [InlineKeyboardButton("❌ Reject", callback_data="action_reject_opp")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_opportunities")],
        [InlineKeyboardButton("◀️ Command Center", callback_data="panel_home")],
    ])


def _finance_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_finance")],
        [
            InlineKeyboardButton("📉 View Expenses", callback_data="menu_finance"),
            InlineKeyboardButton("📈 Revenue Streams", callback_data="menu_finance"),
        ],
        [InlineKeyboardButton("◀️ Command Center", callback_data="panel_home")],
    ])


def _automation_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Run cycle", callback_data="action_run_cycle")],
        [InlineKeyboardButton("🔍 Diagnostics", callback_data="action_diagnostics")],
        [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_automation")],
        [InlineKeyboardButton("◀️ Command Center", callback_data="panel_home")],
    ])


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
    k.append([InlineKeyboardButton("◀️ Back", callback_data="menu_main")])
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
        [InlineKeyboardButton("✅ Generate", callback_data="action_confirm_video")],
        [InlineKeyboardButton("✏️ Change settings", callback_data="menu_generate")],
        [InlineKeyboardButton("❌ Cancel", callback_data="menu_main")],
    ])

def automation_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Run production cycle", callback_data="action_run_cycle")],
        [InlineKeyboardButton("⏸ Pause system", callback_data="action_pause")],
        [InlineKeyboardButton("▶️ Resume system", callback_data="action_resume")],
        [InlineKeyboardButton("🔍 Diagnostics", callback_data="action_diagnostics")],
        [InlineKeyboardButton("◀️ Back", callback_data="menu_main")],
    ])

# ── Handlers ───────────────────────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text replies (e.g. Edit Metadata: Title | Description | Hashtags)."""
    if not update.message or not update.message.text:
        return
    if not _owner_only(update):
        return
    chat_id = update.effective_chat.id
    state = _get_state(chat_id)
    job_id = state.get("pending_edit_job_id")
    if not job_id:
        return
    text = update.message.text.strip()
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
        "🛸 <b>KLIPORA COMMAND CENTER</b>\n\n"
        "Live control terminal for your AI company. Use commands or tap a panel below.",
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
            "🛸 <b>KLIPORA COMMAND CENTER</b>\n\nLive control terminal. Tap a panel:",
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
        await query.edit_message_text("🎬 <b>Generate Video</b>\n\nSelect genre:", reply_markup=genre_keyboard(), parse_mode="HTML")
        return

    if data.startswith("genre_"):
        if data == "genre_back":
            _set_state(chat_id, {"step": "genre"})
            await query.edit_message_text("Select genre:", reply_markup=genre_keyboard(), parse_mode="HTML")
            return
        idx = int(data.split("_")[1])
        state = _get_state(chat_id)
        state["genre"] = GENRES[idx]
        state["step"] = "visual"
        _set_state(chat_id, state)
        await query.edit_message_text(f"Visual style for <b>{state['genre']}</b>:", reply_markup=visual_keyboard(), parse_mode="HTML")
        return

    if data.startswith("vstyle_"):
        if data == "vstyle_back":
            state = _get_state(chat_id)
            state["step"] = "genre"
            _set_state(chat_id, state)
            await query.edit_message_text("Select genre:", reply_markup=genre_keyboard(), parse_mode="HTML")
            return
        v = data.replace("vstyle_", "").replace("_", " ").title()
        state = _get_state(chat_id)
        state["visual_style"] = v
        state["step"] = "narration"
        _set_state(chat_id, state)
        await query.edit_message_text("Narration style:", reply_markup=narration_keyboard(), parse_mode="HTML")
        return

    if data.startswith("nstyle_"):
        if data == "nstyle_back":
            state = _get_state(chat_id)
            state["step"] = "visual"
            _set_state(chat_id, state)
            await query.edit_message_text("Visual style:", reply_markup=visual_keyboard(), parse_mode="HTML")
            return
        n = data.replace("nstyle_", "").replace("_", " ").title()
        state = _get_state(chat_id)
        state["narration_style"] = n
        state["step"] = "duration"
        _set_state(chat_id, state)
        await query.edit_message_text("Duration:", reply_markup=duration_keyboard(), parse_mode="HTML")
        return

    if data == "aspect_back":
        state = _get_state(chat_id)
        state["step"] = "duration"
        _set_state(chat_id, state)
        await query.edit_message_text("Duration:", reply_markup=duration_keyboard(), parse_mode="HTML")
        return

    if data.startswith("duration_"):
        if data == "duration_back":
            state = _get_state(chat_id)
            state["step"] = "narration"
            _set_state(chat_id, state)
            await query.edit_message_text("Narration style:", reply_markup=narration_keyboard(), parse_mode="HTML")
            return
        d = data.replace("duration_", "")
        state = _get_state(chat_id)
        state["duration"] = d
        state["step"] = "aspect"
        _set_state(chat_id, state)
        await query.edit_message_text("Aspect ratio:", reply_markup=aspect_keyboard(), parse_mode="HTML")
        return

    if data.startswith("aspect_") and data != "aspect_back":
        state = _get_state(chat_id)
        state["aspect_ratio"] = data.replace("aspect_", "").replace("x", ":")
        state["step"] = "confirm"
        _set_state(chat_id, state)
        g, v, n, dur, asp = state.get("genre"), state.get("visual_style"), state.get("narration_style"), state.get("duration"), state.get("aspect_ratio")
        await query.edit_message_text(
            f"📋 <b>Confirm video</b>\n\n"
            f"Genre: {g}\nVisual: {v}\nNarration: {n}\nDuration: {dur}s\nAspect: {asp}\n\n"
            f"Estimated cost: ~$0.50–2 (API).",
            reply_markup=confirm_video_keyboard(),
            parse_mode="HTML",
        )
        return

    if data == "action_confirm_video":
        state = _get_state(chat_id)
        topic = state.get("topic") or f"{state.get('genre', 'General')} short"
        body = {
            "topic": topic,
            "genre": state.get("genre"),
            "visual_style": state.get("visual_style"),
            "narration_style": state.get("narration_style"),
            "duration": state.get("duration"),
            "aspect_ratio": state.get("aspect_ratio"),
            "chat_id": str(chat_id),
        }
        result = _api_post("/commands/generate-video", body)
        _set_state(chat_id, {})
        if result.get("job"):
            job_id = result["job"].get("id", "N/A")
            await query.edit_message_text(
                f"✅ <b>Video generation started</b>\n\n"
                f"Job ID: <code>{job_id}</code>\n"
                f"Genre: {state.get('genre')} · {state.get('visual_style')} · {state.get('narration_style')}\n\n"
                f"🔄 Pipeline is processing (script → video → assembly).\n"
                f"You'll get a <b>review message</b> in Telegram when the video is ready to Approve or Discard.",
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
            await query.edit_message_text(
                "❌ Could not reach Mission Control API. Check MISSION_CONTROL_URL in KEY=value.env and that the API is running.",
                reply_markup=main_menu_keyboard(),
                parse_mode="HTML",
            )
        else:
            detail = result.get("detail") or result
            if isinstance(detail, dict):
                detail = detail.get("message", str(detail))
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

    if data == "action_run_cycle":
        result = _api_post("/commands/run-cycle")
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
        d = _api_get("/commands/system-diagnostics")
        if not d:
            await query.edit_message_text("⚠️ Could not fetch diagnostics.", reply_markup=_status_panel_keyboard(), parse_mode="HTML")
            return
        q = d.get("queues", {})
        stalled = d.get("stalled_jobs", [])
        msg = (
            f"🔍 <b>Diagnostics</b>\n\n"
            f"Queues: script={q.get('script_queue',0)} render={q.get('render_queue',0)} "
            f"publish={q.get('publish_queue',0)} failed={q.get('failed_queue',0)}\n"
            f"Stalled jobs: {len(stalled)}"
        )
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

    if data == "menu_settings":
        await query.edit_message_text(
            "🔧 <b>Settings</b>\n\nProduction: 2 videos/day @ 12:00 & 20:00 UAE.\nMax 3 experiments. Budget $440.",
            reply_markup=_console_home_keyboard(),
            parse_mode="HTML",
        )
        return

    # ── Human-in-the-loop: video review approval actions ───────────────────
    if data.startswith("approve_publish_"):
        job_id = data.replace("approve_publish_", "", 1)
        res = _api_post("/commands/approve-publish", {"job_id": job_id})
        if res.get("status") == "ok":
            await query.edit_message_text(f"✅ <b>Queued for publish</b>\nJob: {job_id}\nPlatform pipeline will upload when ready.", parse_mode="HTML")
        else:
            await query.edit_message_text(f"❌ {res.get('detail', res)}", parse_mode="HTML")
        return

    if data.startswith("regenerate_"):
        job_id = data.replace("regenerate_", "", 1)
        res = _api_post("/commands/regenerate-job", {"job_id": job_id})
        if res.get("status") == "ok":
            await query.edit_message_text(f"🔄 <b>Regenerating</b>\nJob: {job_id}\nNew script/visuals queued.", parse_mode="HTML")
        else:
            await query.edit_message_text(f"❌ {res.get('detail', res)}", parse_mode="HTML")
        return

    if data.startswith("discard_"):
        job_id = data.replace("discard_", "", 1)
        res = _api_post("/commands/discard-job", {"job_id": job_id})
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
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("videos", cmd_videos))
    app.add_handler(CommandHandler("experiments", cmd_experiments))
    app.add_handler(CommandHandler("opportunities", cmd_opportunities))
    app.add_handler(CommandHandler("finance", cmd_finance))
    app.add_handler(CommandHandler("automation", cmd_automation))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
