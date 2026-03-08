"""
KLIPORA Mission Control Dashboard — Backend API

FastAPI service exposing a read/write API for the Mission Control dashboard.
The React/Next.js frontend (to be built later) will consume these endpoints.

Data sources:
- Upstash Redis (system flags, queues, finance, experiments, opportunities)
- n8n (workflow health and execution errors)

Control endpoints:
- Pause / resume system
- Trigger video generation
- Trigger experiments and diagnostics
"""

from __future__ import annotations

import datetime as _dt
import os
import typing as t

import requests as _requests

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Defer infra imports so any missing module or config is caught and reported via /health (Railway: set env vars)
_config_ok = False
_config_error = ""
redis = None
guardian = None
controller = None
monitor = None
brain = None
event_bus = None
opportunity_engine = None

try:
    from Infrastructure.redis_client import get_redis_client
    from Command_Center.system_guardian import SystemGuardian
    from Command_Center.workflow_controller import WorkflowController
    from Command_Center.pipeline_monitor import PipelineMonitor
    from Command_Center.company_brain import CompanyBrain
    from Command_Center.event_bus import get_event_bus
    from Agents.opportunity_engine import OpportunityEngine

    redis = get_redis_client()
    guardian = SystemGuardian(redis=redis)
    controller = WorkflowController(redis=redis)
    monitor = PipelineMonitor()
    brain = CompanyBrain(redis=redis)
    event_bus = get_event_bus()
    opportunity_engine = OpportunityEngine(redis=redis, event_bus=event_bus)
    _config_ok = True
except BaseException as e:
    _config_error = f"{type(e).__name__}: {e}"


app = FastAPI(title="KLIPORA Mission Control API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later to specific dashboard domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _require_config():
    if not _config_ok:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Service not configured",
                "message": _config_error,
                "fix": "In Railway → Variables, set UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN, N8N_URL (and optionally N8N_API_KEY), then redeploy.",
            },
        )


@app.middleware("http")
async def require_config_middleware(request, call_next):
    if request.url.path in ("/", "/health"):
        return await call_next(request)
    if not _config_ok:
        return JSONResponse(
            status_code=503,
            content={
                "error": "Service not configured",
                "message": _config_error,
                "fix": "In Railway → Variables, set UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN, N8N_URL, then redeploy.",
            },
        )
    return await call_next(request)


def _iso_now() -> str:
    return _dt.datetime.utcnow().isoformat() + "Z"


def _send_telegram(text: str) -> bool:
    """Send a message to the owner via Telegram. Uses TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars. No-op if unset."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    try:
        r = _requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=5,
        )
        return r.ok
    except Exception:
        return False


def _send_telegram_review(job_id: str, job: dict) -> bool:
    """Send human-in-the-loop review message with preview and Approve/Regenerate/Edit/Discard buttons."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    topic = job.get("topic", "—")
    genre = job.get("genre", "—")
    visual = job.get("visual_style") or job.get("meta", {}).get("visual_style", "—")
    narration = job.get("narration_style") or job.get("meta", {}).get("narration_style", "—")
    duration = job.get("duration") or job.get("meta", {}).get("duration", "—")
    aspect = job.get("aspect_ratio") or job.get("meta", {}).get("aspect_ratio", "—")
    video_url = job.get("video_url") or job.get("preview_url", "")
    script_summary = job.get("script_summary", "")[:200] if job.get("script_summary") else "—"
    quality = job.get("quality_score")
    score_line = f"\n<b>Quality score:</b> {quality}/100\n⚠️ Score &lt; 60 — consider Regenerate.\n" if quality is not None and quality < 60 else (f"\n<b>Quality score:</b> {quality}/100\n" if quality is not None else "")

    caption = (
        "🎬 <b>KLIPORA VIDEO READY FOR REVIEW</b>\n\n"
        f"<b>Topic:</b> {topic}\n"
        f"<b>Genre:</b> {genre}\n"
        f"<b>Visual style:</b> {visual}\n"
        f"<b>Narration:</b> {narration}\n"
        f"<b>Duration:</b> {duration} sec\n"
        f"<b>Aspect ratio:</b> {aspect}\n"
        f"{score_line}"
        f"<b>Script summary:</b> {script_summary}\n\n"
    )
    if video_url:
        caption += f"<b>Preview:</b> {video_url}\n\n"

    # Telegram callback_data max 64 bytes; UUID (36) + prefix fits
    reply_markup = {
        "inline_keyboard": [
            [{"text": "✅ Approve & Publish", "callback_data": f"approve_publish_{job_id}"}],
            [{"text": "🔄 Regenerate", "callback_data": f"regenerate_{job_id}"}, {"text": "✏️ Edit Metadata", "callback_data": f"edit_meta_{job_id}"}],
            [{"text": "❌ Discard", "callback_data": f"discard_{job_id}"}],
        ]
    }
    try:
        r = _requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": caption, "parse_mode": "HTML", "reply_markup": reply_markup},
            timeout=5,
        )
        return r.ok
    except Exception:
        return False


