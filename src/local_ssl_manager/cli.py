"""
Command-line interface for Local SSL Manager.

This module provides the CLI entry points for the local-ssl-manager tool.
It uses Click for command parsing and Rich for terminal output formatting.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich.table import Table

from . import __version__
from .manager import LocalSSLManager
from .ui.domain_selector import show_domain_selector
from .utils.system import check_admin_privileges, run_as_admin

# Create console for rich output
console = Console()


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[bold red]Error:[/bold red] {message}")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[bold green]Success:[/bold green] {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[bold blue]Info:[/bold blue] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[bold yellow]Warning:[/bold yellow] {message}")


def check_privileges() -> bool:
    """
    Check if the script has admin privileges and restart if not.

    Returns:
        True if already admin or restarted, False if cannot restart
    """
    if check_admin_privileges():
        return True

    # If not admin, try to restart with privileges
    print_warning("Administrative privileges required for this operation.")
    print_info("Attempting to restart with elevated privileges...")

    try:
        run_as_admin([sys.executable] + sys.argv)
        sys.exit(0)
    except Exception as e:
        print_error(f"Failed to restart with admin privileges: {e}")
        print_info("Please run this command with administrative privileges.")
        return False


def print_certificate_table(certificates: List[Dict[str, Any]]) -> None:
    """
    Print a table of certificates.

    Args:
        certificates: List of certificate information
    """
    table = Table(
        title="Managed SSL Certificates",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
    )

    table.add_column("Domain", style="dim")
    table.add_column("Created", style="dim")
    table.add_column("Status", style="dim")
    table.add_column("Valid Until", style="dim")
    table.add_column("IP", style="dim")

    # Add rows to the table
    for cert in certificates:
        status_style = "green" if cert["status"] == "valid" else "red"

        # Format the creation date
        created_at = cert["created_at"]
        if isinstance(created_at, str):
            # If it's a string, try to parse it
            try:
                from datetime import datetime

                created_at = datetime.fromisoformat(created_at)
                created_str = created_at.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                created_str = created_at
        else:
            # If it's already a datetime object
            created_str = created_at.strftime("%Y-%m-%d %H:%M")

        table.add_row(
            cert["domain"],
            created_str,
            f"[{status_style}]{cert['status']}[/{status_style}]",
            cert.get("valid_to", "Unknown"),
            cert.get("ip_address", "127.0.0.1"),
        )

    console.print(table)


def print_certificate_details(cert_info: Dict[str, str]) -> None:
    """
    Print details for a single certificate.

    Args:
        cert_info: Certificate information
    """
    panel_content = []

    # Add each field to the panel content
    panel_content.append(f"[bold]Domain:[/bold] {cert_info['domain']}")
    panel_content.append(
        f"[bold]IP Address:[/bold] {cert_info.get('ip_address', '127.0.0.1')}"
    )
    panel_content.append(f"[bold]Certificate Path:[/bold] {cert_info['cert_path']}")
    panel_content.append(f"[bold]Key Path:[/bold] {cert_info['key_path']}")

    if "log_path" in cert_info:
        panel_content.append(f"[bold]Log Path:[/bold] {cert_info['log_path']}")

    if cert_info.get("imported", False):
        panel_content.append("[bold]Imported:[/bold] Yes")

    if "status" in cert_info:
        status_style = "green" if cert_info["status"] == "valid" else "red"
        panel_content.append(
            f"[bold]Status:[/bold] [{status_style}]{cert_info['status']}[/{status_style}]"
        )

    if "valid_to" in cert_info:
        panel_content.append(f"[bold]Valid Until:[/bold] {cert_info['valid_to']}")

    # Create the panel with the content
    panel = Panel(
        "\n\n".join(panel_content),
        title="Certificate Details",
        subtitle="Local SSL Manager",
        border_style="green",
        padding=(1, 2),
    )

    console.print(panel)


@click.group()
@click.version_option(version=__version__, prog_name="Local SSL Manager")
def cli():
    """
    Local SSL Manager - Create and manage SSL certificates for local development.

    This tool helps you:
    - Create self-signed SSL certificates for local domains
    - Automatically update hosts file entries
    - Configure browser trust for certificates
    - Manage certificates with domain-specific logging

    All certificates and configuration are stored in ~/.local-ssl-manager by default.
    """
    pass


@cli.command()
@click.option(
    "--domain",
    "-d",
    required=True,
    help="Domain name to create a certificate for (e.g., myproject.local)",
)
@click.option(
    "--ip", default="127.0.0.1", help="IP address for the domain (default: 127.0.0.1)"
)
@click.option(
    "--base-dir",
    "-b",
    type=click.Path(file_okay=False),
    help="Custom base directory for certificates and configuration",
)
def create(domain: str, ip: str, base_dir: Optional[str] = None):
    """Create a new SSL certificate for a local domain."""
    # Check for admin privileges
    if not check_privileges():
        return

    try:
        # Initialize manager
        manager = LocalSSLManager(Path(base_dir) if base_dir else None)

        # Create certificate with progress indicator
        print_info(f"Creating certificate for {domain}...")
        cert_info = manager.setup_local_domain(domain, ip)

        print_success(f"Certificate for {domain} created successfully!")
        print_certificate_details(cert_info)

        print_info(
            f"To use this certificate in your web server, configure it with:\n"
            f"  - Certificate: {cert_info['cert_path']}\n"
            f"  - Private Key: {cert_info['key_path']}"
            f"Alternatively, use the `ssl-manager export` command."
        )

    except ValueError as e:
        print_error(str(e))
        sys.exit(1)
    except Exception as e:
        print_error(f"Failed to create certificate: {e}")
        sys.exit(1)


@cli.command()
@click.option(
    "--domains",
    "-d",
    help="Comma-separated list of domains to create certificates for",
    required=True,
)
@click.option(
    "--ip", default="127.0.0.1", help="IP address for the domains (default: 127.0.0.1)"
)
@click.option("--name", "-n", help="Optional name for the certificate files")
@click.option(
    "--base-dir",
    "-b",
    type=click.Path(file_okay=False),
    help="Custom base directory for certificates and configuration",
)
def create_multi(
    domains: str, ip: str, name: Optional[str] = None, base_dir: Optional[str] = None
):
    """Create a single certificate for multiple domains."""
    # Check for admin privileges
    if not check_privileges():
        return

    try:
        # Parse domains
        domain_list = [d.strip() for d in domains.split(",") if d.strip()]

        if not domain_list:
            print_error("No valid domains provided")
            sys.exit(1)

        # Initialize manager
        manager = LocalSSLManager(Path(base_dir) if base_dir else None)

        # Create multi-domain certificate with progress indicator
        with Progress(
            SpinnerColumn(),
            TextColumn(
                f"[blue]Creating certificate for {len(domain_list)} domains...[/blue]"
            ),
            transient=True,
        ) as progress:
            progress.add_task("create", total=None)
            cert_info = manager.setup_multi_domain(domain_list, ip, name)

        print_success(
            f"Certificate for {len(domain_list)} domains created successfully!"
        )

        # Display certificate details
        panel_content = [
            f"[bold]Certificate Path:[/bold] {cert_info['cert_path']}",
            f"[bold]Key Path:[/bold] {cert_info['key_path']}",
            f"[bold]IP Address:[/bold] {cert_info['ip_address']}",
            "[bold]Domains:[/bold]",
        ]

        for domain in cert_info["domains"]:
            panel_content.append(f"  - {domain}")

        panel = Panel(
            "\n\n".join(panel_content),
            title="Multi-Domain Certificate Details",
            border_style="green",
            padding=(1, 2),
        )

        console.print(panel)

    except ValueError as e:
        print_error(str(e))
        sys.exit(1)
    except Exception as e:
        print_error(f"Failed to create multi-domain certificate: {e}")
        sys.exit(1)


@cli.command()
@click.option(
    "--domain",
    "-d",
    help="Domain to delete (if not specified, shows interactive selector)",
)
@click.option(
    "--base-dir",
    "-b",
    type=click.Path(file_okay=False),
    help="Custom base directory for certificates and configuration",
)
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
def delete(domain: Optional[str], base_dir: Optional[str], force: bool):
    """Delete a certificate and remove the domain from hosts file."""
    # Check for admin privileges
    if not check_privileges():
        return

    try:
        # Initialize manager
        manager = LocalSSLManager(Path(base_dir) if base_dir else None)

        # If domain not specified, show selector
        if not domain:
            domain_hierarchy = manager.get_domain_hierarchy()
            if not domain_hierarchy:
                print_info("No certificates found.")
                return

            domain = show_domain_selector(domain_hierarchy)
            if not domain:
                print_info("Operation cancelled.")
                return

        # Confirm deletion
        if not force:
            confirm = Confirm.ask(
                f"Are you sure you want to delete certificate for [bold]{domain}[/bold]?",
                default=False,
            )
            if not confirm:
                print_info("Operation cancelled.")
                return

        # Delete certificate with progress indicator
        with Progress(
            SpinnerColumn(),
            TextColumn(f"[blue]Deleting certificate for {domain}...[/blue]"),
            transient=True,
        ) as progress:
            progress.add_task("delete", total=None)
            success = manager.delete_certificate(domain)

        if success:
            print_success(f"Certificate for {domain} deleted successfully!")
        else:
            print_error(f"Failed to delete certificate for {domain}")
            sys.exit(1)

    except ValueError as e:
        print_error(str(e))
        sys.exit(1)
    except Exception as e:
        print_error(f"Failed to delete certificate: {e}")
        sys.exit(1)


@cli.command()
@click.option(
    "--base-dir",
    "-b",
    type=click.Path(file_okay=False),
    help="Custom base directory for certificates and configuration",
)
def list(base_dir: Optional[str]):
    """List all managed certificates."""
    try:
        # Initialize manager
        manager = LocalSSLManager(Path(base_dir) if base_dir else None)

        # Get certificates with progress indicator
        with Progress(
            SpinnerColumn(),
            TextColumn("[blue]Getting certificates...[/blue]"),
            transient=True,
        ) as progress:
            progress.add_task("list", total=None)
            certificates = manager.get_certificates()

        if not certificates:
            print_info("No certificates found.")
            return

        # Display certificates
        print_certificate_table(certificates)

    except Exception as e:
        print_error(f"Failed to list certificates: {e}")
        sys.exit(1)


@cli.command()
@click.option(
    "--domain", "-d", required=True, help="Domain name to export certificate for"
)
@click.option(
    "--output",
    "-o",
    type=click.Path(file_okay=False),
    required=True,
    help="Directory to export certificate to",
)
@click.option(
    "--base-dir",
    "-b",
    type=click.Path(file_okay=False),
    help="Custom base directory for certificates and configuration",
)
def export(domain: str, output: str, base_dir: Optional[str]):
    """Export a certificate to a directory."""
    try:
        # Initialize manager
        manager = LocalSSLManager(Path(base_dir) if base_dir else None)

        # Export certificate with progress indicator
        with Progress(
            SpinnerColumn(),
            TextColumn(f"[blue]Exporting certificate for {domain}...[/blue]"),
            transient=True,
        ) as progress:
            progress.add_task("export", total=None)
            cert_path, key_path = manager.export_certificate(domain, Path(output))

        print_success("Certificate exported successfully!")
        print_info(
            f"Certificate exported to:\n"
            f"  - Certificate: {cert_path}\n"
            f"  - Private Key: {key_path}"
        )

    except ValueError as e:
        print_error(str(e))
        sys.exit(1)
    except Exception as e:
        print_error(f"Failed to export certificate: {e}")
        sys.exit(1)


@cli.command()
@click.option("--domain", "-d", required=True, help="Domain name for the certificate")
@click.option(
    "--cert",
    "-c",
    type=click.Path(exists=True, dir_okay=False),
    required=True,
    help="Path to certificate file",
)
@click.option(
    "--key",
    "-k",
    type=click.Path(exists=True, dir_okay=False),
    required=True,
    help="Path to private key file",
)
@click.option(
    "--ip", default="127.0.0.1", help="IP address for the domain (default: 127.0.0.1)"
)
@click.option(
    "--base-dir",
    "-b",
    type=click.Path(file_okay=False),
    help="Custom base directory for certificates and configuration",
)
def import_cert(domain: str, cert: str, key: str, ip: str, base_dir: Optional[str]):
    """Import an existing certificate."""
    # Check for admin privileges
    if not check_privileges():
        return

    try:
        # Initialize manager
        manager = LocalSSLManager(Path(base_dir) if base_dir else None)

        # Import certificate with progress indicator
        with Progress(
            SpinnerColumn(),
            TextColumn(f"[blue]Importing certificate for {domain}...[/blue]"),
            transient=True,
        ) as progress:
            progress.add_task("import", total=None)
            cert_info = manager.import_certificate(domain, Path(cert), Path(key), ip)

        print_success(f"Certificate for {domain} imported successfully!")
        print_certificate_details(cert_info)

    except ValueError as e:
        print_error(str(e))
        sys.exit(1)
    except Exception as e:
        print_error(f"Failed to import certificate: {e}")
        sys.exit(1)


def main():
    """Main entry point for the CLI."""
    try:
        cli()
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
