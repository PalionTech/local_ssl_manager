"""
Logging utilities for Local SSL Manager.

This module provides a flexible logging system with support for:
- Application-wide logging
- Domain-specific logging with separate log files
"""

import logging
import sys
from pathlib import Path

# Configure root logger with NullHandler to prevent "No handler found" warnings
logging.getLogger("local_ssl_manager").addHandler(logging.NullHandler())


def configure_logging(logs_dir: Path) -> None:
    """
    Configure package-wide logging.

    Args:
        logs_dir: Directory where log files will be stored
    """
    # Ensure logs directory exists
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Configure main application logger
    logger = logging.getLogger("local_ssl_manager")

    # Remove existing handlers to avoid duplicates when reconfiguring
    for handler in list(logger.handlers):
        # Keep null handlers as a fallback
        if not isinstance(handler, logging.NullHandler):
            logger.removeHandler(handler)

    # Set level
    logger.setLevel(logging.INFO)

    # Console handler - user-facing logs (keep simple)
    console_handler = logging.StreamHandler(sys.stdout)
    console_format = logging.Formatter("%(levelname)s: %(message)s")
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler - detailed logs
    try:
        file_handler = logging.FileHandler(logs_dir / "ssl-manager.log")
        file_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not set up log file: {e}")


def get_domain_logger(domain: str, logs_dir: Path) -> logging.Logger:
    """
    Get a domain-specific logger.

    Args:
        domain: The domain name to create a logger for
        logs_dir: Directory where log files will be stored

    Returns:
        A configured logger for the specific domain
    """
    # Ensure logs directory exists
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Create a domain-specific logger
    logger_name = f"local_ssl_manager.domain.{domain}"
    logger = logging.getLogger(logger_name)

    # Remove existing handlers to avoid duplicates
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    # Configure the logger
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Don't propagate to parent

    # Add file handler for domain-specific logs
    log_file = logs_dir / f"{domain}.log"
    handler = logging.FileHandler(log_file)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def get_logger() -> logging.Logger:
    """
    Get the main application logger.

    Returns:
        The main application logger
    """
    return logging.getLogger("local_ssl_manager")
