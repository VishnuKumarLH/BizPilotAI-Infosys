"""Flask CLI, WSGI, and local development entry point."""

from __future__ import annotations

import os

from bizpilot import create_app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", app.config.get("PORT", 5000)))
    app.run(host="0.0.0.0", port=port, debug=bool(app.config.get("FLASK_DEBUG")))
