#!/usr/bin/env python3
"""
Upload WF-VIDEO.json to n8n (replace existing workflow nodes/connections).
Adds webhook trigger POST /webhook/wf-video so the pipeline can chain from WF-GEN.
Requires: N8N_URL, N8N_API_KEY in env (or .env).
Usage: python scripts/upload_wf_video.py
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WF_PATH = os.path.join(ROOT, "Automation", "WF-VIDEO.json")
WF_ID = "jTJnXHXjqo7FwGZV"

_ENV_PATH = os.path.join(ROOT, ".env")
_KEY_ENV = os.path.join(ROOT, "KEY=value.env")


def _load_env_file(path: str) -> None:
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("|") or "=" not in line:
                continue
            if line.startswith("```"):
                continue
            key, _, value = line.partition("=")
            key = key.strip().lstrip("|").strip()
            value = value.strip().strip('"').strip("'").rstrip("|").strip()
            if key and not key.startswith(" "):
                os.environ[key] = value


# Prefer KEY=value.env (has valid N8N_API_KEY); fallback to .env
if os.path.isfile(_KEY_ENV):
    _load_env_file(_KEY_ENV)
_load_env_file(_ENV_PATH)


def main() -> int:
    n8n_url = os.environ.get("N8N_URL", "").rstrip("/")
    api_key = os.environ.get("N8N_API_KEY")
    if not n8n_url or not api_key:
        print("Set N8N_URL and N8N_API_KEY (e.g. in .env or KEY=value.env)")
        sys.exit(1)

    with open(WF_PATH, "r", encoding="utf-8") as f:
        local_wf = json.load(f)

    import urllib.request
    import urllib.error

    headers = {"X-N8N-API-KEY": api_key, "Accept": "application/json"}
    try:
        req = urllib.request.Request(f"{n8n_url}/api/v1/workflows/{WF_ID}", headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            remote = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"GET workflow failed: {e}")
        sys.exit(1)

    # Do not send id (read-only)
    payload = {
        "name": local_wf.get("name", remote.get("name")),
        "nodes": local_wf["nodes"],
        "connections": local_wf["connections"],
        "settings": local_wf.get("settings", remote.get("settings", {})),
    }
    # tags are read-only; do not send

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{n8n_url}/api/v1/workflows/{WF_ID}",
        data=data,
        method="PUT",
        headers={"X-N8N-API-KEY": api_key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
        print(f"OK: workflow '{result.get('name')}' updated (id={result.get('id')}). Webhook POST /webhook/wf-video will register when active.")
    except urllib.error.HTTPError as e:
        print(f"PUT failed: {e}")
        if e.fp:
            try:
                print(e.fp.read().decode())
            except Exception:
                pass
        sys.exit(1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
