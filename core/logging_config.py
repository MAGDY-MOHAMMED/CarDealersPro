import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
import json_logging
import json
from core.request_id import get_request_id


class JSONFormatter (logging.Formatter ):
    def format(self, record):
        log_entry = {
            "timestamp" : self.formatTime(record,self.datefmt) # record has created attribute for log time and to consistent format of the timestamp between log and console
        }
        return json.dumps(log_entry)
class RequestIDFormatter(logging.Formatter): # Formatter that adds request ID to log records
    def format(self, record):
        request_id = get_request_id() or "N/A" # Get the request ID from the request context or use "N/A" if not available
        if not hasattr(record, 'request_id'): # Check if the record already has a request ID
            setattr(record, 'request_id', request_id) # Use setattr to add the attribute
        return super().format(record) # Call the parent class's format method to format the log record by settings 



LOG_DIR = Path ("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "cardealers.log"


LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | [%(request_id)s] | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

formatter = RequestIDFormatter(LOG_FORMAT, datefmt=DATE_FORMAT) # Format for log messages

# Console handler
console_handler = logging.StreamHandler(sys.stdout) # Handler for console output or terminal to show up immediatly
console_handler.setFormatter(formatter)

# File handler with rotation
file_handler = RotatingFileHandler(LOG_FILE,
    maxBytes=1024*1024*10, # 10 MB
    backupCount=5, # Keep 5 backup files
    encoding='utf-8') # Handler for file output with rotation
file_handler.setFormatter(formatter)

logger = logging.getLogger() # this is the root logger
logger.setLevel(logging.INFO) # Set the logging level for the application

logger.addHandler(console_handler) # Add the console handler to the root logger
logger.addHandler(file_handler) # Add the file handler to the root logger

#logging.basicConfig(level=logging.INFO, handlers=[console_handler, file_handler])
logger = logging.getLogger("CarDealersPro") # Logger for the application - can be used to filter log messages by name
logger.setLevel(logging.INFO) # INFO is the default level
if not logger.handlers: # Check if the logger already has handlers to avoid duplicates
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
logger.propagate = False # Prevent log messages from being passed to the root logger (to avoid duplicates) 

def set_log_level(level: str):
    numeric_level = getattr(logging, level.upper(),None)
    if not isinstance(numeric_level, int): # Check if the level is valid
        raise ValueError(f"Invalid log level: {level}")
    logger.setLevel(numeric_level) # Update the level for the logger
    for handler in logger.handlers: # Update the level for all existing handlers
        handler.setLevel(numeric_level)



