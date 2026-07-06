from datetime import date, datetime
from typing import Any


def now_text(fmt: str = "%Y-%m-%d %H:%M") -> str:
    return datetime.now().strftime(fmt)


def to_bool_text(value: Any, default: bool = True) -> str:
    if value in (True, "TRUE", "true", "1", 1, "是", "Y", "y"):
        return "TRUE"
    if value in (False, "FALSE", "false", "0", 0, "否", "N", "n"):
        return "FALSE"
    return "TRUE" if default else "FALSE"


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value or default))
    except Exception:
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except Exception:
        return default


def parse_date(value: Any, fallback: date | None = None) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if value in (None, ""):
        return fallback
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except Exception:
        return fallback
