#!/usr/bin/env python3
"""
Read-only verification: fetch KLIPORA workflow definitions from n8n API,
parse nodes and connections, detect cross-workflow triggers (HTTP Request,
Execute Workflow, Webhook), and output a pipeline map.
Does not modify any workflow or existing scripts.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ENV_PATH = os.path.join(ROOT, ".env")
TARGET_NAMES = ("WF-TREND", "WF-GEN", "WF-VIDEO", "WF-ASSEMBLE")

# Expected pipeline: WF-TREND (data) -> WF-GEN -> WF-VIDEO -> WF-ASSEMBLE (publish)
PIPELINE_ORDER = ["WF-TREND", "WF-GEN", "WF-VIDEO", "WF-ASSEMBLE"]


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


def _get_node_type(n: dict) -> str:
    return (n.get("type") or "").strip()


def _is_trigger_node(n: dict) -> bool:
    t = _get_node_type(n).lower()
    return (
        "trigger" in t
        or "webhook" in t
        or "cron" in t
        or "schedule" in t
    )


def _is_http_request(n: dict) -> bool:
    t = _get_node_type(n).lower()
    return "httprequest" in t or "http" in t and "request" in t


def _is_execute_workflow(n: dict) -> bool:
    t = _get_node_type(n).lower()
    return "executeworkflow" in t or "execute" in t and "workflow" in t


def _is_webhook_trigger(n: dict) -> bool:
    t = _get_node_type(n).lower()
    return "webhook" in t and _is_trigger_node(n)


def _extract_http_url(node: dict) -> list[str]:
    """Extract URL(s) from HTTP Request node parameters (url, path in options, etc.)."""
    urls = []
    params = node.get("parameters") or {}
    # Direct url field (string or expression object with value)
    url = params.get("url") or params.get("URL")
    if isinstance(url, str) and url.strip():
        urls.append(url.strip())
    if isinstance(url, dict) and isinstance(url.get("value"), str) and url["value"].strip():
        urls.append(url["value"].strip())
    # options.url or method+url
    opts = params.get("options") or {}
    if isinstance(opts.get("url"), str) and opts["url"].strip():
        urls.append(opts["url"].strip())
    # Some nodes use path + baseUrl or sendBody
    path = params.get("path")
    if isinstance(path, str) and path.strip():
        base = (params.get("baseUrl") or opts.get("baseUrl") or "").strip()
        if isinstance(base, dict):
            base = (base.get("value") or base.get("value")) or ""
        urls.append((base.rstrip("/") + "/" + path.lstrip("/")).strip("/") or path)
    # Recursively collect any string that looks like a URL from params (for nested structures)
    def collect_urls(obj, out: list):
        if isinstance(obj, str) and ("http" in obj or "webhook" in obj.lower() or "/wf-" in obj.lower()):
            out.append(obj)
        elif isinstance(obj, dict):
            for v in obj.values():
                collect_urls(v, out)
        elif isinstance(obj, list):
            for v in obj:
                collect_urls(v, out)
    collect_urls(params, urls)
    return list(dict.fromkeys(u.strip() for u in urls if isinstance(u, str) and u.strip()))


def _classify_downstream_url(url: str) -> str | None:
    """Classify URL as wf-video, wf-assemble, wf-gen, mission-control, or other."""
    u = (url or "").lower()
    if "/webhook/wf-video" in u or "wf-video" in u:
        return "WF-VIDEO"
    if "/webhook/wf-assemble" in u or "wf-assemble" in u:
        return "WF-ASSEMBLE"
    if "/webhook/wf-gen" in u or "wf-gen" in u:
        return "WF-GEN"
    if "/internal/notify-preview" in u or "notify-preview" in u:
        return "Mission Control (notify-preview)"
    if "mission" in u or "commands/" in u:
        return "Mission Control"
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

    # 1) List workflows and get target IDs
    r = requests.get(f"{n8n_url}/api/v1/workflows", headers=headers, timeout=15)
    r.raise_for_status()
    data = r.json()
    wf_list = data.get("data", data) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    targets = []
    for wf in wf_list:
        name = (wf.get("name") or "")
        for tag in TARGET_NAMES:
            if tag in name:
                targets.append((wf.get("id"), name))
                break

    # 2) Fetch full definition for each
    workflows = {}
    for wf_id, wf_name in targets:
        r2 = requests.get(f"{n8n_url}/api/v1/workflows/{wf_id}", headers=headers, timeout=15)
        r2.raise_for_status()
        workflows[wf_id] = {"id": wf_id, "name": wf_name, "full": r2.json()}

    # 3) For each workflow: triggers, HTTP/Execute nodes, and classify downstream
    print("=" * 90)
    print("KLIPORA pipeline linkage verification (read-only)")
    print("=" * 90)

    pipeline_position = {}
    for i, tag in enumerate(PIPELINE_ORDER):
        pipeline_position[tag] = i + 1

    report = []
    all_downstream = {}

    for wf_id, wf_name in targets:
        full = workflows[wf_id]["full"]
        nodes = full.get("nodes") or []
        connections = full.get("connections") or {}

        trigger_nodes = [n for n in nodes if _is_trigger_node(n)]
        http_nodes = [n for n in nodes if _is_http_request(n)]
        exec_wf_nodes = [n for n in nodes if _is_execute_workflow(n)]

        trigger_types = [(_get_node_type(n), n.get("name")) for n in trigger_nodes]
        downstream_calls = []

        for n in http_nodes:
            urls = _extract_http_url(n)
            for url in urls:
                classification = _classify_downstream_url(url)
                if classification:
                    downstream_calls.append(("HTTP Request", n.get("name"), url[:80], classification))
        # Fallback: scan workflow JSON for webhook path strings (URL may be in expression)
        # Only add downstream when this workflow is the caller (WF-GEN calls wf-video, WF-VIDEO calls wf-assemble)
        full_str = json.dumps(full)
        if "WF-GEN" in wf_name and ("/webhook/wf-video" in full_str or "wf-video" in full_str):
            if not any("WF-VIDEO" in d[3] for d in downstream_calls):
                downstream_calls.append(("HTTP Request (from workflow body)", "Trigger WF-VIDEO or similar", "/webhook/wf-video", "WF-VIDEO"))
        if "WF-VIDEO" in wf_name and ("/webhook/wf-assemble" in full_str or "wf-assemble" in full_str):
            if not any("WF-ASSEMBLE" in d[3] for d in downstream_calls):
                downstream_calls.append(("HTTP Request (from workflow body)", "Trigger WF-ASSEMBLE or similar", "/webhook/wf-assemble", "WF-ASSEMBLE"))

        for n in exec_wf_nodes:
            params = n.get("parameters") or {}
            target = params.get("workflowId") or params.get("workflow") or params.get("target")
            if target:
                downstream_calls.append(("Execute Workflow", n.get("name"), str(target)[:80], "workflow:" + str(target)))

        # Detect by HTTP node name (e.g. "Trigger WF-VIDEO", "Trigger WF-ASSEMBLE") when URL not in params
        for n in http_nodes:
            name = (n.get("name") or "").upper()
            if "WF-VIDEO" in name or "TRIGGER WF-VIDEO" in name:
                if not any("WF-VIDEO" in d[3] for d in downstream_calls):
                    downstream_calls.append(("HTTP Request (by node name)", n.get("name"), "POST webhook", "WF-VIDEO"))
            if "WF-ASSEMBLE" in name or "TRIGGER WF-ASSEMBLE" in name:
                if not any("WF-ASSEMBLE" in d[3] for d in downstream_calls):
                    downstream_calls.append(("HTTP Request (by node name)", n.get("name"), "POST webhook", "WF-ASSEMBLE"))

        # Pipeline position
        pos = "?"
        for tag in TARGET_NAMES:
            if tag in wf_name:
                pos = f"Stage {pipeline_position[tag]}: {tag}"
                break

        report.append({
            "name": wf_name,
            "id": wf_id,
            "position": pos,
            "trigger_nodes": trigger_types,
            "downstream": downstream_calls,
        })
        all_downstream[wf_name] = [d[3] for d in downstream_calls]

    # 4) Print report
    for r in report:
        print(f"\n--- {r['name']} ---")
        print(f"  Workflow ID:     {r['id']}")
        print(f"  Pipeline position: {r['position']}")
        print(f"  Trigger node(s):")
        for t, name in r["trigger_nodes"]:
            print(f"    - {t} ({name})")
        print(f"  Downstream workflow / service call(s):")
        if not r["downstream"]:
            print("    (none detected in this workflow)")
        else:
            for kind, node_name, target, classification in r["downstream"]:
                print(f"    - {kind} [{node_name}]: -> {classification}  ({target})")

    # 5) Pipeline map and dead-end check
    print("\n" + "=" * 90)
    print("PIPELINE MAP (intended: WF-TREND -> WF-GEN -> WF-VIDEO -> WF-ASSEMBLE)")
    print("=" * 90)

    expected_chain = [
        ("WF-GEN", "WF-VIDEO", "WF-GEN should trigger WF-VIDEO (POST /webhook/wf-video)"),
        ("WF-VIDEO", "WF-ASSEMBLE", "WF-VIDEO should trigger WF-ASSEMBLE (POST /webhook/wf-assemble)"),
    ]
    dead_ends = []
    for r in report:
        name = r["name"]
        downstream = all_downstream.get(name, [])
        has_wf_video = any("WF-VIDEO" in d for d in downstream)
        has_wf_assemble = any("WF-ASSEMBLE" in d for d in downstream)
        has_mc = any("Mission Control" in d or "notify" in d for d in downstream)
        if "WF-GEN" in name and not has_wf_video:
            dead_ends.append(f"{name}: no call to WF-VIDEO webhook detected")
        elif "WF-VIDEO" in name and not has_wf_assemble:
            dead_ends.append(f"{name}: no call to WF-ASSEMBLE webhook detected")
        elif "WF-ASSEMBLE" in name and not has_mc:
            # ASSEMBLE should call Mission Control notify-preview (or at least do something downstream)
            if not downstream:
                dead_ends.append(f"{name}: no downstream call to Mission Control detected (check notify-preview)")

    for prev, next_wf, desc in expected_chain:
        found = False
        for r in report:
            if prev in r["name"]:
                if any(next_wf in d for d in all_downstream.get(r["name"], [])):
                    found = True
                break
        print(f"  {prev} -> {next_wf}: {'OK' if found else 'NOT DETECTED'} ({desc})")

    if dead_ends:
        print("\n  Potential dead ends or missing links:")
        for d in dead_ends:
            print(f"    - {d}")
        print("\n  Note: Pipeline may still function via QUEUE + SCHEDULE: WF-GEN pushes to script_queue;")
        print("  WF-VIDEO polls script_queue on schedule; WF-VIDEO pushes to render_queue;")
        print("  WF-ASSEMBLE polls render_queue on schedule. Event-driven POST webhooks are optional.")
    else:
        print("\n  No dead ends detected: each stage has expected downstream call(s) or is the final stage (WF-ASSEMBLE -> Mission Control).")

    print("\n" + "=" * 90)
    return 0


def _print_proposed_patch(repo_gen: dict, repo_video: dict) -> None:
    """Print proposed workflow patch: nodes to add + connection updates (for deployment plan)."""
    def _find_trigger(wf: dict, url_sub: str) -> dict | None:
        for n in wf.get("nodes") or []:
            url = (n.get("parameters") or {}).get("url") or ""
            if url_sub in str(url):
                return n
        return None

    print("\n" + "=" * 90)
    print("PROPOSED WORKFLOW PATCH (nodes + connection additions only; do not deploy from script)")
    print("=" * 90)

    n1 = _find_trigger(repo_gen, "wf-video")
    n2 = _find_trigger(repo_video, "wf-assemble")
    if n1:
        print("\n--- WF-GEN: node to ADD ---")
        print(json.dumps(n1, indent=2))
        print("\n--- WF-GEN: connection updates (add to workflow.connections) ---")
        print('  "Push to script_queue": { "main": [[{ "node": "Trigger WF-VIDEO", "type": "main", "index": 0 }]] },')
        print('  "Trigger WF-VIDEO": { "main": [[{ "node": "Notify Script Ready", "type": "main", "index": 0 }]] }')
    if n2:
        print("\n--- WF-VIDEO: node to ADD ---")
        print(json.dumps(n2, indent=2))
        print("\n--- WF-VIDEO: connection updates (add to workflow.connections) ---")
        print('  "Set Count Expiry 24h": { "main": [[{ "node": "Trigger WF-ASSEMBLE", "type": "main", "index": 0 }]] }')
    print("\n" + "=" * 90)


def _compare_repo_vs_live(
    n8n_url: str,
    headers: dict,
    wf_gen_id: str,
    wf_video_id: str,
) -> None:
    """Load repo workflow JSON from Automation/, compare to live API; print diff of event-driven trigger nodes."""
    automation_dir = os.path.join(ROOT, "Automation")
    repo_gen_path = os.path.join(automation_dir, "WF-GEN.json")
    repo_video_path = os.path.join(automation_dir, "WF-VIDEO.json")

    def _load_repo_wf(path: str) -> dict | None:
        if not os.path.isfile(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _event_trigger_nodes(wf: dict, url_substring: str) -> list[dict]:
        out = []
        for n in wf.get("nodes") or []:
            params = n.get("parameters") or {}
            url = params.get("url") or params.get("path") or ""
            if url_substring in str(url):
                out.append(n)
        return out

    def _connection_incoming(connections: dict, node_name: str) -> list[str]:
        incoming = []
        for src, out in (connections or {}).items():
            for main_list in out.get("main") or []:
                for edge in main_list or []:
                    if edge.get("node") == node_name:
                        incoming.append(src)
                        break
        return incoming

    def _connection_outgoing(connections: dict, node_name: str) -> list[str]:
        out = (connections or {}).get(node_name, {}).get("main", [[]])
        return [e.get("node") for lst in out for e in (lst or []) if e.get("node")]

    print("\n" + "=" * 90)
    print("REPO vs LIVE: event-driven trigger nodes (Automation/*.json vs GET /api/v1/workflows/{id})")
    print("=" * 90)

    repo_gen = _load_repo_wf(repo_gen_path)
    repo_video = _load_repo_wf(repo_video_path)
    if not repo_gen or not repo_video:
        print("  Could not load Automation/WF-GEN.json or WF-VIDEO.json. Skipping repo vs live diff.")
        return

    trigger_gen = _event_trigger_nodes(repo_gen, "wf-video")
    trigger_video = _event_trigger_nodes(repo_video, "wf-assemble")

    live_gen = live_video = None
    try:
        r1 = requests.get(f"{n8n_url}/api/v1/workflows/{wf_gen_id}", headers=headers, timeout=15)
        r1.raise_for_status()
        live_gen = r1.json()
    except Exception as e:
        print(f"  Live WF-GEN fetch failed: {e}")
    try:
        r2 = requests.get(f"{n8n_url}/api/v1/workflows/{wf_video_id}", headers=headers, timeout=15)
        r2.raise_for_status()
        live_video = r2.json()
    except Exception as e:
        print(f"  Live WF-VIDEO fetch failed: {e}")

    live_gen_names = {n.get("name") for n in (live_gen or {}).get("nodes") or []}
    live_video_names = {n.get("name") for n in (live_video or {}).get("nodes") or []}

    # --- WF-GEN: Trigger WF-VIDEO ---
    print("\n--- WF-GEN (repo: Automation/WF-GEN.json, live id: " + wf_gen_id + ") ---")
    for n in trigger_gen:
        name = n.get("name")
        in_live = name in live_gen_names
        params = n.get("parameters") or {}
        url = params.get("url", "")
        method = params.get("method", "")
        pos = n.get("position", [])
        conn_in = _connection_incoming(repo_gen.get("connections") or {}, name)
        conn_out = _connection_outgoing(repo_gen.get("connections") or {}, name)
        print(f"  Node: {name}")
        print(f"    type: {n.get('type')}")
        print(f"    method: {method}  url: {url[:70]}...")
        print(f"    position: {pos}")
        print(f"    connection: {' -> '.join(conn_in)} -> [{name}] -> {' -> '.join(conn_out)}")
        print(f"    IN REPO: yes   IN LIVE: {'yes' if in_live else 'NO (MISSING)'}")
        if not in_live:
            print("    >>> REPO NODE MISSING IN LIVE DEPLOYMENT <<<")

    # --- WF-VIDEO: Trigger WF-ASSEMBLE ---
    print("\n--- WF-VIDEO (repo: Automation/WF-VIDEO.json, live id: " + wf_video_id + ") ---")
    for n in trigger_video:
        name = n.get("name")
        in_live = name in live_video_names
        params = n.get("parameters") or {}
        url = params.get("url", "")
        method = params.get("method", "")
        pos = n.get("position", [])
        conn_in = _connection_incoming(repo_video.get("connections") or {}, name)
        conn_out = _connection_outgoing(repo_video.get("connections") or {}, name)
        print(f"  Node: {name}")
        print(f"    type: {n.get('type')}")
        print(f"    method: {method}  url: {url[:70]}...")
        print(f"    position: {pos}")
        print(f"    connection: {' -> '.join(conn_in)} -> [{name}] -> {' -> '.join(conn_out)}")
        print(f"    IN REPO: yes   IN LIVE: {'yes' if in_live else 'NO (MISSING)'}")
        if not in_live:
            print("    >>> REPO NODE MISSING IN LIVE DEPLOYMENT <<<")

    print("\n" + "=" * 90)
    print("Adding these nodes would convert: schedule-polling -> hybrid event-driven + polling (lower latency).")
    print("=" * 90)

    _print_proposed_patch(repo_gen, repo_video)


if __name__ == "__main__":
    import requests
    _load_env()
    n8n_url = os.environ.get("N8N_URL", "").rstrip("/")
    api_key = os.environ.get("N8N_API_KEY")
    if n8n_url and api_key:
        headers = {"X-N8N-API-KEY": api_key, "Accept": "application/json", "Content-Type": "application/json"}
        _compare_repo_vs_live(n8n_url, headers, "VCw1KVSRcgRmlujA", "jTJnXHXjqo7FwGZV")
    sys.exit(main())