# ── Request models ────────────────────────────────────────────────────────


class GenerateVideoRequest(BaseModel):
    topic: str
    genre: t.Optional[str] = None
    visual_style: t.Optional[str] = None
    narration_style: t.Optional[str] = None
    duration: t.Optional[str] = None
    aspect_ratio: t.Optional[str] = None
    chat_id: t.Optional[str] = None


class RunExperimentRequest(BaseModel):
    experiment_id: str


class JobIdRequest(BaseModel):
    job_id: str


class UpdateMetadataRequest(BaseModel):
    job_id: str
    title: t.Optional[str] = None
    description: t.Optional[str] = None
    hashtags: t.Optional[str] = None


# ── System health and production endpoints ───────────────────────────────


@app.get("/health/system")
def system_health() -> dict:
    """
    High-level system health snapshot for the dashboard.
    Never raises: returns DEGRADED and minimal payload if a check fails.
    """
    try:
        flags = guardian.check_system_flags()
        queues = guardian.check_queues()
        failures = guardian.check_n8n_failures()
    except Exception as e:
        return {
            "timestamp": _iso_now(),
            "status": "DEGRADED",
            "message": f"Health check error: {type(e).__name__}",
            "flags": {"paused": False, "daily_count": 0, "videos_per_day": 2, "date": _dt.datetime.utcnow().strftime("%Y-%m-%d")},
            "queues": {"script_queue": 0, "render_queue": 0, "publish_queue": 0, "failed_queue": 0},
            "n8n_failures": {},
        }
    failures = failures if isinstance(failures, dict) else {}
    status = "HEALTHY"
    if flags.get("paused"):
        status = "PAUSED"
    try:
        if sum(failures.values()) > guardian.MAX_FAILED_EXECUTIONS_WINDOW:
            status = "DEGRADED"
    except Exception:
        pass
    return {
        "timestamp": _iso_now(),
        "status": status,
        "flags": flags,
        "queues": queues,
        "n8n_failures": failures,
    }


@app.get("/production")
def production_summary() -> dict:
    """
    Daily production view suitable for the Production Monitor widget.
    """
    flags = guardian.check_system_flags()
    queues = guardian.check_queues()

    return {
        "date": flags["date"],
        "videos_generated_today": flags["daily_count"],
        "target_videos_per_day": flags["videos_per_day"],
        "queues": queues,
    }


@app.get("/automation")
def automation_status() -> dict:
    """
    Overview of key n8n workflows.
    """
    try:
        workflows = monitor.list_workflows()
    except Exception as exc:  # n8n down or API error
        raise HTTPException(status_code=503, detail=f"n8n unavailable: {exc}")

    # Normalise into a small summary for the dashboard.
    items = []
    if isinstance(workflows, dict) and "data" in workflows:
        wf_list = workflows["data"]
    else:
        wf_list = workflows or []

    for wf in wf_list:
        items.append(
            {
                "id": wf.get("id"),
                "name": wf.get("name"),
                "active": wf.get("active"),
            }
        )

    return {"workflows": items}


# ── Finance and budget views (keys to be populated by Finance Agent) ─────


