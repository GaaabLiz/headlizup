import os
import logging
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Create logs directory if it doesn't exist
    log_dir = "/app/logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # Use a service identifier for the filename
    service_id = name.lower().replace("_", "-")
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(log_dir, f"{service_id}-{date_str}.log")
    
    # File handler (Daily rotation at midnight, keeps 7 days)
    file_handler = TimedRotatingFileHandler(
        log_file, 
        when="midnight", 
        interval=1, 
        backupCount=7,
        encoding="utf-8"
    )
    
    # Custom namer to ensure rotated files follow the format: service-YYYY-MM-DD.log
    def namer(default_name):
        base_dir, base_file = os.path.split(default_name)
        parts = base_file.split(".")
        # Default rotation name: service-YYYY-MM-DD.log.YYYY-MM-DD
        if len(parts) >= 3:
            rotation_date = parts[2]
            return os.path.join(base_dir, f"{service_id}-{rotation_date}.log")
        return default_name

    file_handler.namer = namer
    file_handler.setLevel(logging.DEBUG)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    
    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
    return logger
