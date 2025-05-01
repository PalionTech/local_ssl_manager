"""
Local SSL Manager - Easily create and manage SSL certificates for local development.

This package provides tools to create self-signed SSL certificates for local domains,
update hosts files, and configure browser trust.
"""

__version__ = "0.1.0"

from .manager import LocalSSLManager

__all__ = ["LocalSSLManager"]