@app.get("/finance/revenue")
def revenue_summary() -> dict:
    """
    Revenue dashboard.

    Expected Redis keys (can be zero/absent early on):
    - finance:revenue:today
    - finance:revenue:week
    - finance:revenue:month
    - finance:revenue:source:<name>
    """
    def _to_float(value: t.Optional[str]) -> float:
        try:
            return float(value or 0)
        except ValueError:
            return 0.0

    today = _to_float(redis.get("finance:revenue:today"))
    week = _to_float(redis.get("finance:revenue:week"))
    month = _to_float(redis.get("finance:revenue:month"))

    sources = {
        "youtube_ads": _to_float(redis.get("finance:revenue:source:youtube_ads")),
        "affiliate": _to_float(redis.get("finance:revenue:source:affiliate")),
        "digital_products": _to_float(
            redis.get("finance:revenue:source:digital_products")
        ),
        "music_service": _to_float(
            redis.get("finance:revenue:source:music_service")
        ),
    }

    return {
        "today": today,
        "week": week,
        "month": month,
        "sources": sources,
    }


@app.get("/finance/budget")
def budget_summary() -> dict:
    """
    Budget and spend view.

    Expected Redis keys:
    - finance:capital_initial (default 440)
    - finance:spent_total
    - finance:remaining
    - finance:spend:category:<name>
    """
    def _to_float(value: t.Optional[str]) -> float:
        try:
            return float(value or 0)
        except ValueError:
            return 0.0

    capital = _to_float(redis.get("finance:capital_initial") or "440")
    spent = _to_float(redis.get("finance:spent_total"))
    remaining = _to_float(redis.get("finance:remaining") or str(capital - spent))

    categories = {
        "api_usage": _to_float(redis.get("finance:spend:category:api_usage")),
        "cloud_hosting": _to_float(
            redis.get("finance:spend:category:cloud_hosting")
        ),
        "tools": _to_float(redis.get("finance:spend:category:tools")),
        "advertising": _to_float(
            redis.get("finance:spend:category:advertising")
        ),
    }

    return {
        "capital_initial": capital,
        "spent": spent,
        "remaining": remaining,
        "categories": categories,
    }


# ── Experiments and opportunities (Experiment Lab / Opportunity Radar) ───


@app.get("/experiments")
def experiments_view() -> dict:
    """
    View of active experiments.

    Expected Redis key:
    - experiments:active  -> JSON array of experiment objects
    """
    experiments = redis.get_json("experiments:active") or []
    return {"experiments": experiments}


@app.get("/opportunities")
def opportunities_view() -> dict:
    """
    View of pending opportunities.

    Expected Redis key:
    - opportunities:pending -> JSON array
    """
    opportunities = redis.get_json("opportunities:pending") or []
    return {"opportunities": opportunities}


class OpportunityActionRequest(BaseModel):
    opportunity_id: str


class RejectOpportunityRequest(BaseModel):
    opportunity_id: str
    reason: str = ""


@app.post("/commands/approve-opportunity")
def approve_opportunity_cmd(req: OpportunityActionRequest) -> dict:
    """Move first matching opportunity from pending to approved."""
    if not opportunity_engine:
        raise HTTPException(status_code=503, detail="Opportunity engine not loaded")
    result = opportunity_engine.approve_opportunity(req.opportunity_id)
    if not result:
        raise HTTPException(status_code=404, detail="Opportunity not found or already processed")
    return {"status": "ok", "opportunity": result}


@app.post("/commands/reject-opportunity")
def reject_opportunity_cmd(req: RejectOpportunityRequest) -> dict:
    """Move opportunity from pending to rejected."""
    if not opportunity_engine:
        raise HTTPException(status_code=503, detail="Opportunity engine not loaded")
    result = opportunity_engine.reject_opportunity(req.opportunity_id, req.reason or "Rejected via dashboard")
    if not result:
        raise HTTPException(status_code=404, detail="Opportunity not found or already processed")
    return {"status": "ok", "opportunity": result}


# ── Notifications / Alerts ------------------------------------------------


@app.get("/notifications")
def notifications_view(limit: int = 50) -> dict:
    """
    Simple alert log.

    Expected Redis key:
    - alerts:log -> list (RPUSHed messages)
    """
    items = redis.lrange("alerts:log", -limit, -1)
    return {"alerts": items}


