import contextvars
import uuid
from typing import Optional
import threading



request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar('request_id', default=None)

def get_request_id() -> Optional[str]:
    return request_id_var.get() # Get the request ID from the request context

def set_request_id(request_id: Optional[str]) -> None:
    request_id_var.set(request_id) # Set the request ID in the request context

def generate_request_id() -> str:
    return str(uuid.uuid4()) # Generate a unique request ID


def ensure_request_id() -> str:
    request_id = get_request_id() or "N/A" # Get the request ID from the request context or use
    if not request_id:
        request_id = generate_request_id()
        set_request_id(request_id)
    return request_id


