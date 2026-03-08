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
import typing as t

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

try:
    from Infrastructure.redis_client import get_redis_client
    from Command_Center.system_guardian import SystemGuardian
    from Command_Center.workflow_controller import WorkflowController
    from Command_Center.pipeline_monitor import PipelineMonitor
    from Command_Center.company_brain import CompanyBrain
    from Command_Center.event_bus import get_event_bus

    redis = get_redis_client()
    guardian = SystemGuardian(redis=redis)
    controller = WorkflowController(redis=redis)
    monitor = PipelineMonitor()
    brain = CompanyBrain(redis=redis)
    event_bus = get_event_bus()
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


# ── System health and production endpoints ───────────────────────────────


@app.get("/health/system")
def system_health() -> dict:
    """
    High-level system health snapshot for the dashboard.
    """
    flags = guardian.check_system_flags()
    queues = guardian.check_queues()
    failures = guardian.check_n8n_failures()

    # Simple status derivation for now.
    status = "HEALTHY"
    if flags.get("paused"):
        status = "PAUSED"
    if sum(failures.values()) > guardian.MAX_FAILED_EXECUTIONS_WINDOW:
        status = "DEGRADED"

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


@app.post("/commands/run-cycle")
def run_orchestration_cycle() -> dict:
    """
    Run one KLIPORA orchestration cycle: CEO plan → CTO health check → Operations production.
    Call this from a cron job or n8n schedule to drive the company loop in the cloud.
    """
    from Agents.ceo_agent import CEOAgent
    from Agents.cto_agent import CTOAgent
    from Agents.operations_agent import OperationsAgent

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


