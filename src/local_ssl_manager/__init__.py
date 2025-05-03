"""
Local SSL Manager - Create and manage SSL certificates for local development.

Tools for self-signed certificates, hosts file updates, and browser trust setup.
"""

__version__ = "0.1.10"

from .manager import LocalSSLManager

__all__ = ["LocalSSLManager"]
