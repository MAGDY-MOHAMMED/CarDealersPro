import logging
import sys
from app.core.request_id import get_request_id


class RequestIDFormatter(logging.Formatter): # Formatter that adds request ID to log records
    def format(self, record):
        request_id = get_request_id() or "N/A" # Get the request ID from the request context or use "N/A" if not available
        if not hasattr(record, 'request_id'): # Check if the record already has a request ID
            record.request_id = request_id
        return super().format(record) # Call the parent class's format method to format the log record by settings


LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | [%(request_id)s] | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

formatter = RequestIDFormatter(LOG_FORMAT, datefmt=DATE_FORMAT) # Format for log messages

# Console handler only (for Docker/AWS/Cloud logging)
console_handler = logging.StreamHandler(sys.stdout) # Handler for console output
console_handler.setFormatter(formatter)

logger = logging.getLogger("CarDealersPro") # Logger for the application
logger.setLevel(logging.INFO) # INFO is the default level

if not logger.handlers: # Check if the logger already has handlers to avoid duplicates
    logger.addHandler(console_handler)
logger.propagate = False # Prevent log messages from being passed to the root logger (to avoid duplicates)

def set_log_level(level: str):
    numeric_level = getattr(logging, level.upper(),None)
    if not isinstance(numeric_level, int): # Check if the level is valid
        raise ValueError(f"Invalid log level: {level}")
    logger.setLevel(numeric_level) # Update the level for the logger
    for handler in logger.handlers: # Update the level for all existing handlers
        handler.setLevel(numeric_level)



