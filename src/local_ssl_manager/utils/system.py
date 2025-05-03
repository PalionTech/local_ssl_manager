"""
System utilities for cross-platform operations.

This module provides functions for system-level operations that need to work
across different operating systems (Windows, macOS, Linux), including:
- Hosts file management
- Privilege elevation
- Command execution
- Certificate trust store management
"""

import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List

# Import the logger
from ..logging import get_logger

logger = get_logger()


def check_admin_privileges() -> bool:
    """
    Check if the script is running with administrator/root privileges.

    Returns:
        True if running with admin privileges, False otherwise
    """
    try:
        system = platform.system()

        if system == "Windows":
            # On Windows, try to write to a protected location
            try:
                admin_check_file = Path("C:/Windows/Temp/admin_check.txt")
                admin_check_file.touch(exist_ok=True)
                admin_check_file.unlink()
                return True
            except (PermissionError, OSError):
                return False

        elif system == "Darwin" or system == "Linux":
            # On Unix-like systems, check effective user ID
            return os.geteuid() == 0

        else:
            # Fallback for other systems
            logger.warning(f"Unsupported system for privilege check: {system}")
            return False

    except Exception as e:
        logger.error(f"Error checking admin privileges: {e}")
        return False


def run_as_admin(args: List[str]) -> None:
    """
    Re-run the current script with administrative privileges.

    Args:
        args: Command line arguments to pass to the elevated process

    Raises:
        RuntimeError: If elevation fails
    """
    system = platform.system()

    try:
        if system == "Windows":
            # On Windows, use PowerShell to trigger UAC
            cmd = [
                "powershell",
                "Start-Process",
                sys.executable,
                "-ArgumentList",
                f'"{" ".join(args)}"',
                "-Verb",
                "RunAs",
            ]
            subprocess.run(cmd, check=True)

        elif system == "Darwin":  # macOS
            # On macOS, use a more reliable approach that preserves the environment
            # Instead of trying to restart with a module import, just use sudo directly
            cmd = ["sudo"] + args
            logger.info(f"Running command with sudo: {cmd}")
            subprocess.run(cmd, check=True)
            sys.exit(0)  # Exit after successful sudo execution

        elif system == "Linux":
            # On Linux, use sudo
            cmd = ["sudo"] + args
            subprocess.run(cmd, check=True)

        else:
            raise RuntimeError(f"Unsupported system for privilege elevation: {system}")

    except subprocess.SubprocessError as e:
        logger.error(f"Failed to run with admin privileges: {e}")
        raise RuntimeError(f"Failed to run with admin privileges: {e}")


def get_hosts_file_path() -> Path:
    """
    Get the path to the system hosts file.

    Returns:
        Path to the hosts file
    """
    system = platform.system()

    if system == "Windows":
        return Path(os.environ["WINDIR"]) / "System32" / "drivers" / "etc" / "hosts"
    else:  # macOS, Linux, and other Unix-like systems
        return Path("/etc/hosts")


def backup_hosts_file(backup_path: Path) -> None:
    """
    Create a backup of the system hosts file.

    Args:
        backup_path: Path where the backup will be stored

    Raises:
        RuntimeError: If backup fails
    """
    hosts_path = get_hosts_file_path()

    try:
        # Check if we need to create a backup
        if not backup_path.exists():
            # Need to handle permissions differently on different platforms
            system = platform.system()

            if system == "Windows" and not check_admin_privileges():
                # For Windows without admin, copy content
                with open(hosts_path, "r") as src, open(backup_path, "w") as dst:
                    dst.write(src.read())
            else:
                # For Unix or Windows with admin, use copy function
                import shutil

                shutil.copy2(hosts_path, backup_path)

            logger.info(f"Created hosts file backup at {backup_path}")

    except Exception as e:
        logger.error(f"Failed to backup hosts file: {e}")
        raise RuntimeError(f"Failed to backup hosts file: {e}")


def update_hosts_file(
    domain: str, ip_address: str = "127.0.0.1", remove: bool = False
) -> None:
    """
    Update the hosts file to add or remove a domain.

    Args:
        domain: Domain name to add or remove
        ip_address: IP address to associate with the domain
        remove: If True, remove the domain; if False, add it

    Raises:
        RuntimeError: If hosts file update fails
    """
    hosts_path = get_hosts_file_path()

    try:
        # Read current hosts file
        with open(hosts_path, "r") as f:
            hosts_content = f.read().splitlines()

        # Create a temporary file for the updated content
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as temp_file:
            temp_path = temp_file.name

            if remove:
                # Remove the domain entry
                for line in hosts_content:
                    # Skip lines containing both domain and IP
                    if not (domain in line and ip_address in line):
                        temp_file.write(line + "\n")

                logger.info(f"Removing {domain} from hosts file")

            else:
                # Check if domain already exists
                domain_exists = any(
                    domain in line and not line.strip().startswith("#")
                    for line in hosts_content
                )

                if not domain_exists:
                    # Write existing content
                    for line in hosts_content:
                        temp_file.write(line + "\n")

                    # Add new domain entry
                    temp_file.write(f"{ip_address} {domain}\n")
                    logger.info(f"Adding {domain} to hosts file with IP {ip_address}")

                else:
                    # Just keep existing content
                    for line in hosts_content:
                        temp_file.write(line + "\n")
                    logger.info(f"Domain {domain} already exists in hosts file")

        # Now copy the temp file to the hosts file (may require elevation)
        system = platform.system()

        if system == "Windows":
            if check_admin_privileges():
                # Direct copy if we have admin rights
                import shutil

                shutil.copy2(temp_path, hosts_path)
            else:
                # Try to use icacls to grant temporary permission
                try:
                    subprocess.run(
                        ["icacls", str(hosts_path), "/grant", f"{os.getlogin()}:F"],
                        check=True,
                        capture_output=True,
                    )
                    import shutil

                    shutil.copy2(temp_path, hosts_path)
                    # Restore permissions
                    subprocess.run(
                        ["icacls", str(hosts_path), "/reset"],
                        check=True,
                        capture_output=True,
                    )
                except subprocess.SubprocessError:
                    # If that fails, try with elevation
                    raise RuntimeError(
                        "Cannot update hosts file without admin privileges"
                    )

        else:  # macOS and Linux
            if check_admin_privileges():
                # Direct copy if we have admin rights
                import shutil

                shutil.copy2(temp_path, hosts_path)
            else:
                # Use sudo for elevation
                subprocess.run(["sudo", "cp", temp_path, str(hosts_path)], check=True)

    except Exception as e:
        logger.error(f"Failed to update hosts file: {e}")
        raise RuntimeError(f"Failed to update hosts file: {e}")

    finally:
        # Clean up the temporary file
        try:
            os.unlink(temp_path)
        except (OSError, NameError):
            pass


