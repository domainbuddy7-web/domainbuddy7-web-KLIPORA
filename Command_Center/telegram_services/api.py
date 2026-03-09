"""
Mission Control API client: GET, POST, PATCH to Mission Control URL.

Holds base URL (from env or injection) and exposes api_get(path),
api_post(path, body), api_patch(path, body). Returns decoded JSON or
a canonical error shape (_error, _code or detail). No Telegram types;
used by panels and diagnostics.

See docs/TELEGRAM_DASHBOARD_ARCHITECTURE_DESIGN.md.
"""
