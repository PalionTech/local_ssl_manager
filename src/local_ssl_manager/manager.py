"""
Core SSL Manager implementation.

This module provides the main LocalSSLManager class, which coordinates
all certificate management operations, hosts file updates, and logging.
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .logging import LoggingManager
from .utils.certificate import (
    check_certificate_validity,
    create_certificate,
    create_multi_domain_certificate,
)
from .utils.system import (
    backup_hosts_file,
    check_domain_in_hosts,
    setup_browser_trust,
    update_hosts_file,
)
from .utils.validators import validate_domain, validate_ip_address


class LocalSSLManager:
    """
    Main class for managing local SSL certificates.

    This class provides methods to:
    - Create SSL certificates for local domains
    - Delete existing certificates
    - List all managed certificates
    - Export and import certificates
    - Update hosts file entries
    """

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize the SSL Manager.

        Args:
            base_dir: Optional base directory for storing certificates and configuration.
                    If not provided, uses ~/.local-ssl-manager or the directory
                    specified by the SSL_MANAGER_HOME environment variable.
        """
        # Determine base directory
        if base_dir is None:
            # Check for environment variable first
            env_dir = os.environ.get("SSL_MANAGER_HOME")
            if env_dir:
                self.base_dir = Path(env_dir)
            else:
                # If running as sudo, use the original user's home
                sudo_user = os.environ.get("SUDO_USER")
                if sudo_user and os.geteuid() == 0:  # Running as root via sudo
                    import pwd

                    # Get the original user's home directory
                    user_home = Path(pwd.getpwnam(sudo_user).pw_dir)
                    self.base_dir = user_home / ".local-ssl-manager"
                else:
                    self.base_dir = Path.home() / ".local-ssl-manager"
        else:
            self.base_dir = base_dir

        # Set up subdirectories
        self.certs_dir = self.base_dir / "certs"
        self.logs_dir = self.base_dir / "logs"
        self.config_dir = self.base_dir / "config"
        self.hosts_backup = self.base_dir / "hosts.backup"
        self.metadata_file = self.config_dir / "certificates.json"

        # Create directories
        self._setup_directories()

        # Initialize logging
        self.logging_manager = LoggingManager(self.logs_dir)
        self.logger = self.logging_manager.get_logger()

        self.logger.info(
            f"SSL Manager initialized with base directory: {self.base_dir}"
        )

    def _setup_directories(self) -> None:
        """Create the necessary directories for certificates and configuration."""
        for directory in [
            self.base_dir,
            self.certs_dir,
            self.logs_dir,
            self.config_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)

        if not self.metadata_file.exists():
            self._save_metadata({})

    def _save_metadata(self, metadata: Dict) -> None:
        """
        Save certificate metadata to JSON file.

        Args:
            metadata: Dictionary containing certificate metadata
        """
        with open(self.metadata_file, "w") as f:
            json.dump(metadata, f, indent=2, default=str)

    def _load_metadata(self) -> Dict:
        """
        Load certificate metadata from JSON file.

        Returns:
            Dictionary containing certificate metadata
        """
        if not self.metadata_file.exists():
            return {}

        with open(self.metadata_file, "r") as f:
            return json.load(f)

    def check_domain_exists(self, domain: str) -> bool:
        """
        Check if a domain is already configured.

        Args:
            domain: Domain name to check

        Returns:
            True if domain already exists, False otherwise
        """
        # Check in our metadata
        metadata = self._load_metadata()
        if domain in metadata:
            return True

        # Check in hosts file
        return check_domain_in_hosts(domain)

    def setup_local_domain(
        self, domain: str, ip_address: str = "127.0.0.1"
    ) -> Dict[str, str]:
        """
        Set up a local domain with SSL certificate.

        This method:
        1. Validates the domain name
        2. Sets up browser trust
        3. Updates the hosts file
        4. Creates an SSL certificate
        5. Updates metadata

        Args:
            domain: Domain name to set up
            ip_address: IP address to associate with the domain

        Returns:
            Dictionary with certificate information

        Raises:
            ValueError: If domain is invalid or already exists
        """
        # Validate domain name
        is_valid, error = validate_domain(domain)
        if not is_valid:
            raise ValueError(f"Invalid domain name: {error}")

        # Validate IP address
        is_valid_ip, ip_error = validate_ip_address(ip_address)
        if not is_valid_ip:
            raise ValueError(f"Invalid IP address: {ip_error}")

        # Check if domain already exists
        if self.check_domain_exists(domain):
            raise ValueError(f"Domain {domain} is already configured")

        # Get domain-specific logger
        domain_logger = self.logging_manager.get_domain_logger(domain)

        self.logger.info(f"Setting up domain {domain}...")
        domain_logger.info(f"Starting setup for domain {domain}")

        # Set up browser trust
        trust_result = setup_browser_trust()
        domain_logger.info(
            f"Browser trust setup {'successful' if trust_result else 'failed'}"
        )

        # Back up hosts file before modification
        backup_hosts_file(self.hosts_backup)
        domain_logger.info(f"Backed up hosts file to {self.hosts_backup}")

        # Update hosts file
        update_hosts_file(domain, ip_address)
        domain_logger.info(f"Added {domain} to hosts file with IP {ip_address}")

        # Create SSL certificate
        try:
            cert_path, key_path = create_certificate(domain, self.certs_dir)
            domain_logger.info(f"Created SSL certificate at {cert_path}")
        except Exception:
            # Rollback hosts file change if certificate creation fails
            try:
                update_hosts_file(domain, ip_address, remove=True)
                domain_logger.info(
                    "Rolled back hosts file changes due to certificate creation failure"
                )
            except Exception as rollback_error:
                domain_logger.error(
                    f"Failed to rollback hosts file change: {rollback_error}"
                )

            # Re-raise the original error
            raise

        # Get log file path
        log_path = self.logs_dir / f"{domain}.log"

        # Update metadata
        metadata = self._load_metadata()
        metadata[domain] = {
            "created_at": datetime.now().isoformat(),
            "ip_address": ip_address,
            "cert_path": str(cert_path),
            "key_path": str(key_path),
            "log_path": str(log_path),
            "status": "active",
        }
        self._save_metadata(metadata)
        domain_logger.info("Updated certificate metadata")

        # Log completion
        domain_logger.info("Domain setup completed successfully")
        self.logger.info(f"Domain {domain} setup complete")

        # Return certificate information
        return {
            "domain": domain,
            "ip_address": ip_address,
            "cert_path": str(cert_path),
            "key_path": str(key_path),
            "log_path": str(log_path),
        }

    def setup_multi_domain(
        self,
        domains: List[str],
        ip_address: str = "127.0.0.1",
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Set up multiple domains with a single SSL certificate.

        Args:
            domains: List of domain names to set up
            ip_address: IP address to associate with the domains
            name: Optional name for the certificate files

        Returns:
            Dictionary with certificate information

        Raises:
            ValueError: If any domain is invalid or already exists
        """
        if not domains:
            raise ValueError("No domains provided")

        # Determine certificate name
        if name is None:
            # Use the first domain as the name
            name = domains[0]

        # Get domain-specific logger
        domain_logger = self.logging_manager.get_domain_logger(name)

        self.logger.info(f"Setting up multi-domain {name}...")
        domain_logger.info(f"Starting setup for multi-domain {name}")

        # Validate all domains
        for domain in domains:
            is_valid, error = validate_domain(domain)
            if not is_valid:
                raise ValueError(f"Invalid domain name '{domain}': {error}")

            if self.check_domain_exists(domain):
                raise ValueError(f"Domain {domain} is already configured")

        # Validate IP address
        is_valid_ip, ip_error = validate_ip_address(ip_address)
        if not is_valid_ip:
            raise ValueError(f"Invalid IP address: {ip_error}")

        self.logger.info(
            f"Setting up {len(domains)} domains with shared certificate..."
        )

        # Set up browser trust
        trust_result = setup_browser_trust()
        domain_logger.info(
            f"Browser trust setup {'successful' if trust_result else 'failed'}"
        )

        # Back up hosts file
        backup_hosts_file(self.hosts_backup)
        domain_logger.info(f"Backed up hosts file to {self.hosts_backup}")

        # Update hosts file for all domains
        for domain in domains:
            update_hosts_file(domain, ip_address)

        # Create multi-domain certificate
        try:
            cert_path, key_path = create_multi_domain_certificate(
                domains, self.certs_dir, name=name
            )
            domain_logger.info(f"Created SSL certificate at {cert_path}")
        except Exception:
            # Rollback hosts file change if certificate creation fails
            try:
                for domain in domains:
                    update_hosts_file(domain, ip_address, remove=True)
                domain_logger.info(
                    "Rolled back hosts file changes due to certificate creation failure"
                )
            except Exception as rollback_error:
                domain_logger.error(
                    f"Failed to rollback hosts file change: {rollback_error}"
                )

            # Re-raise the original error
            raise

        # Update metadata for each domain
        metadata = self._load_metadata()

        for domain in domains:
            log_path = self.logs_dir / f"{domain}.log"

            metadata[domain] = {
                "created_at": datetime.now().isoformat(),
                "ip_address": ip_address,
                "cert_path": str(cert_path),
                "key_path": str(key_path),
                "log_path": str(log_path),
                "status": "active",
                "multi_domain": True,
                "multi_domain_name": name,
                "shared_with": domains,
            }

            domain_logger.info(
                f"Domain {domain} added to multi-domain certificate {name}"
            )

        self._save_metadata(metadata)

        self.logger.info(
            f"Multi-domain setup {name} complete for {len(domains)} domains"
        )

        return {
            "domains": domains,
            "ip_address": ip_address,
            "cert_path": str(cert_path),
            "key_path": str(key_path),
            "name": name,
        }

    def get_certificates(self) -> List[Dict[str, Any]]:
        """
        Get information about all managed certificates.

        Returns:
            List of certificate information dictionaries
        """
        metadata = self._load_metadata()
        certificates = []

        for domain, data in metadata.items():
            # Check if certificate file exists
            cert_path = Path(data["cert_path"])

            if cert_path.exists():
                # Check certificate validity
                validity = check_certificate_validity(cert_path)

                # Create certificate info dictionary
                cert_info = {
                    "domain": domain,
                    "created_at": (
                        datetime.fromisoformat(data["created_at"])
                        if isinstance(data["created_at"], str)
                        else data["created_at"]
                    ),
                    "ip_address": data.get("ip_address", "127.0.0.1"),
                    "cert_path": data["cert_path"],
                    "key_path": data["key_path"],
                    "log_path": data.get(
                        "log_path", str(self.logs_dir / f"{domain}.log")
                    ),
                    "status": validity["status"],
                    "valid_from": validity.get("valid_from", ""),
                    "valid_to": validity.get("valid_to", ""),
                    "multi_domain": data.get("multi_domain", False),
                }

                # Add domains list if this is a multi-domain certificate
                if cert_info["multi_domain"]:
                    cert_info["shared_with"] = data.get("shared_with", [])

                certificates.append(cert_info)
            else:
                # Certificate file not found
                certificates.append(
                    {
                        "domain": domain,
                        "created_at": (
                            datetime.fromisoformat(data["created_at"])
                            if isinstance(data["created_at"], str)
                            else data["created_at"]
                        ),
                        "cert_path": data["cert_path"],
                        "status": "missing",
                        "error": "Certificate file not found",
                    }
                )

        return certificates

    def get_domain_hierarchy(self) -> List[Tuple[str, datetime]]:
        """
        Get a hierarchical list of domains with creation date.

        Returns:
            List of (domain, created_at) tuples sorted by domain hierarchy
        """
        metadata = self._load_metadata()
        domains = []

        for domain, data in metadata.items():
            created_at = (
                datetime.fromisoformat(data["created_at"])
                if isinstance(data["created_at"], str)
                else data["created_at"]
            )
            domains.append((domain, created_at))

        # Sort by domain hierarchy (number of dots) and then alphabetically
        return sorted(domains, key=lambda x: (x[0].count("."), x[0]))

    def delete_certificate(self, domain: str) -> bool:
        """
        Delete a certificate and remove domain from hosts file.

        Args:
            domain: Domain name to delete

        Returns:
            True if successful, False otherwise

        Raises:
            ValueError: If certificate not found
        """
        metadata = self._load_metadata()

        if domain not in metadata:
            raise ValueError(f"Certificate for {domain} not found")

        # Get domain logger before we delete anything
        domain_logger = self.logging_manager.get_domain_logger(domain)
        domain_logger.info(f"Starting deletion of certificate for {domain}")

        # Get certificate data
        cert_data = metadata[domain]
        ip_address = cert_data.get("ip_address", "127.0.0.1")

        try:
            # For multi-domain certificates, we need special handling
            is_multi_domain = cert_data.get("multi_domain", False)

            if is_multi_domain:
                # Get list of domains sharing this certificate
                shared_with = cert_data.get("shared_with", [])

                # Remove this domain from hosts file
                update_hosts_file(domain, ip_address, remove=True)
                domain_logger.info(f"Removed {domain} from hosts file")

                # Remove from metadata
                del metadata[domain]
                self._save_metadata(metadata)
                domain_logger.info("Removed domain from metadata")

                # Only delete certificate files if this is the last domain using them
                if not any(d in metadata for d in shared_with if d != domain):
                    cert_path = Path(cert_data["cert_path"])
                    key_path = Path(cert_data["key_path"])

                    if cert_path.exists():
                        cert_path.unlink()
                        domain_logger.info(f"Deleted certificate file: {cert_path}")

                    if key_path.exists():
                        key_path.unlink()
                        domain_logger.info(f"Deleted key file: {key_path}")
                else:
                    domain_logger.info(
                        "Certificate files not deleted as they are still used by other domains"
                    )
            else:
                # Standard single-domain certificate
                cert_path = Path(cert_data["cert_path"])
                key_path = Path(cert_data["key_path"])

                # Delete certificate files
                if cert_path.exists():
                    cert_path.unlink()
                    domain_logger.info(f"Deleted certificate file: {cert_path}")

                if key_path.exists():
                    key_path.unlink()
                    domain_logger.info(f"Deleted key file: {key_path}")

                # Remove domain from hosts file
                update_hosts_file(domain, ip_address, remove=True)
                domain_logger.info(f"Removed {domain} from hosts file")

                # Remove from metadata
                del metadata[domain]
                self._save_metadata(metadata)
                domain_logger.info("Removed certificate from metadata")

            # Log final deletion
            domain_logger.info(f"Certificate for {domain} has been deleted")
            self.logger.info(f"Certificate for {domain} deleted successfully")

            return True

        except Exception as e:
            domain_logger.error(f"Error deleting certificate: {e}")
            self.logger.error(f"Failed to delete certificate for {domain}: {e}")
            return False

    def export_certificate(self, domain: str, export_dir: Path) -> Tuple[Path, Path]:
        """
        Export a certificate to a specified directory.

        Args:
            domain: Domain name to export
            export_dir: Directory to export to

        Returns:
            Tuple of (exported_cert_path, exported_key_path)

        Raises:
            ValueError: If certificate not found
        """
        metadata = self._load_metadata()

        if domain not in metadata:
            raise ValueError(f"Certificate for {domain} not found")

        # Ensure export directory exists
        export_dir.mkdir(parents=True, exist_ok=True)

        # Get certificate paths
        cert_data = metadata[domain]
        cert_path = Path(cert_data["cert_path"])
        key_path = Path(cert_data["key_path"])

        if not cert_path.exists():
            raise FileNotFoundError(f"Certificate file not found: {cert_path}")

        if not key_path.exists():
            raise FileNotFoundError(f"Key file not found: {key_path}")

        # Define export paths
        export_cert_path = export_dir / f"{domain}.crt"
        export_key_path = export_dir / f"{domain}.key"

        # Copy files
        shutil.copy2(cert_path, export_cert_path)
        shutil.copy2(key_path, export_key_path)

        self.logger.info(f"Exported certificate for {domain} to {export_dir}")

        return export_cert_path, export_key_path

    def import_certificate(
        self,
        domain: str,
        cert_path: Path,
        key_path: Path,
        ip_address: str = "127.0.0.1",
    ) -> Dict[str, str]:
        """
        Import an existing certificate.

        Args:
            domain: Domain name for the certificate
            cert_path: Path to the certificate file
            key_path: Path to the key file
            ip_address: IP address to associate with the domain

        Returns:
            Dictionary with certificate information

        Raises:
            ValueError: If domain is invalid or already exists
            FileNotFoundError: If certificate or key file not found
        """
        # Validate domain name
        is_valid, error = validate_domain(domain)
        if not is_valid:
            raise ValueError(f"Invalid domain name: {error}")

        # Validate IP address
        is_valid_ip, ip_error = validate_ip_address(ip_address)
        if not is_valid_ip:
            raise ValueError(f"Invalid IP address: {ip_error}")

        # Check if domain already exists
        if self.check_domain_exists(domain):
            raise ValueError(f"Domain {domain} is already configured")

        # Check if files exist
        if not cert_path.exists():
            raise FileNotFoundError(f"Certificate file not found: {cert_path}")

        if not key_path.exists():
            raise FileNotFoundError(f"Key file not found: {key_path}")

        # Get domain-specific logger
        domain_logger = self.logging_manager.get_domain_logger(domain)
        domain_logger.info(f"Starting import of certificate for {domain}")

        # Copy certificate files to our directory
        local_cert_path = self.certs_dir / f"{domain}.crt"
        local_key_path = self.certs_dir / f"{domain}.key"

        shutil.copy2(cert_path, local_cert_path)
        shutil.copy2(key_path, local_key_path)

        domain_logger.info(f"Copied certificate to {local_cert_path}")
        domain_logger.info(f"Copied key to {local_key_path}")

        # Update hosts file
        update_hosts_file(domain, ip_address)
        domain_logger.info(f"Added {domain} to hosts file with IP {ip_address}")

        # Get log file path
        log_path = self.logs_dir / f"{domain}.log"

        # Check certificate validity
        validity = check_certificate_validity(local_cert_path)

        # Update metadata
        metadata = self._load_metadata()
        metadata[domain] = {
            "created_at": datetime.now().isoformat(),
            "imported_at": datetime.now().isoformat(),
            "ip_address": ip_address,
            "cert_path": str(local_cert_path),
            "key_path": str(local_key_path),
            "log_path": str(log_path),
            "status": validity["status"],
            "imported": True,
            "original_cert_path": str(cert_path),
            "original_key_path": str(key_path),
        }
        self._save_metadata(metadata)
        domain_logger.info("Updated certificate metadata")

        # Log completion
        domain_logger.info("Certificate import completed successfully")
        self.logger.info(f"Imported certificate for {domain}")

        # Return certificate information
        return {
            "domain": domain,
            "ip_address": ip_address,
            "cert_path": str(local_cert_path),
            "key_path": str(local_key_path),
            "log_path": str(log_path),
            "imported": True,
            "status": validity["status"],
        }
