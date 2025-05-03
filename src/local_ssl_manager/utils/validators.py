"""
Validation utilities for domain names and certificate parameters.

This module provides functions to validate domain names and other inputs
used in certificate creation and management.
"""

import re
from pathlib import Path
from typing import Optional, Tuple


def validate_domain(domain: str) -> Tuple[bool, Optional[str]]:
    """
    Validate that a domain name follows proper formatting rules.

    Args:
        domain: The domain name to validate

    Returns:
        A tuple of (is_valid, error_message)
        If the domain is valid, error_message will be None
    """
    if not domain:
        return False, "Domain name cannot be empty"

    if len(domain) > 255:
        return False, "Domain name exceeds maximum length (255 characters)"

    # Match most common domain patterns
    # This handles standard domains like example.com, test.local, etc.
    pattern = r"""
    ^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)
    +[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$
    """

    if not re.match(pattern, domain, re.VERBOSE):
        return False, "Invalid domain name format"

    # Check each label (parts between dots)
    labels = domain.split(".")
    for label in labels:
        if not label:  # Empty label (e.g., "domain..com")
            return False, "Domain labels cannot be empty"

        if label.startswith("-") or label.endswith("-"):
            return False, "Domain labels cannot start or end with hyphens"

        if not all(c.isalnum() or c == "-" for c in label):
            return (
                False,
                "Domain labels can only contain alphanumeric characters and hyphens",
            )

    # if not labels[-1] == "local":
    #    return False, "Domains have to end with .local for local ssl management"

    return True, None


def validate_ip_address(ip: str) -> Tuple[bool, Optional[str]]:
    """
    Validate an IP address.

    Args:
        ip: The IP address to validate

    Returns:
        A tuple of (is_valid, error_message)
        If the IP is valid, error_message will be None
    """
    # Simple IPv4 validation
    pattern = r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$"
    match = re.match(pattern, ip)

    if not match:
        return False, "Invalid IP address format"

    # Check each octet is in valid range (0-255)
    for octet in match.groups():
        if int(octet) > 255:
            return False, "IP address octets must be between 0 and 255"

    return True, None


def validate_path(path: str) -> Tuple[bool, Optional[str]]:
    """
    Validate that a file path is properly formatted.

    Args:
        path: The file path to validate

    Returns:
        A tuple of (is_valid, error_message)
    """
    if not path:
        return False, "Path cannot be empty"

    # Use built-in path validation functionality
    try:
        # Convert to a Path object to validate basic structure
        Path(path)

        # Check for characters that are universally problematic in paths
        # These are the characters that are invalid on most filesystems
        invalid_chars = '<>|*?"'
        for char in invalid_chars:
            if char in path:
                return False, f"Path contains invalid character: '{char}'"

        return True, None
    except ValueError as e:
        return False, f"Invalid path format: {str(e)}"
