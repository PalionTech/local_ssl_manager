#!/usr/bin/env python3
"""
Simple version bumping script for local-ssl-manager.

This script updates version numbers in pyproject.toml and __init__.py,
and adds a placeholder entry to CHANGELOG.md.
"""

import re
from datetime import datetime
from pathlib import Path


def get_version():
    """Get current version from pyproject.toml."""
    with open("pyproject.toml", "r") as f:
        content = f.read()
    match = re.search(r'version\s*=\s*"([^"]+)"', content)
    return match.group(1) if match else None


def bump_version(version_type="patch", specific_version=None):
    """Bump version in pyproject.toml and __init__.py."""
    current = get_version()
    if not current:
        print("Error: Could not find version in pyproject.toml")
        return False

    # Calculate new version
    if specific_version:
        new_version = specific_version
    else:
        major, minor, patch = map(int, current.split("."))
        if version_type == "major":
            new_version = f"{major+1}.0.0"
        elif version_type == "minor":
            new_version = f"{major}.{minor+1}.0"
        else:  # patch
            new_version = f"{major}.{minor}.{patch+1}"

    # Update pyproject.toml
    with open("pyproject.toml", "r") as f:
        content = f.read()
    updated = re.sub(r'(version\s*=\s*")([^"]+)(")', f"\\1{new_version}\\3", content)
    with open("pyproject.toml", "w") as f:
        f.write(updated)

    # Update __init__.py if it exists
    init_path = Path("src/local_ssl_manager/__init__.py")
    if init_path.exists():
        with open(init_path, "r") as f:
            content = f.read()
        updated = re.sub(
            r'(__version__\s*=\s*")([^"]+)(")', f"\\1{new_version}\\3", content
        )
        with open(init_path, "w") as f:
            f.write(updated)

    # Update CHANGELOG.md
    update_changelog(new_version)

    print(f"Version bumped: {current} -> {new_version}")
    return True


def update_changelog(version):
    """Add a new entry to CHANGELOG.md."""
    today = datetime.now().strftime("%Y-%m-%d")
    new_entry = (
        f"\n## [v{version}] - {today}\n\n### Added\n\n### Changed\n\n### Fixed\n\n"
    )

    try:
        with open("CHANGELOG.md", "r") as f:
            content = f.read()

        # Find where to insert the new entry
        if "## [" in content:
            updated = content.replace("## [", new_entry + "## [", 1)
        else:
            updated = content + new_entry

        with open("CHANGELOG.md", "w") as f:
            f.write(updated)

        print(f"Added entry for v{version} to CHANGELOG.md")
    except FileNotFoundError:
        # Create changelog if it doesn't exist
        with open("CHANGELOG.md", "w") as f:
            f.write(f"# Changelog\n{new_entry}")
        print("Created CHANGELOG.md")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Bump version numbers")
    parser.add_argument(
        "--type",
        choices=["patch", "minor", "major"],
        default="patch",
        help="Type of version bump",
    )
    parser.add_argument("--version", help="Specific version to set")
    args = parser.parse_args()

    bump_version(args.type, args.version)
