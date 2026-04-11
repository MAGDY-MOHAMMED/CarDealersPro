from core.logger_base import logger

import contextvars
import uuid
from typing import Optional


request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('request_id', default=None)

def get_request_id() -> Optional[str]:
    return request_id_var.get() # type: ignore

def set_request_id(request_id: Optional[str]) -> None:
    request_id_var.set(request_id)

def generate_request_id() -> str:
    request_id_var.set(None)
    return str(uuid.uuid4())

def ensure_request_id() -> str:
    request_id = get_request_id()
    if request_id is None:
        request_id = generate_request_id()
        logger.info(f"Generated new request ID: {request_id}", extra={"request_id": request_id})
    return request_id