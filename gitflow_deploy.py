#!/usr/bin/env python3
"""
GitFlow-based deployment script for local-ssl-manager.

This script automates the process of creating release branches,
finalizing releases, and deploying to PyPI following GitFlow conventions.
"""

import argparse
import re
import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import Optional


class DeploymentAction(Enum):
    """Possible deployment actions."""

    START_RELEASE = "start-release"
    FINALIZE_RELEASE = "finalize-release"
    HOTFIX = "hotfix"
    DEPLOY = "deploy"


def get_current_version() -> str:
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


def update_version(new_version: str) -> None:
    """Update the version in pyproject.toml."""
    pyproject_path = Path("pyproject.toml")
    init_path = Path("src/local_ssl_manager/__init__.py")

    # Update pyproject.toml
    with open(pyproject_path, "r") as f:
        content = f.read()

    updated_content = re.sub(
        r'(version\s*=\s*")([^"]+)(")', r"\g<1>" + new_version + r"\g<3>", content
    )

    with open(pyproject_path, "w") as f:
        f.write(updated_content)

    # Update __init__.py if it exists
    if init_path.exists():
        with open(init_path, "r") as f:
            content = f.read()

        updated_content = re.sub(
            r'(__version__\s*=\s*")([^"]+)(")',
            r"\g<1>" + new_version + r"\g<3>",
            content,
        )

        with open(init_path, "w") as f:
            f.write(updated_content)


def validate_version(version: str) -> bool:
    """Validate that the version string follows semantic versioning."""
    pattern = r"^\d+\.\d+\.\d+$"
    if not re.match(pattern, version):
        print(f"Error: Version '{version}' does not follow semantic versioning (X.Y.Z)")
        return False
    return True


def get_next_version(current_version: str, version_part: str = "patch") -> str:
    """
    Calculate the next version based on semantic versioning.

    Args:
        current_version: Current version string (X.Y.Z)
        version_part: Which part to increment: 'major', 'minor', or 'patch'

    Returns:
        Next version string
    """
    parts = current_version.split(".")
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

    if version_part == "major":
        return f"{major + 1}.0.0"
    elif version_part == "minor":
        return f"{major}.{minor + 1}.0"
    else:  # patch
        return f"{major}.{minor}.{patch + 1}"


def run_command(command: str, error_message: str, capture_output: bool = True) -> str:
    """Run a shell command and exit if it fails."""
    print(f"Running: {command}")
    result = subprocess.run(
        command, shell=True, capture_output=capture_output, text=True
    )
    if result.returncode != 0:
        print(f"Error: {error_message}")
        print(f"Command output: {result.stderr}")
        sys.exit(1)
    return result.stdout.strip() if capture_output else ""


def git_is_clean() -> bool:
    """Check if the git working directory is clean."""
    result = subprocess.run(
        "git status --porcelain", shell=True, capture_output=True, text=True
    )
    return result.stdout.strip() == ""


def get_current_branch() -> str:
    """Get the name of the current git branch."""
    return run_command("git branch --show-current", "Failed to get current branch")


def update_changelog(version: str, message: Optional[str] = None) -> None:
    """
    Update the CHANGELOG.md file with the new version.

    Creates the file if it doesn't exist.
    """
    changelog_path = Path("CHANGELOG.md")

    # Get today's date
    from datetime import datetime

    today = datetime.now().strftime("%Y-%m-%d")

    # Create or update the changelog
    if changelog_path.exists():
        with open(changelog_path, "r") as f:
            content = f.read()
    else:
        content = """# Changelog\n\n
        All notable changes to this project will be documented in this file.\n\n"""

    # Add new version section at the top
    version_header = f"## [v{version}] - {today}\n\n"
    if message:
        version_content = f"{message}\n\n"
    else:
        version_content = "### Added\n- \n\n### Changed\n- \n\n### Fixed\n- \n\n"

    new_content = content.split("## [", 1)
    if len(new_content) > 1:
        updated_content = (
            new_content[0] + version_header + version_content + "## [" + new_content[1]
        )
    else:
        updated_content = content + "\n" + version_header + version_content

    with open(changelog_path, "w") as f:
        f.write(updated_content)

    print(f"Updated CHANGELOG.md with version {version}")


