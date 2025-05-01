"""
Logging utilities for Local SSL Manager.

This module provides a flexible logging system with support for:
- Application-wide logging
- Domain-specific logging with separate log files
- Configurable log levels and formats
"""

import logging
import sys
from pathlib import Path
from typing import Dict


class LoggingManager:
    """
    Manages application and domain-specific logging.

    This class handles the creation and configuration of loggers for both
    the main application and for specific domains being managed.
    """

    def __init__(self, logs_dir: Path):
        """
        Initialize the logging manager.

        Args:
            logs_dir: Directory where log files will be stored
        """
        self.logs_dir = logs_dir
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Configure the main application logger
        self._setup_main_logger()

        # Track configured domain loggers
        self.domain_loggers: Dict[str, logging.Logger] = {}

    def _setup_main_logger(self) -> None:
        """Configure the main application logger."""
        logger = logging.getLogger("local_ssl_manager")

        # Only configure if not already set up
        if not logger.handlers:
            logger.setLevel(logging.INFO)

            # Console handler - user-facing logs
            console_handler = logging.StreamHandler(sys.stdout)
            console_format = logging.Formatter("%(levelname)s: %(message)s")
            console_handler.setFormatter(console_format)
            logger.addHandler(console_handler)

            # File handler - complete logs
            file_handler = logging.FileHandler(self.logs_dir / "ssl-manager.log")
            file_format = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            file_handler.setFormatter(file_format)
            logger.addHandler(file_handler)

    def get_domain_logger(self, domain: str) -> logging.Logger:
        """
        Get or create a domain-specific logger.

        Args:
            domain: The domain name to create a logger for

        Returns:
            A configured logger for the specific domain
        """
        # Return existing logger if already configured
        if domain in self.domain_loggers:
            return self.domain_loggers[domain]

        # Create a new domain-specific logger
        logger_name = f"local_ssl_manager.domain.{domain}"
        logger = logging.getLogger(logger_name)

        # Reset any existing handlers to avoid duplicates
        if logger.handlers:
            for handler in logger.handlers:
                logger.removeHandler(handler)

        # Configure the domain logger
        logger.setLevel(logging.INFO)
        logger.propagate = False  # Don't propagate to parent/root logger

        # Add file handler for domain-specific logs
        log_file = self.logs_dir / f"{domain}.log"
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        # Store reference to configured logger
        self.domain_loggers[domain] = logger

        return logger

    def get_logger(self) -> logging.Logger:
        """
        Get the main application logger.

        Returns:
            The main application logger
        """
        return logging.getLogger("local_ssl_manager")


# Convenience function to get the main logger from anywhere
def get_logger() -> logging.Logger:
    """
    Get the main application logger.

    Returns:
        The main application logger
    """
    return logging.getLogger("local_ssl_manager")


# Configure null handler to prevent "No handler found" warnings
# when the package is imported without explicit logging configuration
logging.getLogger("local_ssl_manager").addHandler(logging.NullHandler())
