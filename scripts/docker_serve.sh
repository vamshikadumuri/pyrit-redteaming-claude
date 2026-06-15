#!/bin/bash
set -e

PYTHON=/opt/venv/bin/python

echo "Installing missing dependencies..."
uv pip install --python $PYTHON -q aiosqlite python-multipart

echo "Starting agentic-redteam web app..."
cd /workspace
PYTHONPATH=/workspace $PYTHON scripts/serve.py