@app.get("/events")
def events_view(limit: int = 100, event_type: t.Optional[str] = None) -> dict:
    """
    Activity timeline for the dashboard.
    """
    events = event_bus.get_events(limit=limit, event_type=event_type)
    return {"events": events}


# ── Owner command panel endpoints ----------------------------------------


@app.post("/commands/pause")
def pause_system() -> dict:
    redis.set("system:paused", "1")
    redis.rpush("alerts:log", f"{_iso_now()} — System paused via dashboard")
    event_bus.publish(
        "SYSTEM_ALERT",
        {"message": "System paused via dashboard", "source": "dashboard"},
        category="alerts",
    )
    return {"status": "paused"}


@app.post("/commands/resume")
def resume_system() -> dict:
    redis.delete("system:paused")
    redis.rpush("alerts:log", f"{_iso_now()} — System resumed via dashboard")
    event_bus.publish(
        "SYSTEM_ALERT",
        {"message": "System resumed via dashboard", "source": "dashboard"},
        category="alerts",
    )
    return {"status": "resumed"}


@app.post("/commands/generate-video")
def generate_video(req: GenerateVideoRequest) -> dict:
    """
    Manually trigger a video generation job.
    """
    if guardian.check_system_flags().get("paused"):
        raise HTTPException(
            status_code=400,
            detail="System is paused; cannot generate video.",
        )

    job = controller.start_generation_job(
        topic=req.topic,
        genre=req.genre,
        visual_style=req.visual_style,
        narration_style=req.narration_style,
        duration=req.duration,
        aspect_ratio=req.aspect_ratio,
        chat_id=req.chat_id,
    )
    redis.rpush(
        "alerts:log",
        f"{_iso_now()} — Manual video job created: {job['id']} ({req.topic})",
    )
    event_bus.publish(
        "VIDEO_JOB_CREATED",
        {"job_id": job["id"], "topic": req.topic, "source": "dashboard"},
        category="videos",
    )
    return {"job": job}


@app.post("/commands/run-experiment")
def run_experiment(req: RunExperimentRequest) -> dict:
    """
    Signal the system to run an experiment.

    The Operations / CEO / Opportunity agents will watch this queue and
    perform the actual orchestration.
    """
    redis.rpush("commands:run_experiment", req.experiment_id)
    redis.rpush(
        "alerts:log",
        f"{_iso_now()} — Experiment requested: {req.experiment_id}",
    )
    event_bus.publish(
        "EXPERIMENT_STARTED",
        {"experiment_id": req.experiment_id, "source": "dashboard"},
        category="experiments",
    )
    return {"status": "queued", "experiment_id": req.experiment_id}


def _get_pending_job(job_id: str) -> t.Optional[dict]:
    """Load pending_approve:{job_id} from Redis. Handles JSON or URL-encoded JSON."""
    import urllib.parse
    raw = redis.get(f"pending_approve:{job_id}")
    if not raw:
        return None
    s = raw if isinstance(raw, str) else (raw.decode("utf-8") if hasattr(raw, "decode") else str(raw))
    for val in (s, urllib.parse.unquote(s)):
        try:
            return json.loads(val)
        except Exception:
            continue
    return None


def _set_pending_job(job_id: str, job: dict) -> None:
    """Write pending_approve:{job_id}. Optional: set TTL 24h (86400) to auto-expire."""
    redis.set_json(f"pending_approve:{job_id}", job)


def _del_pending_job(job_id: str) -> None:
    redis.delete(f"pending_approve:{job_id}")