def start_release(version_part: str, version: Optional[str] = None) -> None:
    """
    Start a new release branch from develop.

    Args:
        version_part: Which part to increment: 'major', 'minor', or 'patch'
        version: Specific version to use (optional)
    """
    # Ensure we're on develop branch
    current_branch = get_current_branch()
    if current_branch != "develop":
        print(
            f"""Error: You must be on the develop branch
                to start a release (current: {current_branch})"""
        )
        sys.exit(1)

    # Make sure develop is up to date
    run_command("git pull origin develop", "Failed to pull latest changes from develop")

    # Determine the version
    current_version = get_current_version()
    if version:
        new_version = version
    else:
        new_version = get_next_version(current_version, version_part)

    if not validate_version(new_version):
        sys.exit(1)

    # Create release branch
    release_branch = f"release/v{new_version}"
    run_command(
        f"git checkout -b {release_branch}", f"Failed to create branch {release_branch}"
    )

    # Update version in files
    update_version(new_version)

    # Update changelog
    update_changelog(new_version)

    # Commit changes
    run_command(
        f'git commit -am "Prepare release v{new_version}"',
        "Failed to commit version change",
    )

    # Push to remote
    run_command(
        f"git push -u origin {release_branch}",
        f"Failed to push {release_branch} to remote",
    )

    print(f"\n✅ Release branch {release_branch} created successfully!")
    print(f"Current version: {current_version} → New version: {new_version}")
    print("\nNext steps:")
    print("1. Complete the CHANGELOG.md with all significant changes")
    print("2. Make any final adjustments needed for the release")
    print("3. Run 'python gitflow_deploy.py finalize-release' when ready to finalize")


def finalize_release() -> None:
    """
    Finalize a release by merging into main and develop.
    """
    # Check if we're on a release branch
    current_branch = get_current_branch()
    if not current_branch.startswith("release/"):
        print(
            f"Error: You must be on a release branch to finalize (current: {current_branch})"
        )
        sys.exit(1)

    # Make sure the working directory is clean
    if not git_is_clean():
        print("Error: Working directory is not clean. Commit or stash changes first.")
        sys.exit(1)

    # Extract version from branch name or from files
    version = current_branch.replace("release/v", "")
    if not validate_version(version):
        # Try to get from pyproject.toml instead
        version = get_current_version()

    # Make sure release branch is up to date
    run_command(f"git pull origin {current_branch}", "Failed to pull latest changes")

    # Merge to main
    run_command("git checkout main", "Failed to checkout main branch")
    run_command("git pull origin main", "Failed to pull latest changes from main")
    run_command(
        f'git merge --no-ff {current_branch} -m "Merge release v{version} into main"',
        f"Failed to merge {current_branch} into main",
    )

    # Create version tag
    tag_name = f"v{version}"
    run_command(f'git tag -a {tag_name} -m "Version {version}"', "Failed to create tag")

    # Push main and tag
    run_command("git push origin main", "Failed to push main to remote")
    run_command(f"git push origin {tag_name}", "Failed to push tag to remote")

    # Merge back to develop
    run_command("git checkout develop", "Failed to checkout develop branch")
    run_command("git pull origin develop", "Failed to pull latest changes from develop")
    run_command(
        f'git merge --no-ff {current_branch} -m "Merge release v{version} back into develop"',
        f"Failed to merge {current_branch} into develop",
    )
    run_command("git push origin develop", "Failed to push develop to remote")

    # Delete release branch
    run_command(
        "git branch -d " + current_branch, "Failed to delete local release branch"
    )
    run_command(
        "git push origin -d " + current_branch, "Failed to delete remote release branch"
    )

    print(f"\n✅ Release v{version} finalized successfully!")
    print(f"Version tag {tag_name} created and pushed.")
    print("\nGitHub Actions will now build and publish the package to PyPI.")
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


