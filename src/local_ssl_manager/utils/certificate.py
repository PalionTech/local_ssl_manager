"""
Certificate utilities for creating and managing SSL certificates.

This module provides functions for:
- Creating self-signed certificates
- Verifying certificate validity
- Getting certificate information
"""

import os
import platform
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..logging import get_logger
from .system import check_command_exists, install_mkcert

logger = get_logger()


def get_mkcert_command() -> str:
    """
    Get the mkcert command, using full path if needed.

    Returns:
        The mkcert command to use
    """
    # Check if we have a stored path from recent installation
    if platform.system() == "Windows" and "MKCERT_PATH" in os.environ:
        mkcert_path = os.environ["MKCERT_PATH"]
        if Path(mkcert_path).exists():
            return mkcert_path

    # Otherwise just use 'mkcert' and hope it's in PATH
    return "mkcert"


def create_certificate(domain: str, cert_dir: Path) -> Tuple[Path, Path]:
    """
    Create a self-signed SSL certificate for a domain.

    Args:
        domain: The domain to create the certificate for
        cert_dir: Directory to store the certificate files

    Returns:
        Tuple of (certificate_path, key_path)

    Raises:
        RuntimeError: If certificate creation fails
    """
    # Ensure certificate directory exists
    cert_dir.mkdir(parents=True, exist_ok=True)

    # Define certificate and key paths
    cert_path = cert_dir / f"{domain}.crt"
    key_path = cert_dir / f"{domain}.key"

    # Ensure mkcert is available
    if not check_command_exists("mkcert") and not install_mkcert():
        raise RuntimeError("Cannot create certificate without mkcert")

    try:
        logger.info(f"Creating certificate for {domain}...")

        # Get the correct mkcert command
        mkcert_cmd = get_mkcert_command()

        # Create the certificate using mkcert
        subprocess.run(
            [
                mkcert_cmd,
                "-cert-file",
                str(cert_path),
                "-key-file",
                str(key_path),
                domain,
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        # Check if certificate files were actually created
        if not cert_path.exists() or not key_path.exists():
            raise RuntimeError("Certificate files were not created")

        logger.info(f"Certificate created at {cert_path}")
        logger.info(f"Private key created at {key_path}")

        return cert_path, key_path

    except subprocess.SubprocessError as e:
        error_msg = e.stderr if hasattr(e, "stderr") else str(e)
        logger.error(f"Failed to create certificate: {error_msg}")
        raise RuntimeError(f"Certificate creation failed: {error_msg}")

    except Exception as e:
        logger.error(f"Error creating certificate: {e}")
        raise RuntimeError(f"Certificate creation failed: {e}")


def create_multi_domain_certificate(
    domains: List[str], cert_dir: Path, name: str = "multi-domain"
) -> Tuple[Path, Path]:
    """
    Create a certificate for multiple domains.

    Args:
        domains: List of domains to include in the certificate
        cert_dir: Directory to store the certificate files
        name: Base name for the certificate files

    Returns:
        Tuple of (certificate_path, key_path)

    Raises:
        RuntimeError: If certificate creation fails
    """
    # Ensure certificate directory exists
    cert_dir.mkdir(parents=True, exist_ok=True)

    # Define certificate and key paths
    cert_path = cert_dir / f"{name}.crt"
    key_path = cert_dir / f"{name}.key"

    # Ensure mkcert is available
    if not check_command_exists("mkcert") and not install_mkcert():
        raise RuntimeError("Cannot create certificate without mkcert")

    try:
        logger.info(f"Creating multi-domain certificate for {len(domains)} domains...")

        # Get the correct mkcert command
        mkcert_cmd = get_mkcert_command()

        # Build the command: mkcert -cert-file CERT -key-file KEY domain1 domain2 ...
        cmd = [
            mkcert_cmd,
            "-cert-file",
            str(cert_path),
            "-key-file",
            str(key_path),
        ]
        cmd.extend(domains)

        # Create the certificate
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        # Check if certificate files were actually created
        if not cert_path.exists() or not key_path.exists():
            raise RuntimeError("Certificate files were not created")

        logger.info(f"Multi-domain certificate created at {cert_path}")

        return cert_path, key_path

    except subprocess.SubprocessError as e:
        error_msg = e.stderr if hasattr(e, "stderr") else str(e)
        logger.error(f"Failed to create multi-domain certificate: {error_msg}")
        raise RuntimeError(f"Certificate creation failed: {error_msg}")

    except Exception as e:
        logger.error(f"Error creating multi-domain certificate: {e}")
        raise RuntimeError(f"Certificate creation failed: {e}")


def check_certificate_validity(cert_path: Path) -> Dict[str, Any]:
    """
    Check the validity of a certificate and return its information.

    Args:
        cert_path: Path to the certificate file

    Returns:
        Dictionary with certificate information
    """
    if not cert_path.exists():
        return {"status": "invalid", "error": "Certificate file not found"}

    # Try to use OpenSSL for detailed certificate information
    from .system import check_command_exists, install_openssl

    if not check_command_exists("openssl") and not install_openssl():
        # Return basic info if OpenSSL unavailable
        return {
            "status": "unknown",
            "subject": f"CN={cert_path.stem}",
            "issuer": "mkcert development CA",
            "valid_from": "Install OpenSSL for details",
            "valid_to": "Install OpenSSL for details",
            "domains": [cert_path.stem],
        }

    try:
        # Get detailed certificate information using OpenSSL
        result = subprocess.run(
            ["openssl", "x509", "-in", str(cert_path), "-text", "-noout"],
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
            errors="replace",
        )

        output = result.stdout
        info = {
            "status": "valid",
            "subject": extract_field(output, "Subject:"),
            "issuer": extract_field(output, "Issuer:"),
            "valid_from": extract_field(output, "Not Before:"),
            "valid_to": extract_field(output, "Not After :"),
            "domains": extract_domains(output),
        }

        # Check if certificate is expired
        valid_to_str = info["valid_to"]
        if valid_to_str:
            try:
                import re
                from datetime import datetime

                date_match = re.search(
                    r"(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+\d{4})", valid_to_str
                )
                if date_match:
                    expiry_date = datetime.strptime(
                        date_match.group(1), "%b %d %H:%M:%S %Y"
                    )
                    if expiry_date < datetime.now():
                        info["status"] = "expired"
            except (ValueError, AttributeError):
                pass  # Keep status as valid if date parsing fails

        return info

    except subprocess.SubprocessError as e:
        logger.warning(f"OpenSSL certificate check failed: {e}")
        return {
            "status": "unknown",
            "subject": f"CN={cert_path.stem}",
            "issuer": "Unable to determine",
            "valid_from": "Unable to determine",
            "valid_to": "Unable to determine",
            "domains": [cert_path.stem],
        }

    except Exception as e:
        logger.error(f"Certificate validation error: {e}")
        return {"status": "invalid", "error": str(e)}


def extract_field(text: str, field_name: str) -> str:
    """
    Extract a field value from certificate text.

    Args:
        text: Certificate text
        field_name: Field name to extract

    Returns:
        The field value
    """
    for line in text.splitlines():
        if field_name in line:
            return line.split(field_name, 1)[1].strip()
    return ""


def extract_domains(text: str) -> List[str]:
    """
    Extract domain names from certificate text.

    Args:
        text: Certificate text from OpenSSL

    Returns:
        List of domain names
    """
    domains = []

    # Look for Subject Alternative Name section - simplified pattern
    san_match = re.search(
        r"X509v3 Subject Alternative Name:[\s\n]+(.*?)(?=$|X509v3)", text, re.DOTALL
    )
    if san_match:
        san_text = san_match.group(1).strip()
        # Extract domain names from DNS entries
        for entry in san_text.split(", "):
            if entry.startswith("DNS:"):
                domains.append(entry.split("DNS:", 1)[1])

    # Also look for common name (CN) in subject
    cn_match = re.search(r"Subject:.*?CN\s*=\s*([^\s,]+)", text, re.DOTALL)
    if cn_match and cn_match.group(1) not in domains:
        domains.append(cn_match.group(1))

    return domains


def get_certificate_expiry(cert_path: Path) -> Optional[str]:
    """
    Get the expiry date of a certificate.

    Args:
        cert_path: Path to the certificate file

    Returns:
        Expiry date as string, or None if certificate is invalid
    """
    cert_info = check_certificate_validity(cert_path)
    return cert_info.get("valid_to") if cert_info["status"] == "valid" else None