@app.post("/internal/daily-report")
def send_daily_report() -> dict:
    """
    Send the KLIPORA daily report to Telegram. Call from cron or n8n each morning.
    """
    prod = guardian.check_system_flags()
    rev = redis.get("finance:revenue:today") or "0"
    try:
        rev_today = float(rev)
    except ValueError:
        rev_today = 0.0
    month_raw = redis.get("finance:revenue:month") or "0"
    try:
        rev_month = float(month_raw)
    except ValueError:
        rev_month = 0.0
    exps = redis.get_json("experiments:active") or []
    top = exps[0] if exps else None
    opps = redis.get_json("opportunities:pending") or []
    msg = (
        "📊 <b>KLIPORA DAILY REPORT</b>\n\n"
        f"Videos Published: {prod.get('daily_count', 0)}\n"
        f"Revenue: ${rev_today:.2f}\n"
        f"Expenses: —\n\n"
        f"<b>Top Experiment</b>\n{top.get('title', '—') if top else '—'}\n\n"
        f"<b>New Opportunities</b>\n"
    )
    for o in opps[:3]:
        msg += f"• {o.get('title', '?')}\n"
    if not opps:
        msg += "—\n"
    _send_telegram(msg)
    return {"sent": True}


@app.post("/internal/notify-preview")
def notify_preview(req: JobIdRequest) -> dict:
    """
    Human-in-the-loop: send preview to Telegram with Approve/Regenerate/Edit/Discard.
    Call this from n8n WF-ASSEMBLE after storing the job in Redis pending_approve:{job_id}.
    Recommended: set TTL 86400 (24h) on pending_approve:{job_id} in n8n so unreviewed jobs expire.
    """
    job = _get_pending_job(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="pending_approve:{job_id} not found")
    job.setdefault("job_id", req.job_id)
    ok = _send_telegram_review(req.job_id, job)
    return {"sent": ok, "job_id": req.job_id}


def _call_railway_render(job: dict) -> bool:
    """Call Railway Render service to assemble clips + voiceover and send to Telegram. Returns True if accepted."""
    render_url = (os.environ.get("RAILWAY_RENDER_URL") or "https://klipora-render-service-production.up.railway.app").rstrip("/")
    clip_urls = job.get("clip_urls") or []
    voice_url = job.get("voice_url")
    if not clip_urls or not voice_url:
        return False
    chat_id = job.get("chatId") or os.environ.get("TELEGRAM_CHAT_ID")
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not chat_id or not bot_token:
        return False
    payload = {
        "clips": clip_urls,
        "voiceover": voice_url,
        "chatId": str(chat_id),
        "botToken": bot_token,
        "jobId": job.get("job_id"),
        "title": job.get("topic") or job.get("title", ""),
        "genre": job.get("genre", ""),
    }
    try:
        r = _requests.post(f"{render_url}/render", json=payload, timeout=30)
        return r.ok
    except Exception:
        return False


