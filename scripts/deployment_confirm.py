#!/usr/bin/env python3
"""
KLIPORA deployment confirmation: n8n workflows, webhooks, Redis, health monitor.
Uses N8N_URL and N8N_API_KEY from .env or KEY=value.env.
"""
import json
import os
import sys
import urllib.request
from urllib.error import HTTPError, URLError

def load_env():
    config = {}
    for path in (".env", "KEY=value.env"):
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip()
                if v in ("", "your_n8n_api_key", "xxxx") or "CAPS" in v:
                    continue
                config[k] = v
    return config

def main():
    config = load_env()
    base = (config.get("N8N_BASE_URL") or config.get("N8N_URL") or "").rstrip("/")
    api_key = config.get("N8N_API_KEY") or config.get("N8N_API_TOKEN")
    if not base or not api_key:
        print("ERROR: Set N8N_URL and N8N_API_KEY in .env or KEY=value.env")
        sys.exit(1)

    results = {
        "workflow_activation": {},
        "webhooks": {},
        "redis": {},
        "e2e_trigger": None,
        "health_workflow": None,
        "telegram": None,
    }

    ids = [
        ("VCw1KVSRcgRmlujA", "WF-GEN"),
        ("jTJnXHXjqo7FwGZV", "WF-VIDEO"),
        ("EzV0MUz5U6ZOnOjV", "WF-ASSEMBLE"),
    ]

    # 1–2: Check workflow status and activate
    print("--- Workflow status and activation ---")
    for wid, name in ids:
        try:
            req = urllib.request.Request(f"{base}/rest/workflows/{wid}", method="GET")
            req.add_header("X-N8N-API-KEY", api_key)
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode())
            active = data.get("active", False)
            results["workflow_activation"][name] = {"active": active, "error": None}
            print(f"  {name}: active={active}")
            if not active:
                req2 = urllib.request.Request(f"{base}/rest/workflows/{wid}/activate", method="POST")
                req2.add_header("X-N8N-API-KEY", api_key)
                try:
                    urllib.request.urlopen(req2, timeout=10)
                    results["workflow_activation"][name]["activated"] = True
                    print(f"    -> Activated")
                except HTTPError as e:
                    results["workflow_activation"][name]["error"] = f"Activate {e.code}"
                    print(f"    -> Activate failed: {e.code}")
        except HTTPError as e:
            results["workflow_activation"][name] = {"active": False, "error": f"GET {e.code}"}
            print(f"  {name}: API error {e.code}")
        except URLError as e:
            results["workflow_activation"][name] = {"active": False, "error": str(e)}
            print(f"  {name}: {e}")

    # 3: Webhook tests
    print("\n--- Webhook tests ---")
    for path, payload in (
        ("/webhook/wf-video", {"jobId": "deploy-test-v"}),
        ("/webhook/wf-assemble", {"job_id": "deploy-test-a"}),
    ):
        try:
            req = urllib.request.Request(
                base + path,
                data=json.dumps(payload).encode(),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                body = r.read().decode()
                status = r.status
            ok = status == 200 and "accepted" in body
            results["webhooks"][path] = {"status": status, "body": body[:200], "ok": ok}
            print(f"  POST {path}: {status} {'OK' if ok else 'FAIL'} {body[:80]}")
        except HTTPError as e:
            body = e.read().decode()[:200]
            results["webhooks"][path] = {"status": e.code, "body": body, "ok": False}
            print(f"  POST {path}: {e.code} {body[:80]}")
        except URLError as e:
            results["webhooks"][path] = {"error": str(e), "ok": False}
            print(f"  POST {path}: {e}")

    # 4: Trigger wf-gen
    print("\n--- E2E trigger POST /webhook/wf-gen ---")
    try:
        req = urllib.request.Request(
            base + "/webhook/wf-gen",
            data=json.dumps({
                "topic": "Deployment confirmation test",
                "genre": "Mystery",
                "chat_id": config.get("TELEGRAM_CHAT_ID", "8232710919"),
            }).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode()
            results["e2e_trigger"] = {"status": r.status, "body": body[:300]}
        print(f"  Status: {results['e2e_trigger']['status']} {body[:120]}")
    except Exception as e:
        results["e2e_trigger"] = {"error": str(e)}
        print(f"  Error: {e}")

    # 5: Redis queues
    print("\n--- Redis queues ---")
    upstash_base = "https://wealthy-hyena-4511.upstash.io"
    token = "ARGfAAImcDE5NTI1MGEzYzhjMjQ0ZWM1YTFkYjY0ZmIxOTBhNmQ4YnAxNDUxMQ"
    for key in ("script_queue", "render_queue"):
        try:
            req = urllib.request.Request(upstash_base + f"/llen/{key}", method="GET")
            req.add_header("Authorization", f"Bearer {token}")
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode())
            length = data.get("result", -1)
            results["redis"][key] = length
            print(f"  {key}: {length}")
        except Exception as e:
            results["redis"][key] = f"error: {e}"
            print(f"  {key}: {e}")

    # 6–7: Import and activate health workflow
    print("\n--- Health workflow import ---")
    wf_path = os.path.join(os.path.dirname(__file__), "..", "Automation", "WF-HEALTH.json")
    if os.path.isfile(wf_path):
        with open(wf_path, encoding="utf-8") as f:
            health_payload = json.load(f)
        # Remove meta/id so n8n creates new
        health_payload.pop("id", None)
        health_payload.pop("meta", None)
        try:
            req = urllib.request.Request(
                base + "/rest/workflows",
                data=json.dumps(health_payload).encode(),
                method="POST",
                headers={"X-N8N-API-KEY": api_key, "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                created = json.loads(r.read().decode())
            hid = created.get("id")
            results["health_workflow"] = {"imported": True, "id": hid}
            print(f"  Imported: id={hid}")
            if hid:
                req2 = urllib.request.Request(f"{base}/rest/workflows/{hid}/activate", method="POST")
                req2.add_header("X-N8N-API-KEY", api_key)
                try:
                    urllib.request.urlopen(req2, timeout=10)
                    results["health_workflow"]["active"] = True
                    results["telegram"] = "Health monitor active; status sent every 1 min to Telegram."
                    print("  Activated. Telegram status every 1 min.")
                except HTTPError as e:
                    results["health_workflow"]["active"] = False
                    results["health_workflow"]["activate_error"] = e.code
                    print(f"  Activate failed: {e.code}")
        except HTTPError as e:
            body = e.read().decode()
            if e.code == 409 or "already exists" in body.lower():
                results["health_workflow"] = {"imported": "already_exists", "message": body[:200]}
                results["telegram"] = "Health workflow may already exist; activate it in n8n for Telegram reporting."
                print("  Workflow may already exist (409). Activate in n8n if needed.")
            else:
                results["health_workflow"] = {"error": f"{e.code} {body[:200]}"}
                print(f"  Import failed: {e.code} {body[:200]}")
        except URLError as e:
            results["health_workflow"] = {"error": str(e)}
            print(f"  Import error: {e}")
    else:
        results["health_workflow"] = {"error": f"File not found: {wf_path}"}
        print(f"  Skip: {wf_path} not found")

    # Report file
    report_path = os.path.join(os.path.dirname(__file__), "..", "docs", "DEPLOYMENT_CONFIRMATION_REPORT.json")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nReport written: {report_path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
