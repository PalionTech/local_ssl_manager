"""
Local SSL Manager - Create and manage SSL certificates for local development.
Local SSL Manager - Create and manage SSL certificates for local development.

Tools for self-signed certificates, hosts file updates, and browser trust setup.
Tools for self-signed certificates, hosts file updates, and browser trust setup.
"""

__version__ = "0.1.8"

from .manager import LocalSSLManager

__all__ = ["LocalSSLManager"]
