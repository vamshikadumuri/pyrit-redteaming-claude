"""Run the web app inside pyrit:0.13.0-v2.
OPENAI_CHAT_KEY=... ATTACKER_ENDPOINT=... ATTACKER_MODEL=... python scripts/serve.py
"""

import os

import uvicorn

from agentic_redteam.logging_config import configure_logging
from agentic_redteam.web.app import create_app

if __name__ == "__main__":
    configure_logging()
    app = create_app(store_path=os.environ.get("APP_DB", "app.sqlite3"))
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8006")))
