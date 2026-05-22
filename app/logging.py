import logging
import sys

# Configure basic logging format
def setup_logging(level=logging.INFO):
    """Setup simple console logging"""
    
    # Create formatter with colors for console
    class ColoredFormatter(logging.Formatter):
        COLORS = {
            'DEBUG': '\033[36m',     # Cyan
            'INFO': '\033[32m',      # Green
            'WARNING': '\033[33m',   # Yellow
            'ERROR': '\033[31m',     # Red
            'CRITICAL': '\033[35m',  # Magenta
        }
        RESET = '\033[0m'
        
        def format(self, record):
            log_message = super().format(record)
            color = self.COLORS.get(record.levelname, self.RESET)
            return f"{color}{log_message}{self.RESET}"
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # Set formatter
    formatter = ColoredFormatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    
    # Set specific loggers
    logging.getLogger('uvicorn.access').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    
    return root_logger

def get_logger(name: str):
    """Get a logger instance for a specific module"""
    return logging.getLogger(name)

class RequestLogger:
    """Simple request logging middleware"""
    
    async def log_request(self, request, call_next):
        logger = get_logger("api")
        
        # Log incoming request
        logger.info(f"→ {request.method} {request.url.path}")
        
        # Process request
        response = await call_next(request)
        
        # Log response status
        status_color = "\033[32m" if response.status_code < 400 else "\033[31m"
        logger.info(f"← {response.status_code} {request.method} {request.url.path}{status_color}\033[0m")
        
        return response