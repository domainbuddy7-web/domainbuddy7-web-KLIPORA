#!/usr/bin/env python3
"""
Read-only verification: fetch KLIPORA workflow metadata from n8n API and report
id, name, active, node count, trigger nodes, connections, and execution settings.
Does not modify any workflow or the ensure_n8n_workflows_active script.
"""
from __future__ import annotations

import os
import sys

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

    # 1) List workflows
    r = requests.get(f"{n8n_url}/api/v1/workflows", headers=headers, timeout=15)
    r.raise_for_status()
    data = r.json()
    wf_list = data.get("data", data) if isinstance(data, dict) else (data if isinstance(data, list) else [])

    # 2) Find target workflows and fetch full detail for each
    targets = []
    for wf in wf_list:
        name = (wf.get("name") or "")
        for tag in TARGET_NAMES:
            if tag in name:
                targets.append((wf.get("id"), name))
                break

    if not targets:
        print("No target workflows (WF-TREND, WF-GEN, WF-VIDEO, WF-ASSEMBLE) found.")
        return 0

    print("=" * 80)
    print("KLIPORA workflow structure verification (read-only)")
    print("=" * 80)

    all_valid = True
    for wf_id, wf_name in targets:
        r2 = requests.get(f"{n8n_url}/api/v1/workflows/{wf_id}", headers=headers, timeout=15)
        r2.raise_for_status()
        full = r2.json()

        nodes = full.get("nodes") or []
        connections = full.get("connections") or {}
        settings = full.get("settings") or {}
        active = full.get("active", False)

        # Trigger-like types: Cron, Webhook, Telegram, etc.
        trigger_types = []
        disabled_trigger = False
        for n in nodes:
            t = (n.get("type") or "")
            name_node = n.get("name") or ""
            dis = n.get("disabled", False)
            if "trigger" in t.lower() or "cron" in t.lower() or "webhook" in t.lower() or "telegram" in t.lower():
                trigger_types.append(t)
                if dis:
                    disabled_trigger = True
            # Common trigger type patterns in n8n
            if t.startswith("n8n-nodes-base.") and (
                "Cron" in t or "Webhook" in t or "Trigger" in t or "Telegram" in t
            ):
                if t not in trigger_types:
                    trigger_types.append(t)
                if dis:
                    disabled_trigger = True

        has_connections = bool(connections)
        # connections structure: { "NodeName": { "main": [[ { "node": "Next", "type": "main", "index": 0 } ]] } }
        connection_count = sum(
            len(out.get("main", [[]])[0]) if out.get("main") else 0
            for out in connections.values()
        )

        # Execution logging (n8n often uses settings.saveExecutionProgress, settings.executionOrder, etc.)
        save_execution = settings.get("saveExecutionProgress")
        save_manual_executions = settings.get("saveManualExecutions")
        execution_order = settings.get("executionOrder", "v1")

        print(f"\n--- {wf_name} ---")
        print(f"  id:           {wf_id}")
        print(f"  active:       {active}")
        print(f"  nodes:        {len(nodes)}")
        print(f"  trigger types: {trigger_types or '(none detected)'}")
        print(f"  disabled trigger: {disabled_trigger}")
        print(f"  has connections:  {has_connections} (outbound links: {connection_count})")
        print(f"  settings.saveExecutionProgress: {save_execution}")
        print(f"  settings.saveManualExecutions:  {save_manual_executions}")
        print(f"  settings.executionOrder:        {execution_order}")

        # Validity checks
        if len(nodes) == 0:
            print("  VALIDITY: INVALID - empty node list")
            all_valid = False
        elif not trigger_types:
            print("  VALIDITY: WARNING - no trigger node detected (workflow may not run automatically)")
            all_valid = False
        elif disabled_trigger:
            print("  VALIDITY: WARNING - at least one trigger node is disabled")
            all_valid = False
        elif not has_connections and len(nodes) > 1:
            print("  VALIDITY: WARNING - multiple nodes but no connections")
            all_valid = False
        else:
            print("  VALIDITY: OK - has trigger(s), non-empty, connected")

    print("\n" + "=" * 80)
    return 0 if all_valid else 2


if __name__ == "__main__":
    sys.exit(main())
