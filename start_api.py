"""
Start the Mission Control API (for Docker / Railway).
Uses PORT from environment; defaults to 8000.
"""
import os
import sys

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"Starting KLIPORA Mission Control API on port {port}", flush=True)
    import uvicorn
    uvicorn.run(
        "Command_Center.dashboard_api:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
