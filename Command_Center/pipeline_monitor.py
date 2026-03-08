"""
KLIPORA Command Center — Pipeline Monitor

Responsibility:
- Read-only view into n8n workflow and execution state.
- Utility methods for detecting failed executions.

This module only talks to n8n. Queue and Redis health are handled by
`system_guardian.py`.
"""

from __future__ import annotations

import datetime as _dt
import typing as t

from Infrastructure.api_clients import N8nClient, get_n8n_client


class PipelineMonitor:
    """
    Thin wrapper around `N8nClient` specialised for monitoring.
    """

    def __init__(self, n8n_client: t.Optional[N8nClient] = None, config: t.Optional[dict] = None) -> None:
        self.client = n8n_client or get_n8n_client()

    # ── Workflow and execution listing ─────────────────────────────────────

    def list_workflows(self) -> t.Any:
        """
        Return all workflows from n8n.
        """
        return self.client.list_workflows()

    def list_recent_executions(
        self,
        status: t.Optional[str] = None,
        workflow_id: t.Optional[str] = None,
        limit: int = 50,
    ) -> t.Any:
        """
        Return recent executions, optionally filtered by status or workflow.
        """
        return self.client.list_executions(
            status=status,
            workflow_id=workflow_id,
            limit=limit,
        )

    def get_execution(self, execution_id: t.Union[str, int]) -> t.Any:
        """
        Fetch a single execution from n8n.
        """
        return self.client.get_execution(execution_id)

    # ── Failure helpers ────────────────────────────────────────────────────

    def find_failed_executions(
        self,
        workflow_id: t.Optional[str] = None,
        limit: int = 50,
    ) -> t.List[dict]:
        """
        Convenience helper to fetch the most recent failed executions.
        """
        data = self.client.list_executions(
            status="error",
            workflow_id=workflow_id,
            limit=limit,
        )
        # n8n returns { data: [ ... ] } in recent versions
        executions = data.get("data") if isinstance(data, dict) else data
        return list(executions or [])

    def summarize_failures(
        self,
        workflow_id: t.Optional[str] = None,
        limit: int = 50,
    ) -> dict:
        """
        Summarise recent failed executions by workflow.
        """
        failed = self.find_failed_executions(workflow_id=workflow_id, limit=limit)
        summary: dict = {}
        for item in failed:
            wf_id = str(item.get("workflowId") or "unknown")
            summary.setdefault(wf_id, 0)
            summary[wf_id] += 1
        return summary


def utc_now_iso() -> str:
    return _dt.datetime.utcnow().isoformat() + "Z"


__all__ = ["PipelineMonitor", "utc_now_iso"]
