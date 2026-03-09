"""
Redis state for Telegram: wizard state, topic settings, system visual style.

Wizard state keyed by chat_id (e.g. telegram:wizard:{chat_id}). Topic
settings: telegram:topic_settings:{chat_id}. System visual style:
system:visual_style. All Redis keys and value shapes live here; UI code
does not touch raw Redis. No Telegram types.

See docs/TELEGRAM_DASHBOARD_ARCHITECTURE_DESIGN.md.
"""
