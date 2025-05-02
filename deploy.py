#!/usr/bin/env python3
"""
Deployment script for local-ssl-manager.

This script automates the process of deploying a new version to PyPI.
It handles version updates, git tagging, and provides helpful reminders.
"""

import os
import re
import sys
import subprocess
from pathlib import Path
import argparse


def get_current_version():
    """Extract the current version from pyproject.toml."""
    pyproject_path = Path("pyproject.toml")

    if not pyproject_path.exists():
        print("Error: pyproject.toml not found")
        sys.exit(1)

    with open(pyproject_path, "r") as f:
        content = f.read()

    # Look for version in pyproject.toml
    version_match = re.search(r'version\s*=\s*"([^"]+)"', content)
    if not version_match:
        print("Error: Could not find version in pyproject.toml")
        sys.exit(1)

    return version_match.group(1)


def update_version(new_version):
    """Update the version in pyproject.toml."""
    pyproject_path = Path("pyproject.toml")

    with open(pyproject_path, "r") as f:
        content = f.read()

    # Replace version in pyproject.toml
    updated_content = re.sub(
        r'(version\s*=\s*")([^"]+)(")', r"\g<1>" + new_version + r"\g<3>", content
    )

    with open(pyproject_path, "w") as f:
        f.write(updated_content)


def validate_version(version):
    """Validate that the version string follows semantic versioning."""
    pattern = r"^\d+\.\d+\.\d+$"
    if not re.match(pattern, version):
        print(f"Error: Version '{version}' does not follow semantic versioning (X.Y.Z)")
        return False
    return True


def run_command(command, error_message):
    """Run a shell command and exit if it fails."""
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {error_message}")
        print(f"Command output: {result.stderr}")
        sys.exit(1)
    return result.stdout.strip()


def git_is_clean():
    """Check if the git working directory is clean."""
    result = subprocess.run(
        "git status --porcelain", shell=True, capture_output=True, text=True
    )
    return result.stdout.strip() == ""


def main():
    """Main deployment process."""
    parser = argparse.ArgumentParser(
        description="Deploy a new version of local-ssl-manager"
    )
    parser.add_argument("--version", "-v", help="New version to deploy (X.Y.Z format)")
    parser.add_argument("--message", "-m", help="Version tag message")
    args = parser.parse_args()

    # Check if git is available
    try:
        run_command("git --version", "Git is not installed")
    except Exception:
        print("Error: Git is not installed or not in PATH")
        sys.exit(1)

    # Check if on main branch
    current_branch = run_command(
        "git branch --show-current", "Failed to get current branch"
    )
    if current_branch != "main":
        print(f"Warning: You are on branch '{current_branch}', not 'main'")
        proceed = input("Do you want to proceed anyway? (y/N): ").lower()
        if proceed != "y":
            print("Deployment cancelled")
            sys.exit(0)

    # Get the current version
    current_version = get_current_version()
    print(f"Current version: {current_version}")

    # Get new version from argument or prompt
    new_version = args.version
    if not new_version:
        new_version = input(f"Enter new version (current: {current_version}): ")

    if not validate_version(new_version):
        sys.exit(1)

    # Check if working directory is clean
    if not git_is_clean():
        print(
            "Error: Git working directory is not clean. Commit or stash changes first."
        )
        sys.exit(1)

    # Pull latest changes
    print("Pulling latest changes from main...")
    run_command("git pull origin main", "Failed to pull latest changes")

    # Update version in pyproject.toml
    print(f"Updating version from {current_version} to {new_version}...")
    update_version(new_version)

    # Commit version change
    print("Committing version change...")
    run_command(
        f'git commit -am "Bump version to {new_version}"',
        "Failed to commit version change",
    )

    # Create tag message
    tag_message = args.message
    if not tag_message:
        tag_message = input("Enter tag message (e.g., 'Add new feature X'): ")
        if not tag_message:
            tag_message = f"Version {new_version}"

    # Create and push tag
    tag_name = f"v{new_version}"
    print(f"Creating tag {tag_name}...")
    run_command(f'git tag -a {tag_name} -m "{tag_message}"', "Failed to create tag")

    # Push changes and tag
    print("Pushing changes to main...")
    run_command("git push origin main", "Failed to push changes")

    print(f"Pushing tag {tag_name}...")
    run_command(f"git push origin {tag_name}", "Failed to push tag")

    print("\n================ Deployment Started ================")
    print(f"Version {new_version} has been tagged and pushed.")
    print("GitHub Actions will now build and publish the package to PyPI.")
    print("You can monitor the workflow at:")
    # Get repository URL
    repo_url = run_command(
        "git config --get remote.origin.url", "Failed to get repository URL"
    )
    # Convert SSH URL to HTTPS if necessary
    if repo_url.startswith("git@github.com:"):
        repo_url = repo_url.replace("git@github.com:", "https://github.com/")
        if repo_url.endswith(".git"):
            repo_url = repo_url[:-4]
    print(f"{repo_url}/actions")
    print("======================================================")

    print("\nIMPORTANT REMINDERS:")
    print("1. Check that GitHub Actions successfully publishes the package")
    print("2. Verify the new version appears on PyPI")
    print("3. Create a GitHub release with release notes if desired")
    print("\nDeployment process completed successfully!")


if __name__ == "__main__":
    main()
