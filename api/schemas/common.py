from pydantic import BaseModel
from typing import Any


class ApiResponse(BaseModel):
    ok: bool = True
    message: str = "success"
    data: Any = None
