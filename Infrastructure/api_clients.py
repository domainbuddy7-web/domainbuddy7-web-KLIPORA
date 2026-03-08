"""
KLIPORA Infrastructure — External API Clients

Centralised, minimal HTTP clients for:
- n8n Automation Engine

These helpers keep HTTP details out of agents and Command Center modules.
"""

from __future__ import annotations

import json
import os
import typing as t

import requests

ScriptPath = os.path.dirname(os.path.abspath(__file__))
KliporaRoot = os.path.dirname(ScriptPath)


def _config_from_env() -> dict:
    """
    Build minimal config from env (for Railway/cloud deployment).
    """
    url = os.environ.get("N8N_URL", "").rstrip("/")
    if url:
        return {
            "n8n_url": url,
            "n8n_api_key": os.environ.get("N8N_API_KEY"),
        }
    return {}


def _load_config() -> dict:
    """
    Load config from env (deployment) or from config.json (local).
    """
    env_config = _config_from_env()
    if env_config.get("n8n_url"):
        return env_config

    config_paths = [
        os.path.join(KliporaRoot, "Infrastructure", "config.json"),
        os.path.join(ScriptPath, "config.json"),
        os.path.join(KliporaRoot, "config.json"),
    ]

    for path in config_paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

    raise RuntimeError(
        "n8n config not found. Set N8N_URL (and optionally N8N_API_KEY), "
        "or provide config.json in one of: " + ", ".join(config_paths)
    )


class N8nClient:
    """
    Lightweight client for the n8n REST API and webhooks.

    - `base_url` should be the root n8n URL, e.g. https://example.com
    - `api_key` is optional; when absent, only webhook calls that do not
      require authentication will work.
    """

    def __init__(
        self,
        base_url: t.Optional[str] = None,
        api_key: t.Optional[str] = None,
        config: t.Optional[dict] = None,
        timeout: int = 15,
    ) -> None:
        config = config or _load_config()

        self.base_url = (base_url or config.get("n8n_url", "")).rstrip("/")
        if not self.base_url:
            raise RuntimeError("n8n_url is missing. Set N8N_URL or config.json")

        # `n8n_api_key` may be provided in config or via env var.
        self.api_key = (
            api_key
            or config.get("n8n_api_key")
            or os.environ.get("N8N_API_KEY")
        )
        self.timeout = timeout

    # ── Internal helpers ──────────────────────────────────────────────────

    def _headers(self, needs_auth: bool = True) -> dict:
        headers: dict = {"Content-Type": "application/json"}
        if needs_auth and self.api_key:
            headers["X-N8N-API-KEY"] = self.api_key
        return headers

    def _url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url + path

    # ── Public methods used by Command Center ─────────────────────────────

    # Webhooks (WF-GEN, WF-TREND, etc.)

    def trigger_webhook(
        self,
        path: str,
        payload: t.Optional[dict] = None,
        needs_auth: bool = False,
    ) -> requests.Response:
        """
        Trigger an n8n webhook.

        `path` should be the webhook path, e.g. "/webhook/wf-gen" or "webhook/wf-gen".
        """
        url = self._url(path)
        data = json.dumps(payload or {})
        resp = requests.post(
            url,
            headers=self._headers(needs_auth=needs_auth),
            data=data,
            timeout=self.timeout,
        )
        return resp

    # Core REST endpoints

    def list_workflows(self) -> t.Any:
        """
        GET /api/v1/workflows
        """
        url = self._url("/api/v1/workflows")
        resp = requests.get(url, headers=self._headers(), timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def list_executions(
        self,
        status: t.Optional[str] = None,
        workflow_id: t.Optional[str] = None,
        limit: int = 50,
    ) -> t.Any:
        """
        GET /api/v1/executions with optional filters.
        """
        url = self._url("/api/v1/executions")
        params: dict = {"limit": limit}
        if status:
            params["status"] = status
        if workflow_id:
            params["workflowId"] = workflow_id

        resp = requests.get(
            url,
            headers=self._headers(),
            params=params,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def get_execution(self, execution_id: t.Union[str, int]) -> t.Any:
        """
        GET /api/v1/executions/:id
        """
        url = self._url(f"/api/v1/executions/{execution_id}")
        resp = requests.get(url, headers=self._headers(), timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def run_workflow(
        self,
        workflow_id: t.Union[str, int],
        body: t.Optional[dict] = None,
    ) -> t.Any:
        """
        POST /api/v1/workflows/:id/run

        Requires n8n API key with appropriate permissions.
        """
        url = self._url(f"/api/v1/workflows/{workflow_id}/run")
        resp = requests.post(
            url,
            headers=self._headers(),
            data=json.dumps(body or {}),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()


def get_n8n_client() -> N8nClient:
    """
    Convenience factory to construct an N8nClient from config.json.
    """
    return N8nClient()


__all__ = [
    "N8nClient",
    "get_n8n_client",
]

