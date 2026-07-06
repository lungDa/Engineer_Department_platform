from typing import Any


def success(data: Any = None, message: str = "success") -> dict:
    return {
        "ok": True,
        "message": message,
        "data": data,
    }


def failed(message: str, data: Any = None) -> dict:
    return {
        "ok": False,
        "message": message,
        "data": data,
    }


def warning(message: str, data: Any = None) -> dict:
    return {
        "ok": True,
        "level": "warning",
        "message": message,
        "data": data,
    }
