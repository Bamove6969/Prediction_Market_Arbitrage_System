"""
Centralized Logging Module for Prediction Market Arbitrage System

Features:
- Structured JSON logging
- Multiple output handlers (console, file, syslog)
- Log levels by component
- Real-time log streaming support
- WebSocket log broadcasting
"""

import logging
import json
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler

# Color codes for console
class ColoredFormatter(logging.Formatter):
    """Colored console formatter"""
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logger(
    name: str = "arbitrage",
    level: str = "INFO",
    log_file: Optional[str] = None,
    enable_console: bool = True,
    json_format: bool = False
) -> logging.Logger:
    """
    Setup a configured logger with multiple handlers
    
    Args:
        name: Logger name
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
        enable_console: Enable console output
        json_format: Use JSON formatting for logs
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    logger.handlers.clear()

    # Prevent propagation to root logger
    logger.propagate = False

    # Common format
    if json_format:
        format_str = '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}'
    else:
        format_str = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'

    # Console handler with colors
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(ColoredFormatter(format_str, datefmt='%H:%M:%S'))
        logger.addHandler(console_handler)

    # File handler with rotation
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10_000_000,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(format_str, datefmt='%Y-%m-%d %H:%M:%S'))
        logger.addHandler(file_handler)

    return logger


# Pre-configured loggers for different components
def get_scanner_logger():
    return setup_logger("arbitrage.scanner", os.getenv("LOG_LEVEL", "INFO"))

def get_fetcher_logger():
    return setup_logger("arbitrage.fetchers", os.getenv("LOG_LEVEL", "INFO"))

def get_llm_logger():
    return setup_logger("arbitrage.llm", os.getenv("LOG_LEVEL", "INFO"))

def get_api_logger():
    return setup_logger("arbitrage.api", os.getenv("LOG_LEVEL", "INFO"))


# ===========================================
# Real-time Log Streaming Class
# ===========================================
class LogStreamer:
    """Stream logs to WebSocket clients in real-time"""
    
    def __init__(self):
        self._subscribers = set()
    
    def subscribe(self, callback):
        """Add a subscriber callback"""
        self._subscribers.add(callback)
    
    def unsubscribe(self, callback):
        """Remove a subscriber"""
        self._subscribers.discard(callback)
    
    def broadcast(self, record: logging.LogRecord):
        """Broadcast log record to all subscribers"""
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        for callback in self._subscribers:
            try:
                callback(log_entry)
            except Exception:
                pass


# Global log streamer instance
log_streamer = LogStreamer()


# ===========================================
# Structured Logging Helpers
# ===========================================
def log_scan_progress(logger: logging.Logger, phase: str, progress: int, total: int, details: str = ""):
    """Log scan progress in structured format"""
    logger.info(f"SCAN | {phase} | {progress}/{total} | {details}")

def log_market_count(logger: logging.Logger, platform: str, count: int):
    logger.info(f"MARKET_COUNT | platform={platform} | count={count}")

def log_match_found(logger: logging.Logger, match_id: str, roi: float, platforms: tuple):
    logger.info(f"MATCH_FOUND | id={match_id} | roi={roi:.2f}% | platforms={platforms[0]}-{platforms[1]}")

def log_error(logger: logging.Logger, context: str, error: Exception):
    logger.error(f"ERROR | context={context} | error={type(error).__name__} | message={str(error)}")


# Initialize default logger
default_logger = setup_logger(
    "arbitrage",
    level=os.getenv("LOG_LEVEL", "INFO"),
    log_file=os.getenv("LOG_FILE", "/tmp/arbitrage.log")
)