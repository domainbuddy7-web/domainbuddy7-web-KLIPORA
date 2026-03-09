#!/usr/bin/env python3
"""
Upload WF-ASSEMBLE.json to n8n (replace existing workflow).
Requires: N8N_URL, N8N_API_KEY in env (or .env).
Usage: python scripts/upload_wf_assemble.py
"""
from __future__ import annotations

import json
import os
import sys

# Repo root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WF_PATH = os.path.join(ROOT, "Automation", "WF-ASSEMBLE.json")
WF_ID = "EzV0MUz5U6ZOnOjV"  # from handoff

_ENV_PATH = os.path.join(ROOT, ".env")


def _load_env_file() -> None:
    """Load only KEY=value lines from .env (ignores markdown and comments)."""
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


# Load .env with our parser first (handles markdown-heavy files); skip dotenv to avoid parse noise
_load_env_file()


def main() -> None:
    n8n_url = os.environ.get("N8N_URL", "").rstrip("/")
    api_key = os.environ.get("N8N_API_KEY")
    if not n8n_url or not api_key:
        print("Set N8N_URL and N8N_API_KEY (e.g. in .env or Railway)")
        print(f"  N8N_URL set: {bool(n8n_url)}  N8N_API_KEY set: {bool(api_key)}")
        sys.exit(1)
    print(f"Using N8N_URL={n8n_url[:50]}...  API key length: {len(api_key)}")

    with open(WF_PATH, "r", encoding="utf-8") as f:
        local_wf = json.load(f)

    import urllib.request
    import urllib.error
    headers = {"X-N8N-API-KEY": api_key, "Accept": "application/json"}

    # GET current workflow to preserve n8n id and versionId
    try:
        req = urllib.request.Request(
            f"{n8n_url}/api/v1/workflows/{WF_ID}",
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            remote = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("401 Unauthorized: N8N_API_KEY is wrong or expired. In n8n go to Settings -> API, create a new key, put it in .env as N8N_API_KEY=...")
        else:
            print(f"GET workflow failed: {e}")
        if e.code == 404:
            print("Workflow ID not found. List your workflow IDs in n8n and set WF_ID in this script, or import WF-ASSEMBLE.json manually.")
        sys.exit(1)
    except Exception as e:
        print(f"GET workflow failed: {e}")
        sys.exit(1)

    # Build payload with only properties n8n API accepts (id is read-only, do not send)
    payload = {
        "name": local_wf.get("name", remote.get("name")),
        "nodes": local_wf["nodes"],
        "connections": local_wf["connections"],
        "settings": local_wf.get("settings", remote.get("settings", {})),
    }
    # tags/id are read-only; do not send

    # PUT
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{n8n_url}/api/v1/workflows/{WF_ID}",
        data=data,
        method="PUT",
        headers={
            "X-N8N-API-KEY": api_key,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
        print(f"OK: workflow '{result.get('name')}' updated (id={result.get('id')}).")
    except Exception as e:
        print(f"PUT workflow failed: {e}")
        if hasattr(e, "read"):
            try:
                print(e.read().decode())
            except Exception:
                pass
        sys.exit(1)


if __name__ == "__main__":
    main()
