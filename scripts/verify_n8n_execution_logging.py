#!/usr/bin/env python3
"""
Read-only verification: fetch recent workflow executions from n8n API and report
execution id, workflow id/name, status, start/stop time, duration.
Verifies that the instance is storing execution history for KLIPORA workflows.
Does not modify any workflow or the ensure_n8n_workflows_active script.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ENV_PATH = os.path.join(ROOT, ".env")
TARGET_NAMES = ("WF-TREND", "WF-GEN", "WF-VIDEO", "WF-ASSEMBLE")


def _load_env() -> None:
    if not os.path.isfile(_ENV_PATH):
        return
    with open(_ENV_PATH, "r", encoding="utf-8") as f:
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


def _parse_ts(ts) -> str:
    if ts is None:
        return "—"
    if isinstance(ts, (int, float)):
        try:
            return datetime.utcfromtimestamp(ts / 1000.0).strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception:
            return str(ts)
    return str(ts)


def _duration_ms(started, stopped) -> int | None:
    """Return duration in ms if both timestamps are parseable."""
    def to_ms(ts):
        if ts is None:
            return None
        if isinstance(ts, (int, float)):
            return int(ts) if ts > 1e12 else int(ts * 1000)
        if isinstance(ts, str):
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return int(dt.timestamp() * 1000)
            except Exception:
                return None
        return None
    s, p = to_ms(started), to_ms(stopped)
    if s is not None and p is not None and p >= s:
        return p - s
    return None


def main() -> int:
    _load_env()
    n8n_url = os.environ.get("N8N_URL", "").rstrip("/")
    api_key = os.environ.get("N8N_API_KEY")
    if not n8n_url or not api_key:
        print("Set N8N_URL and N8N_API_KEY in .env", file=sys.stderr)
        return 1
    try:
        import requests
    except ImportError:
        print("pip install requests", file=sys.stderr)
        return 1

    headers = {
        "X-N8N-API-KEY": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    # 1) Get workflow id -> name map for target workflows
    r_wf = requests.get(f"{n8n_url}/api/v1/workflows", headers=headers, timeout=15)
    r_wf.raise_for_status()
    wf_data = r_wf.json()
    wf_list = wf_data.get("data", wf_data) if isinstance(wf_data, dict) else (wf_data if isinstance(wf_data, list) else [])
    target_ids = set()
    id_to_name = {}
    for wf in wf_list:
        name = (wf.get("name") or "")
        for tag in TARGET_NAMES:
            if tag in name:
                target_ids.add(wf.get("id"))
                id_to_name[wf.get("id")] = name
                break

    # 2) Get recent executions (try common query params)
    # n8n public API: GET /api/v1/executions?limit=50 or with workflowId
    params = {"limit": 100}
    r_ex = requests.get(f"{n8n_url}/api/v1/executions", headers=headers, params=params, timeout=15)
    if r_ex.status_code == 404:
        # Some instances use /rest/executions
        r_ex = requests.get(f"{n8n_url}/rest/executions", headers=headers, params=params, timeout=15)
    r_ex.raise_for_status()
    ex_data = r_ex.json()
    executions = ex_data.get("data", ex_data) if isinstance(ex_data, dict) else (ex_data if isinstance(ex_data, list) else [])

    # 3) Filter to target workflows and build report
    target_executions = []
    for ex in executions:
        wf_id = ex.get("workflowId")
        if wf_id in target_ids:
            target_executions.append(ex)
        # Some APIs return workflowData.name
        wf_name = (ex.get("workflowData") or {}).get("name") or ""
        if not wf_id and wf_name:
            for tag in TARGET_NAMES:
                if tag in wf_name:
                    target_executions.append(ex)
                    break

    # Sort by start time descending (newest first)
    def start_key(e):
        s = e.get("startedAt") or 0
        return s if isinstance(s, (int, float)) else 0
    target_executions.sort(key=start_key, reverse=True)

    print("=" * 90)
    print("KLIPORA execution logging verification (read-only)")
    print("=" * 90)
    print(f"\nTarget workflow IDs: {target_ids}")
    print(f"Total executions returned by API: {len(executions)}")
    print(f"Executions for target workflows (WF-TREND, WF-GEN, WF-VIDEO, WF-ASSEMBLE): {len(target_executions)}\n")

    if not target_executions:
        print("No execution records found for the four core workflows.")
        print("\nPossible causes:")
        print("  • Workflows have not been run yet after activation.")
        print("  • Instance execution saving is disabled or limited.")
        print("  • Environment variables to check on the n8n (Railway) deployment:")
        print("    - EXECUTIONS_DATA_SAVE_ON_SUCCESS  (e.g. 'all' to save successful runs)")
        print("    - EXECUTIONS_DATA_SAVE_ON_ERROR    (e.g. 'all' to save failed runs)")
        print("    - EXECUTIONS_DATA_SAVE_MANUAL_EXECUTIONS  (e.g. true for manual runs)")
        print("  • Database (SQLite/Postgres) must be writable; check instance logs for DB errors.")
        print("=" * 90)
        return 0

    print("Recent executions (newest first):\n")
    for ex in target_executions[:50]:
        ex_id = ex.get("id")
        wf_id = ex.get("workflowId")
        wf_name = id_to_name.get(wf_id) or (ex.get("workflowData") or {}).get("name") or "—"
        status = ex.get("status") or ex.get("finished")  # success, error, running, etc.
        if status is True:
            status = "success"
        elif status is False:
            status = "error"
        if isinstance(ex.get("finished"), bool):
            if ex.get("finished") is True and status not in ("error", "crashed"):
                status = "success"
            elif ex.get("finished") is False:
                status = "running"
        started = ex.get("startedAt")
        stopped = ex.get("stoppedAt")
        duration_ms = ex.get("executionTime") if ex.get("executionTime") is not None else _duration_ms(started, stopped)
        duration_str = f"{duration_ms} ms" if duration_ms is not None else "—"
        print(f"  id: {ex_id}")
        print(f"  workflowId: {wf_id}  |  workflow: {wf_name[:50]}")
        print(f"  status: {status}  |  started: {_parse_ts(started)}  |  stopped: {_parse_ts(stopped)}  |  duration: {duration_str}")
        print()

    # Per-workflow execution count
    by_wf = {}
    for ex in target_executions:
        wf_id = ex.get("workflowId")
        by_wf[wf_id] = by_wf.get(wf_id, 0) + 1
    print("\nExecutions per workflow (in this batch):")
    for wf_id, count in sorted(by_wf.items(), key=lambda x: -x[1]):
        print(f"  {id_to_name.get(wf_id, wf_id)}: {count}")

    print("\n" + "=" * 90)
    print("Conclusion: Execution records exist; instance is storing execution history for these workflows.")
    print("=" * 90)
    return 0


if __name__ == "__main__":
    sys.exit(main())
