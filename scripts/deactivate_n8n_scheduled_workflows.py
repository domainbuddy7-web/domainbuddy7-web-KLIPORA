#!/usr/bin/env python3
"""
Deactivate WF-VIDEO and WF-ASSEMBLE in n8n (stops schedule from firing).
Requires: N8N_URL, N8N_API_KEY in env or .env.
Usage: python scripts/deactivate_n8n_scheduled_workflows.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ENV_PATH = os.path.join(ROOT, ".env")

# Workflow IDs (from n8n URL / existing scripts)
WF_VIDEO_ID = "jTJnXHXjqo7FwGZV"
WF_ASSEMBLE_ID = "EzV0MUz5U6ZOnOjV"


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


_load_env()


def main() -> None:
    n8n_url = os.environ.get("N8N_URL", "").rstrip("/")
    api_key = os.environ.get("N8N_API_KEY")
    if not n8n_url or not api_key:
        print("Set N8N_URL and N8N_API_KEY (e.g. in .env or Railway).")
        print("  Then run: python scripts/deactivate_n8n_scheduled_workflows.py")
        sys.exit(1)

    headers = {
        "X-N8N-API-KEY": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    for name, wf_id in [
        ("WF-VIDEO", WF_VIDEO_ID),
        ("WF-ASSEMBLE", WF_ASSEMBLE_ID),
    ]:
        try:
            # GET current workflow
            req = urllib.request.Request(
                f"{n8n_url}/api/v1/workflows/{wf_id}",
                headers={k: v for k, v in headers.items() if k != "Content-Type"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                wf = json.loads(resp.read().decode())
            wf["active"] = False
            # PUT with active: false
            data = json.dumps(wf).encode("utf-8")
            req = urllib.request.Request(
                f"{n8n_url}/api/v1/workflows/{wf_id}",
                data=data,
                method="PUT",
                headers=headers,
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode())
                print(f"OK: {name} deactivated (id={result.get('id')}, active={result.get('active')}).")
        except urllib.error.HTTPError as e:
            body = e.read().decode() if e.fp else ""
            print(f"FAIL: {name} HTTP {e.code}: {body[:200]}")
            if e.code == 404:
                print(f"  Workflow id {wf_id} not found; update IDs in this script.")
        except Exception as e:
            print(f"FAIL: {name} {e}")
            sys.exit(1)

    print("Done. Scheduled runs (WF-VIDEO, WF-ASSEMBLE) are now off.")


if __name__ == "__main__":
    main()
