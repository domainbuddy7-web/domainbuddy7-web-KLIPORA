#!/usr/bin/env python3
"""
Ensure KLIPORA n8n workflows (WF-TREND, WF-GEN, WF-VIDEO, WF-ASSEMBLE) are active.
Uses n8n API: list workflows, then for each inactive target workflow, GET + PUT active=true.
Requires: N8N_URL, N8N_API_KEY in env or .env.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ENV_PATH = os.path.join(ROOT, ".env")

# Names to match (workflow name must contain one of these)
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
        print("Set N8N_URL and N8N_API_KEY (e.g. in .env). Cannot query n8n API.", file=sys.stderr)
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
    base = n8n_url

    # 1) List workflows
    try:
        r = requests.get(f"{base}/api/v1/workflows", headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        print(f"n8n API list failed: {e}", file=sys.stderr)
        return 2

    if isinstance(data, dict) and "data" in data:
        wf_list = data["data"]
    else:
        wf_list = data if isinstance(data, list) else []

    # 2) Find target workflows by name
    targets = []
    for wf in wf_list:
        name = (wf.get("name") or "")
        for tag in TARGET_NAMES:
            if tag in name:
                targets.append((name, wf.get("id"), wf.get("active", False)))
                break

    report = []
    for name, wf_id, was_active in targets:
        prev = "active" if was_active else "inactive"
        if was_active:
            report.append({"name": name, "previous": prev, "current": "active"})
            continue
        # 3) GET full workflow, set active=True, PUT
        try:
            r = requests.get(f"{base}/api/v1/workflows/{wf_id}", headers=headers, timeout=15)
            r.raise_for_status()
            body = r.json()
            body["active"] = True
            r2 = requests.put(
                f"{base}/api/v1/workflows/{wf_id}",
                headers=headers,
                data=json.dumps(body),
                timeout=15,
            )
            r2.raise_for_status()
            report.append({"name": name, "previous": prev, "current": "active"})
        except requests.RequestException as e:
            report.append({"name": name, "previous": prev, "current": f"error: {e}"})

    # Print report
    print("Workflow name                    | Previous  | Current")
    print("-" * 60)
    for row in report:
        name = (row["name"] or "")[:30].ljust(30)
        print(f"{name} | {row['previous']:9} | {row['current']}")
    return 0 if all(r["current"] == "active" for r in report) else 3


if __name__ == "__main__":
    sys.exit(main())
