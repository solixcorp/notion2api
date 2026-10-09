import logging
import json
import time
from datetime import datetime

class JsonFormatter(logging.Formatter):
    """Custom JSON log formatter."""
    def format(self, record):
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        
        # Merge custom extra fields
        if hasattr(record, "request_info"):
            log_record.update(record.request_info)
            
        # Include exception traceback if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_record, ensure_ascii=False)

def setup_logger(name="notion_opus"):
    """Configure and return the singleton global logger."""
    logger = logging.getLogger(name)
    
    # Guard against duplicate handlers
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(JsonFormatter())
        
        logger.addHandler(console_handler)
        
    return logger

# Global singleton logger instance
logger = setup_logger()
