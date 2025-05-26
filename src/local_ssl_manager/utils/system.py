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
            subprocess.run(cmd, check=True, encoding="utf-8", errors="replace")

        elif system == "Darwin":  # macOS
            # On macOS, use a more reliable approach that preserves the environment
            # Instead of trying to restart with a module import, just use sudo directly
            cmd = ["sudo"] + args
            logger.info(f"Running command with sudo: {cmd}")
            subprocess.run(cmd, check=True, encoding="utf-8", errors="replace")
            sys.exit(0)  # Exit after successful sudo execution

        elif system == "Linux":
            # On Linux, use sudo
            cmd = ["sudo"] + args
            subprocess.run(cmd, check=True, encoding="utf-8", errors="replace")

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
                        encoding="utf-8",
                        errors="replace",
                    )
                    import shutil

                    shutil.copy2(temp_path, hosts_path)
                    # Restore permissions
                    subprocess.run(
                        ["icacls", str(hosts_path), "/reset"],
                        check=True,
                        capture_output=True,
                        encoding="utf-8",
                        errors="replace",
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
                subprocess.run(
                    ["sudo", "cp", temp_path, str(hosts_path)],
                    check=True,
                    encoding="utf-8",
                    errors="replace",
                )

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
                ["where", command],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        else:
            # On Unix-like systems, use which command
            result = subprocess.run(
                ["which", command],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

        # Command exists if return code is 0
        return result.returncode == 0

    except Exception:
        return False


def _download_mkcert_windows() -> str:
    """
    Download mkcert directly from GitHub releases for Windows.

    Returns:
        Path to the installed mkcert executable, or empty string if failed
    """
    import shutil
    import urllib.request

    try:
        # Determine architecture
        import struct

        is_64bit = struct.calcsize("P") * 8 == 64
        arch = "amd64" if is_64bit else "386"

        # mkcert download URL (using a stable version)
        version = "v1.4.4"  # Latest stable version as of 2023
        filename = f"mkcert-{version}-windows-{arch}.exe"
        url = f"https://github.com/FiloSottile/mkcert/releases/download/{version}/{filename}"

        # Download to temp directory
        temp_dir = Path(tempfile.gettempdir()) / "mkcert_download"
        temp_dir.mkdir(exist_ok=True)
        download_path = temp_dir / "mkcert.exe"

        logger.info(f"Downloading mkcert from {url}...")
        urllib.request.urlretrieve(url, download_path)

        # Try to move to a directory in PATH
        # First, try Program Files
        program_files = Path(os.environ.get("ProgramFiles", "C:\\Program Files"))
        target_dir = program_files / "mkcert"

        try:
            target_dir.mkdir(exist_ok=True)
            target_path = target_dir / "mkcert.exe"
            shutil.move(str(download_path), str(target_path))

            # Add to PATH for current session
            current_path = os.environ.get("PATH", "")
            if str(target_dir) not in current_path:
                os.environ["PATH"] = f"{current_path};{target_dir}"

            logger.info(f"mkcert installed to {target_path}")

            # Store the path globally so we can use it later
            os.environ["MKCERT_PATH"] = str(target_path)

            return str(target_path)

        except (PermissionError, OSError):
            # If we can't write to Program Files, try user's local directory
            local_dir = Path.home() / ".local" / "bin"
            local_dir.mkdir(parents=True, exist_ok=True)
            target_path = local_dir / "mkcert.exe"

            shutil.move(str(download_path), str(target_path))

            # Add to PATH for current session
            current_path = os.environ.get("PATH", "")
            if str(local_dir) not in current_path:
                os.environ["PATH"] = f"{current_path};{local_dir}"

            logger.info(f"mkcert installed to {target_path}")

            # Store the path globally so we can use it later
            os.environ["MKCERT_PATH"] = str(target_path)

            return str(target_path)

    except Exception as e:
        logger.error(f"Failed to download mkcert: {e}")
        return ""
    finally:
        # Clean up temp directory
        if "temp_dir" in locals() and temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.error(f"Failed to clean up temporary files: {e}")
                pass


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
                subprocess.run(
                    ["brew", "install", "mkcert"],
                    check=True,
                    encoding="utf-8",
                    errors="replace",
                )
                return check_command_exists("mkcert")

        elif system == "Linux":
            # Try apt (Debian/Ubuntu)
            if check_command_exists("apt"):
                subprocess.run(
                    ["sudo", "apt", "update"],
                    check=True,
                    encoding="utf-8",
                    errors="replace",
                )
                subprocess.run(
                    ["sudo", "apt", "install", "-y", "mkcert"],
                    check=True,
                    encoding="utf-8",
                    errors="replace",
                )
                return check_command_exists("mkcert")

            # Try dnf (Fedora)
            elif check_command_exists("dnf"):
                subprocess.run(
                    ["sudo", "dnf", "install", "-y", "mkcert"],
                    check=True,
                    encoding="utf-8",
                    errors="replace",
                )
                return check_command_exists("mkcert")

        elif system == "Windows":
            # Try Chocolatey first
            if check_command_exists("choco"):
                logger.info("Found Chocolatey, installing mkcert...")
                try:
                    subprocess.run(
                        ["choco", "install", "mkcert", "-y"],
                        check=True,
                        encoding="utf-8",
                        errors="replace",
                    )
                    return check_command_exists("mkcert")
                except subprocess.SubprocessError:
                    logger.warning(
                        "Chocolatey installation failed, trying direct download..."
                    )

            # Direct download from GitHub
            mkcert_path = _download_mkcert_windows()
            return bool(mkcert_path)

        # Provide instructions for manual installation if we couldn't install automatically
        else:
            logger.warning(
                "Could not install mkcert automatically. Please install it manually."
            )

        return False

    except Exception as e:
        logger.error(f"Failed to install mkcert: {e}")
        return False


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


def _run_mkcert_install_elevated_windows(mkcert_cmd: str) -> bool:
    """
    Try to run mkcert -install with elevation on Windows.

    Returns:
        True if successful, False otherwise
    """
    try:
        # Create a temporary PowerShell script to run mkcert -install as admin
        ps_script = f"""
        Start-Process -FilePath "{mkcert_cmd}" -ArgumentList "-install" -Verb RunAs -Wait
        """

        # Run the PowerShell script
        subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        # Check if it worked by verifying the CA exists
        ca_root_result = subprocess.run(
            [mkcert_cmd, "-CAROOT"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        if ca_root_result.returncode == 0:
            ca_root = ca_root_result.stdout.strip()
            root_ca_path = Path(ca_root) / "rootCA.pem"
            return root_ca_path.exists()

        return False

    except Exception as e:
        logger.error(f"Failed to run mkcert with elevation: {e}")
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
            # On Windows, provide more detailed error message
            if platform.system() == "Windows":
                logger.error(
                    "Failed to install mkcert automatically. Please install manually:"
                )
                logger.error(
                    "  1. Download from: https://github.com/FiloSottile/mkcert/releases"
                )
                logger.error("  2. Or install via Chocolatey: choco install mkcert")
                logger.error("  3. Ensure mkcert.exe is in your PATH")
            return False

        # Get the correct mkcert command
        mkcert_cmd = get_mkcert_command()

        # Initialize mkcert CA
        logger.info("Setting up root CA certificate...")

        # On Windows, try different approaches
        if platform.system() == "Windows":
            # First try normal execution
            result = subprocess.run(
                [mkcert_cmd, "-install"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )

            if result.returncode != 0:
                if (
                    "The request is not supported" in result.stderr
                    or "access denied" in result.stderr.lower()
                ):
                    logger.info("Attempting to install CA with elevated privileges...")

                    # Try with elevation
                    if _run_mkcert_install_elevated_windows(mkcert_cmd):
                        logger.info(
                            "Successfully installed CA with elevated privileges"
                        )
                    else:
                        logger.warning(
                            "Failed to add certificate to system store (permission denied)."
                        )
                        logger.warning(
                            "Certificate will still work but you may see browser warnings."
                        )
                        logger.info(
                            "To fix this, run 'mkcert -install' as Administrator manually."
                        )
                else:
                    # Other errors should still fail
                    raise subprocess.CalledProcessError(
                        result.returncode, result.args, result.stdout, result.stderr
                    )
        else:
            # Non-Windows systems
            subprocess.run(
                [mkcert_cmd, "-install"], check=True, encoding="utf-8", errors="replace"
            )

        # Get the CA root path
        ca_root = subprocess.run(
            [mkcert_cmd, "-CAROOT"],
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
            errors="replace",
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
                    encoding="utf-8",
                    errors="replace",
                )
                logger.info("Added root certificate to System keychain")
            except subprocess.SubprocessError as e:
                logger.warning(f"Could not add to System keychain: {e}")

        logger.info("Root certificate setup completed")
        return True

    except Exception as e:
        logger.error(f"Failed to set up browser trust: {e}")
        return False


def install_openssl() -> bool:
    """
    Install OpenSSL if it's not already installed.

    Returns:
        True if OpenSSL is available after this function runs
    """
    if check_command_exists("openssl"):
        logger.info("OpenSSL is already installed")
        return True

    logger.info("OpenSSL not found. Attempting to install...")
    system = platform.system()

    try:
        if system == "Windows":
            return _install_openssl_windows()
        elif system == "Darwin":  # macOS
            return _install_openssl_macos()
        elif system == "Linux":
            return _install_openssl_linux()
        else:
            logger.warning(f"Unsupported system: {system}")
            return False

    except Exception as e:
        logger.error(f"Failed to install OpenSSL: {e}")
        return False


def _install_openssl_windows() -> bool:
    """Install OpenSSL on Windows using Git for Windows (most reliable method)."""
    # First, try common locations where OpenSSL might already exist
    common_paths = [
        "C:/Program Files/Git/usr/bin/openssl.exe",
        "C:/Program Files (x86)/Git/usr/bin/openssl.exe",
        "C:/msys64/usr/bin/openssl.exe",
        "C:/Windows/System32/openssl.exe",
    ]

    for path in common_paths:
        if Path(path).exists():
            # Add to PATH for current session
            bin_dir = str(Path(path).parent)
            current_path = os.environ.get("PATH", "")
            if bin_dir not in current_path:
                os.environ["PATH"] = f"{current_path};{bin_dir}"
                logger.info(f"Found OpenSSL at {path}")
                return True

    # If Git for Windows is installed, it includes OpenSSL
    git_paths = ["C:/Program Files/Git/usr/bin", "C:/Program Files (x86)/Git/usr/bin"]

    for git_path in git_paths:
        openssl_path = Path(git_path) / "openssl.exe"
        if openssl_path.exists():
            current_path = os.environ.get("PATH", "")
            if git_path not in current_path:
                os.environ["PATH"] = f"{current_path};{git_path}"
                logger.info(f"Using OpenSSL from Git installation: {openssl_path}")
                return True

    # Try package managers if available
    if check_command_exists("choco"):
        try:
            subprocess.run(
                ["choco", "install", "openssl", "-y"], check=True, capture_output=True
            )
            return check_command_exists("openssl")
        except subprocess.SubprocessError:
            pass

    if check_command_exists("scoop"):
        try:
            subprocess.run(
                ["scoop", "install", "openssl"], check=True, capture_output=True
            )
            return check_command_exists("openssl")
        except subprocess.SubprocessError:
            pass

    # Provide clear installation instructions
    logger.warning(
        "OpenSSL not found. Please install using one of these methods:\n"
        "  1. Install Git for Windows (includes OpenSSL): https://git-scm.com/download/win\n"
        "  2. Download OpenSSL directly: https://slproweb.com/products/Win32OpenSSL.html\n"
        "  3. Use Chocolatey: choco install openssl\n"
        "  4. Use Scoop: scoop install openssl"
    )
    return False


def _install_openssl_macos() -> bool:
    """Install OpenSSL on macOS."""
    if check_command_exists("brew"):
        try:
            subprocess.run(["brew", "install", "openssl"], check=True)

            # Add Homebrew paths to current session
            homebrew_paths = ["/opt/homebrew/bin", "/usr/local/bin"]
            current_path = os.environ.get("PATH", "")

            for path in homebrew_paths:
                if Path(path).exists() and path not in current_path:
                    os.environ["PATH"] = f"{path}:{current_path}"

            return check_command_exists("openssl")
        except subprocess.SubprocessError:
            pass

    logger.warning(
        """Please install OpenSSL manually:\n
          1. Install Homebrew: /bin/bash -c
          '$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)'\n
          2. Install OpenSSL: brew install openssl"""
    )
    return False


def _install_openssl_linux() -> bool:
    """Install OpenSSL on Linux."""
    package_managers = [
        (
            ["apt"],
            ["sudo", "apt", "update"],
            ["sudo", "apt", "install", "-y", "openssl"],
        ),
        (["dnf"], None, ["sudo", "dnf", "install", "-y", "openssl"]),
        (["yum"], None, ["sudo", "yum", "install", "-y", "openssl"]),
        (["pacman"], None, ["sudo", "pacman", "-S", "--noconfirm", "openssl"]),
    ]

    for check_cmd, update_cmd, install_cmd in package_managers:
        if check_command_exists(check_cmd[0]):
            try:
                if update_cmd:
                    subprocess.run(update_cmd, check=True, capture_output=True)
                subprocess.run(install_cmd, check=True, capture_output=True)
                return check_command_exists("openssl")
            except subprocess.SubprocessError:
                continue

    logger.warning("Please install OpenSSL using your distribution's package manager")
    return False
