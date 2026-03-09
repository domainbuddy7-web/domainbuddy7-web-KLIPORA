"""
Shared keyboard factory: nav row, refresh, back, standard panel footer.

Builds InlineKeyboardMarkup from reusable rows (e.g. main_dashboard_button(),
refresh_button(callback_data), panel_footer()). Panels compose these instead
of repeating "Main dashboard" and "Refresh" strings. Callback_data values
should come from constants.py.

See docs/TELEGRAM_DASHBOARD_ARCHITECTURE_DESIGN.md.
"""
