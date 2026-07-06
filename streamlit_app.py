"""Streamlit launcher for V5 dual-service architecture.

This wrapper keeps the existing app.py as the current Streamlit UI entrypoint.
Render Streamlit Service should run this file:

    streamlit run streamlit_app.py --server.port $PORT --server.address 0.0.0.0
"""

from pathlib import Path

APP_FILE = Path(__file__).resolve().parent / "app.py"

if not APP_FILE.exists():
    raise FileNotFoundError("app.py not found. Keep streamlit_app.py in the project root.")

exec(APP_FILE.read_text(encoding="utf-8"), globals())
