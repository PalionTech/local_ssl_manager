#!/usr/bin/env python3
"""
Version bumping script for local-ssl-manager.

This script:
1. Updates version numbers in pyproject.toml and __init__.py
2. Adds a placeholder entry to CHANGELOG.md
3. Creates and checks out a release branch based on the new version
"""

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def get_version():
    """Get current version from pyproject.toml."""
    with open("pyproject.toml", "r") as f:
        content = f.read()
    match = re.search(r'version\s*=\s*"([^"]+)"', content)
    return match.group(1) if match else None


def run_command(command, error_message="Command failed"):
    """Run a shell command and handle errors."""
    print(f"Running: {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {error_message}")
        print(f"Command output: {result.stderr}")
        return False
    return True


def get_current_branch():
    """Get the name of the current git branch."""
    result = subprocess.run(
        "git branch --show-current", shell=True, capture_output=True, text=True
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return None


def bump_version(version_type="patch", specific_version=None):
    """
    Bump version in pyproject.toml and __init__.py,
    create a release branch, and update CHANGELOG.md.
    """
    # Check if we're on develop branch
    current_branch = get_current_branch()
    if current_branch != "develop":
        print(f"Warning: You are not on the develop branch (current: {current_branch})")
        cont = input("Do you want to continue anyway? (y/n): ")
        if cont.lower() != "y":
            print("Aborted.")
            return False

    # Get current version and calculate new version
    current = get_version()
    if not current:
        print("Error: Could not find version in pyproject.toml")
        return False

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

    # Ensure version is valid
    if not re.match(r"^\d+\.\d+\.\d+$", new_version):
        print(f"Error: Invalid version format: {new_version}")
        print("Version must be in the format X.Y.Z (e.g., 1.2.3)")
        return False

    # Create release branch
    release_branch = f"release/v{new_version}"
    if not run_command(
        f"git checkout -b {release_branch}", f"Failed to create branch {release_branch}"
    ):
        return False

    print(f"Created and switched to branch: {release_branch}")

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

    # Commit the changes
    if run_command(
        f'git add . && git commit -m "Prepare release v{new_version}"',
        "Failed to commit version change",
    ):
        # Push to remote
        if run_command(
            f"git push -u origin {release_branch}",
            f"Failed to push {release_branch} to remote",
        ):
            print(f"\n✅ Release branch {release_branch} created successfully!")
            print(f"Current version: {current} → New version: {new_version}")
            print("\nNext steps:")
            print("1. Complete the CHANGELOG.md with all significant changes")
            print("2. Create a Pull Request from this branch to main")
            print("3. After merging to main, create a PR from this branch to develop")

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

    parser = argparse.ArgumentParser(
        description="Bump version and create release branch"
    )
    parser.add_argument(
        "--type",
        choices=["patch", "minor", "major"],
        default="patch",
        help="Type of version bump",
    )
    parser.add_argument("--version", help="Specific version to set")
    args = parser.parse_args()

    if not bump_version(args.type, args.version):
        sys.exit(1)