def start_hotfix(version: Optional[str] = None) -> None:
    """
    Start a hotfix branch from main.

    Args:
        version: Specific version to use (optional)
    """
    # Ensure we're on main branch
    current_branch = get_current_branch()
    if current_branch != "main":
        print(
            f"Error: You must be on the main branch to start a hotfix (current: {current_branch})"
        )
        sys.exit(1)

    # Make sure main is up to date
    run_command("git pull origin main", "Failed to pull latest changes from main")

    # Determine the version
    current_version = get_current_version()
    if version:
        new_version = version
    else:
        new_version = get_next_version(current_version, "patch")

    if not validate_version(new_version):
        sys.exit(1)

    # Create hotfix branch
    hotfix_branch = f"hotfix/v{new_version}"
    run_command(
        f"git checkout -b {hotfix_branch}", f"Failed to create branch {hotfix_branch}"
    )

    # Update version in files
    update_version(new_version)

    # Update changelog
    update_changelog(new_version)

    # Commit changes
    run_command(
        f'git commit -am "Prepare hotfix v{new_version}"',
        "Failed to commit version change",
    )

    # Push to remote
    run_command(
        f"git push -u origin {hotfix_branch}",
        f"Failed to push {hotfix_branch} to remote",
    )

    print(f"\n✅ Hotfix branch {hotfix_branch} created successfully!")
    print(f"Current version: {current_version} → New version: {new_version}")
    print("\nNext steps:")
    print("1. Fix the critical issue(s) in this branch")
    print("2. Update the CHANGELOG.md with the fixes made")
    print(
        """3. Finalize the hotfix with 'gitflow_deploy.py finalize-release'
          (same command as regular releases)"""
    )


def finalize_hotfix() -> None:
    """Alias for finalize_release, as the process is the same."""
    return finalize_release()


def main() -> None:
    """Main function to handle deployment actions."""
    parser = argparse.ArgumentParser(
        description="GitFlow-based deployment tool for local-ssl-manager"
    )

    subparsers = parser.add_subparsers(dest="action", help="Action to perform")

    # Start release command
    release_parser = subparsers.add_parser(
        "start-release", help="Start a new release branch from develop"
    )
    release_parser.add_argument(
        "--version-part",
        "-p",
        choices=["major", "minor", "patch"],
        default="patch",
        help="Which part of the version to increment (default: patch)",
    )
    release_parser.add_argument(
        "--version", "-v", help="Specific version to use (overrides version-part)"
    )

    # Finalize release command
    subparsers.add_parser(
        "finalize-release",
        help="Finalize a release branch by merging into main and develop",
    )

    # Hotfix command
    hotfix_parser = subparsers.add_parser(
        "hotfix", help="Start a new hotfix branch from main"
    )
    hotfix_parser.add_argument(
        "--version",
        "-v",
        help="Specific version to use (default: increment patch version)",
    )

    # Deploy command (legacy support for the original deploy.py script)
    deploy_parser = subparsers.add_parser(
        "deploy", help="Legacy deploy command (same as finalize-release)"
    )
    deploy_parser.add_argument(
        "--version", "-v", help="New version to deploy (X.Y.Z format)"
    )
    deploy_parser.add_argument("--message", "-m", help="Version tag message")

    args = parser.parse_args()

    # Check if git is available
    try:
        run_command("git --version", "Git is not installed")
    except Exception:
        print("Error: Git is not installed or not in PATH")
        sys.exit(1)

    # Execute the selected action
    if args.action == "start-release":
        start_release(args.version_part, args.version)
    elif args.action == "finalize-release":
        finalize_release()
    elif args.action == "hotfix":
        start_hotfix(args.version)
    elif args.action == "deploy":
        # Legacy support for deploy.py
        # Just run the finalize-release command
        finalize_release()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
