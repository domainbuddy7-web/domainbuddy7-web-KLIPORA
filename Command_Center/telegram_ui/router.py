"""
Callback routing: registry and dispatcher for Telegram inline button callbacks.

Maps callback_data (exact or prefix) to handler functions. The single
CallbackQueryHandler in telegram_command_center.py will delegate to
handle_callback(update, context, api_client, redis_state, diagnostics).
Panels and wizard register their callback_data and handlers here so the
monolithic if/elif chain can be replaced by a lookup and dispatch.

See docs/TELEGRAM_DASHBOARD_ARCHITECTURE_DESIGN.md.
"""
