from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
API_DIR = BASE_DIR / "api"
CONFIG_DIR = BASE_DIR / "config"
SERVICES_DIR = BASE_DIR / "services"
SHARED_DIR = BASE_DIR / "shared"
ASSETS_DIR = BASE_DIR / "assets"
PAGES_DIR = BASE_DIR / "pages"

ENV_FILE = BASE_DIR / ".env"
ENV_EXAMPLE_FILE = BASE_DIR / ".env.example"