@app.post("/commands/approve-publish")
def approve_publish(req: JobIdRequest) -> dict:
    """Approve video: call Railway Render (if job has clips), push to publish_queue, remove from pending review."""
    job = _get_pending_job(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or already processed")
    render_called = _call_railway_render(job)
    redis.rpush("publish_queue", req.job_id)
    controller.update_job_status(req.job_id, "publishing")
    _del_pending_job(req.job_id)
    event_bus.publish("VIDEO_APPROVED", {"job_id": req.job_id}, category="videos")
    if render_called:
        _send_telegram(f"✅ <b>VIDEO PUBLISHED</b>\nJob: {req.job_id}\nFFmpeg assembling; video will arrive in Telegram shortly.")
    else:
        _send_telegram(f"✅ <b>VIDEO QUEUED FOR PUBLISH</b>\nJob: {req.job_id}\nPlatform pipeline will upload when ready.")
    return {"status": "ok", "job_id": req.job_id, "render_called": render_called}


@app.post("/commands/regenerate-job")
def regenerate_job(req: JobIdRequest) -> dict:
    """Send job back to WF-GEN (same topic, new script/visuals). Removes from pending review."""
    job = _get_pending_job(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or already processed")
    topic = job.get("topic") or "General"
    meta = job.get("meta") or {}
    controller.start_generation_job(
        topic=topic,
        genre=job.get("genre"),
        visual_style=job.get("visual_style") or meta.get("visual_style"),
        narration_style=job.get("narration_style") or meta.get("narration_style"),
        duration=str(job.get("duration", "")) or meta.get("duration"),
        aspect_ratio=job.get("aspect_ratio") or meta.get("aspect_ratio"),
        job_id=None,
    )
    _del_pending_job(req.job_id)
    event_bus.publish("VIDEO_REGENERATE", {"job_id": req.job_id, "topic": topic}, category="videos")
    _send_telegram(f"🔄 <b>Regenerating</b>\nTopic: {topic}\nNew job queued for script generation.")
    return {"status": "ok", "job_id": req.job_id}


@app.post("/commands/discard-job")
def discard_job(req: JobIdRequest) -> dict:
    """Discard video: add topic to used_topics, remove from pending. Prevents topic reuse."""
    job = _get_pending_job(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or already processed")
    topic = job.get("topic") or ""
    if topic:
        redis.sadd("used_topics", topic)
    _del_pending_job(req.job_id)
    redis.rpush("failed_queue", req.job_id)
    event_bus.publish("VIDEO_DISCARDED", {"job_id": req.job_id, "topic": topic}, category="videos")
    _send_telegram(f"❌ <b>Discarded</b>\nJob: {req.job_id}\nTopic marked used.")
    return {"status": "ok", "job_id": req.job_id}


@app.patch("/commands/update-job-metadata")
def update_job_metadata(req: UpdateMetadataRequest) -> dict:
    """Update title/description/hashtags for a pending job; then owner can Approve & Publish."""
    job = _get_pending_job(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or already processed")
    if req.title is not None:
        job["title"] = req.title
    if req.description is not None:
        job["description"] = req.description
    if req.hashtags is not None:
        job["hashtags"] = req.hashtags
    _set_pending_job(req.job_id, job)
    return {"status": "ok", "job_id": req.job_id}


@app.post("/commands/run-cycle")
def run_orchestration_cycle() -> dict:
    """
    Run one KLIPORA orchestration cycle: CEO plan → CTO health check → Operations production.
    Sends Telegram alerts for session start and stop when TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set.
    """
    from Agents.ceo_agent import CEOAgent
    from Agents.cto_agent import CTOAgent
    from Agents.operations_agent import OperationsAgent

    now = _iso_now()
    _send_telegram(
        f"🟢 <b>KLIPORA session started</b>\n"
        f"Time: {now}\n"
        f"Cycle: CEO plan → CTO health → Operations production."
    )

    ceo = CEOAgent(redis=redis, event_bus=event_bus)
    cto = CTOAgent(redis=redis, event_bus=event_bus)
    ops = OperationsAgent(redis=redis, event_bus=event_bus)

    ceo.align_daily_production_limit()
    health_summary = cto.run_health_check()
    production_result = ops.run_production_cycle()

    event_bus.publish(
        "ORCHESTRATION_CYCLE_COMPLETE",
        {"health": health_summary, "production": production_result},
        category="alerts",
    )

    status = production_result.get("status", "ok")
    jobs = production_result.get("created_jobs", [])
    summary = f"Status: {status}. Jobs created: {len(jobs)}."
    _send_telegram(
        f"🔴 <b>KLIPORA session finished</b>\n"
        f"Time: {_iso_now()}\n"
        f"{summary}\n"
        f"Paused: {health_summary.get('flags', {}).get('paused', False)}"
    )

    return {
        "status": "ok",
        "health": health_summary,
        "production": production_result,
    }


@app.get("/commands/system-diagnostics")
def system_diagnostics() -> dict:
    """
    Read-only diagnostics snapshot (does NOT apply policies or mutate state).
    """
    queues = guardian.check_queues()
    flags = guardian.check_system_flags()
    failures = guardian.check_n8n_failures()
    stalled = guardian.detect_stalled_jobs()

    return {
        "timestamp": _iso_now(),
        "queues": queues,
        "flags": flags,
        "n8n_failures": failures,
        "stalled_jobs": stalled,
    }


@app.get("/health")
def health() -> dict:
    """Always returns 200 so Railway keeps the service up; shows config status."""
    return {
        "status": "ok" if _config_ok else "config_missing",
        "config_ok": _config_ok,
        "message": None if _config_ok else _config_error,
        "fix": None if _config_ok else "Set UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN, N8N_URL in Railway Variables, then redeploy.",
    }


@app.get("/")
def root() -> dict:
    return {
        "service": "KLIPORA Mission Control API",
        "version": "0.1.0",
        "timestamp": _iso_now(),
        "config_ok": _config_ok,
    }


