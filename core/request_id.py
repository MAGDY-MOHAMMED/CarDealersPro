import contextvars
import uuid
from typing import Optional
import threading



request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('request_id', default=None)

def get_request_id() -> Optional[str]:
    return _get_request_id()

def set_request_id(request_id: Optional[str]) -> None:
    _set_request_id(request_id)

def generate_request_id() -> str:
    return str(uuid.uuid4())


def ensure_request_id() -> str:
    request_id = get_request_id() or "N/A" # Get the request ID from the request context or use
    if not request_id:
        request_id = generate_request_id()
        set_request_id(request_id)
    return request_id



_request_id = threading.local() #means each thread has its own request_id


def _get_request_id() -> Optional[str]:
    return getattr(_request_id, 'id', None)

def _set_request_id(request_id: Optional[str]) -> None:
    _request_id.id = request_id