def check_domain_in_hosts(domain: str, ip_address: str = "127.0.0.1") -> bool:
    """
    Check if a domain is already in the hosts file.

    Args:
        domain: Domain name to check
        ip_address: IP address associated with the domain

    Returns:
        True if domain is in hosts file, False otherwise
    """
    hosts_path = get_hosts_file_path()

    try:
        with open(hosts_path, "r") as f:
            hosts_content = f.read().splitlines()

        # Check each line for the domain and IP
        for line in hosts_content:
            line = line.strip()

            # Skip comments
            if line.startswith("#"):
                continue

            # Check if line contains both domain and IP
            parts = line.split()
            if len(parts) >= 2 and parts[0] == ip_address and domain in parts[1:]:
                return True

        return False

    except Exception as e:
        logger.error(f"Failed to check hosts file: {e}")
        return False


def check_command_exists(command: str) -> bool:
    """
    Check if a command exists in the system PATH.

    Args:
        command: Command name to check

    Returns:
        True if command exists, False otherwise
    """
    try:
        # Different commands for different platforms
        if platform.system() == "Windows":
            # On Windows, use where command
            result = subprocess.run(
                ["where", command], check=False, capture_output=True, text=True
            )
        else:
            # On Unix-like systems, use which command
            result = subprocess.run(
                ["which", command], check=False, capture_output=True, text=True
            )

        # Command exists if return code is 0
        return result.returncode == 0

    except Exception:
        return False


def install_mkcert() -> bool:
    """
    Install mkcert if it's not already installed.

    Returns:
        True if mkcert is available after this function runs
    """
    # Check if mkcert is already installed
    if check_command_exists("mkcert"):
        logger.info("mkcert is already installed")
        return True

    logger.info("Attempting to install mkcert...")
    system = platform.system()

    try:
        if system == "Darwin":  # macOS
            # Try Homebrew first
            if check_command_exists("brew"):
                subprocess.run(["brew", "install", "mkcert"], check=True)
                return check_command_exists("mkcert")

        elif system == "Linux":
            # Try apt (Debian/Ubuntu)
            if check_command_exists("apt"):
                subprocess.run(["sudo", "apt", "update"], check=True)
                subprocess.run(["sudo", "apt", "install", "-y", "mkcert"], check=True)
                return check_command_exists("mkcert")

            # Try dnf (Fedora)
            elif check_command_exists("dnf"):
                subprocess.run(["sudo", "dnf", "install", "-y", "mkcert"], check=True)
                return check_command_exists("mkcert")

        # Provide instructions for manual installation if we couldn't install automatically
        if system == "Windows":
            logger.warning("mkcert is not installed. Please install it manually:")
            logger.warning("  - Using Chocolatey: choco install mkcert")
            logger.warning(
                "  - Or download from: https://github.com/FiloSottile/mkcert/releases"
            )
        else:
            logger.warning(
                "Could not install mkcert automatically. Please install it manually."
            )

        return False

    except Exception as e:
        logger.error(f"Failed to install mkcert: {e}")
        return False


def setup_browser_trust() -> bool:
    """
    Set up browser trust for self-signed certificates.

    This initializes mkcert's CA and adds it to system and browser trust stores.

    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure mkcert is installed
        if not check_command_exists("mkcert") and not install_mkcert():
            logger.error("Cannot set up browser trust without mkcert")
            return False

        # Initialize mkcert CA
        logger.info("Setting up root CA certificate...")
        subprocess.run(["mkcert", "-install"], check=True)

        # Get the CA root path
        ca_root = subprocess.run(
            ["mkcert", "-CAROOT"], capture_output=True, text=True, check=True
        ).stdout.strip()

        root_ca_path = Path(ca_root) / "rootCA.pem"

        if not root_ca_path.exists():
            logger.error(f"Root CA certificate not found at: {root_ca_path}")
            return False

        logger.info(f"Root CA certificate found at: {root_ca_path}")

        # On macOS, add to System keychain for better trust
        system = platform.system()
        if system == "Darwin" and check_admin_privileges():
            try:
                subprocess.run(
                    [
                        "security",
                        "add-trusted-cert",
                        "-d",
                        "-r",
                        "trustRoot",
                        "-k",
                        "/Library/Keychains/System.keychain",
                        str(root_ca_path),
                    ],
                    check=True,
                )
                logger.info("Added root certificate to System keychain")
            except subprocess.SubprocessError as e:
                logger.warning(f"Could not add to System keychain: {e}")

        logger.info("Root certificate successfully installed")
        return True

    except Exception as e:
        print("FAILED")
        logger.error(f"Failed to set up browser trust: {e}")
        logger.info("Continuing without extended browser trust...")
        return False
