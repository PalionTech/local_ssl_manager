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
from typing import Any, Dict, Optional


class DeploymentAction(Enum):
    """Possible deployment actions."""

    START_RELEASE = "start-release"
    FINALIZE_RELEASE = "finalize-release"
    CONTINUE_RELEASE = "continue-release"
    HOTFIX = "hotfix"
    DEPLOY = "deploy"


class GitFlowState(Enum):
    """States during the release process."""

    INITIAL = "initial"
    MAIN_MERGED = "main_merged"
    MAIN_PUSHED = "main_pushed"
    TAG_CREATED = "tag_created"
    TAG_PUSHED = "tag_pushed"
    DEVELOP_MERGED = "develop_merged"
    COMPLETED = "completed"


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
    """Update the version in pyproject.toml and __init__.py."""
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


def run_command(
    command: str,
    error_message: str,
    capture_output: bool = True,
    check: bool = True,
    no_verify: bool = False,
) -> str:
    """Run a shell command and exit if it fails."""
    print(f"Running: {command}")

    # Add --no-verify for git commit commands if requested
    if no_verify and "git commit" in command:
        command = command.replace("git commit", "git commit --no-verify")

    try:
        result = subprocess.run(
            command, shell=True, capture_output=capture_output, text=True
        )
        if check and result.returncode != 0:
            print(f"Error: {error_message}")
            print(f"Command output: {result.stderr}")
            return ""
        return result.stdout.strip() if capture_output else ""
    except subprocess.SubprocessError as e:
        if check:
            print(f"Error: {error_message}")
            print(f"Command error: {str(e)}")
            sys.exit(1)
        return ""


def git_is_clean() -> bool:
    """Check if the git working directory is clean."""
    result = subprocess.run(
        "git status --porcelain", shell=True, capture_output=True, text=True
    )
    return result.stdout.strip() == ""


def get_current_branch() -> str:
    """Get the name of the current git branch."""
    return run_command("git branch --show-current", "Failed to get current branch")


def save_state(state: Dict[str, Any], state_file: Optional[Path] = None) -> None:
    """Save GitFlow state to a file."""
    if state_file is None:
        state_file = Path(".gitflow_state.txt")

    content = "\n".join([f"{k}={v}" for k, v in state.items()])
    with open(state_file, "w") as f:
        f.write(content)
    print(f"Saved deployment state to {state_file}")


def load_state(state_file: Optional[Path] = None) -> Dict[str, Any]:
    """Load GitFlow state from a file."""
    if state_file is None:
        state_file = Path(".gitflow_state.txt")

    if not state_file.exists():
        return {}

    state = {}
    with open(state_file, "r") as f:
        for line in f.readlines():
            if "=" in line:
                key, value = line.strip().split("=", 1)
                state[key] = value

    return state


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


def start_release(
    version_part: str, version: Optional[str] = None, no_verify: bool = False
) -> None:
    """
    Start a new release branch from develop.

    Args:
        version_part: Which part to increment: 'major', 'minor', or 'patch'
        version: Specific version to use (optional)
        no_verify: Skip pre-commit hooks when committing
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
        no_verify=no_verify,
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


def attempt_merge(
    source_branch: str,
    target_branch: str,
    message: str,
    no_verify: bool = False,
) -> bool:
    """
    Attempt to merge source branch into target branch, handling conflicts gracefully.

    Args:
        source_branch: Branch to merge from
        target_branch: Branch to merge to
        message: Commit message for the merge
        no_verify: Skip pre-commit hooks

    Returns:
        True if merge succeeded, False if conflicts occurred
    """
    # Make sure we're on the target branch
    current_branch = get_current_branch()
    if current_branch != target_branch:
        run_command(
            f"git checkout {target_branch}", f"Failed to checkout {target_branch}"
        )

    # Make sure target branch is up to date
    run_command(
        f"git pull origin {target_branch}",
        f"Failed to pull latest changes from {target_branch}",
    )

    # Attempt the merge
    merge_command = f'git merge --no-ff {source_branch} -m "{message}"'
    if no_verify:
        merge_command = merge_command.replace("git merge", "git merge --no-verify")

    result = subprocess.run(merge_command, shell=True, capture_output=True, text=True)

    # Check for conflicts
    if result.returncode != 0:
        if "Automatic merge failed" in result.stderr or "CONFLICT" in result.stderr:
            print(
                f"\n⚠️ Merge conflicts detected when merging {source_branch} into {target_branch}!"
            )
            print("Please resolve the conflicts manually, then commit the changes.")
            return False
        else:
            # Some other error
            print(f"Error: Failed to merge {source_branch} into {target_branch}")
            print(f"Command output: {result.stderr}")
            sys.exit(1)

    return True


def finalize_release(no_verify: bool = False) -> None:
    """
    Finalize a release by merging into main and develop.

    Args:
        no_verify: Skip pre-commit hooks when committing
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
    branch_match = re.search(r"/(v[0-9]+\.[0-9]+\.[0-9]+)$", current_branch)
    if branch_match:
        version = branch_match.group(1)[1:]  # Remove the 'v' prefix
    else:
        # Try to get from pyproject.toml instead
        version = get_current_version()

    if not validate_version(version):
        sys.exit(1)

    # Make sure release branch is up to date
    run_command(f"git pull origin {current_branch}", "Failed to pull latest changes")

    # Initialize state
    state = {
        "release_branch": current_branch,
        "version": version,
        "state": GitFlowState.INITIAL.value,
    }
    save_state(state)

    # Step 1: Merge to main
    print("\nStep 1: Merging release branch to main...")
    merge_success = attempt_merge(
        current_branch,
        "main",
        f"Merge {current_branch} into main",
        no_verify,
    )

    if not merge_success:
        print("\n🛑 Merge conflicts detected!")
        print("Please follow these steps to resolve the conflicts:")
        print("1. Resolve the conflicts in the affected files")
        print("2. Stage the resolved files with 'git add <file>'")
        print("3. Commit the changes with 'git commit'")
        print("4. Run 'python gitflow_deploy.py continue-release --target=main'")
        sys.exit(1)

    # Update state - main merged successfully
    state["state"] = GitFlowState.MAIN_MERGED.value
    save_state(state)

    # Push changes to main
    push_result = run_command("git push origin main", "Failed to push main to remote")
    if not push_result:
        print("\n🛑 Failed to push to main!")
        print("Please resolve any issues and then run:")
        print("'python gitflow_deploy.py continue-release --target=main-push'")
        sys.exit(1)

    # Update state - main pushed successfully
    state["state"] = GitFlowState.MAIN_PUSHED.value
    save_state(state)

    # Create version tag
    tag_name = f"v{version}"
    tag_result = run_command(
        f'git tag -a {tag_name} -m "Version {version}"', "Failed to create tag"
    )

    if (
        not tag_result and tag_result != ""
    ):  # Empty string is valid for commands with no output
        print("\n🛑 Failed to create version tag!")
        print("Please resolve any issues and then run:")
        print("'python gitflow_deploy.py continue-release --target=tag'")
        sys.exit(1)

    # Update state - tag created successfully
    state["state"] = GitFlowState.TAG_CREATED.value
    save_state(state)

    # Push tag
    tag_push_result = run_command(
        f"git push origin {tag_name}", "Failed to push tag to remote"
    )

    if not tag_push_result and tag_push_result != "":
        print("\n🛑 Failed to push tag!")
        print("Please resolve any issues and then run:")
        print("'python gitflow_deploy.py continue-release --target=tag-push'")
        sys.exit(1)

    # Update state - tag pushed successfully
    state["state"] = GitFlowState.TAG_PUSHED.value
    save_state(state)

    # Step 2: Merge to develop
    print("\nStep 2: Merging release branch to develop...")
    develop_merge_success = attempt_merge(
        current_branch,
        "develop",
        f"Merge {current_branch} back into develop",
        no_verify,
    )

    if not develop_merge_success:
        print("\n🛑 Merge conflicts detected when merging to develop!")
        print("Please follow these steps to resolve the conflicts:")
        print("1. Resolve the conflicts in the affected files")
        print("2. Stage the resolved files with 'git add <file>'")
        print("3. Commit the changes with 'git commit'")
        print("4. Run 'python gitflow_deploy.py continue-release --target=develop'")
        sys.exit(1)

    # Update state - develop merged successfully
    state["state"] = GitFlowState.DEVELOP_MERGED.value
    save_state(state)

    # Push develop
    develop_push_result = run_command(
        "git push origin develop", "Failed to push develop to remote"
    )

    if not develop_push_result and develop_push_result != "":
        print("\n🛑 Failed to push develop!")
        print("Please resolve any issues and then run:")
        print("'python gitflow_deploy.py continue-release --target=develop-push'")
        sys.exit(1)

    # Step 3: Delete release branch
    print("\nStep 3: Cleaning up release branch...")
    run_command(
        f"git branch -d {current_branch}",
        "Failed to delete local release branch",
        check=False,
    )
    run_command(
        f"git push origin -d {current_branch}",
        "Failed to delete remote release branch",
        check=False,
    )

    # Update state - completed
    state["state"] = GitFlowState.COMPLETED.value
    save_state(state)

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

    # Remove state file after successful completion
    try:
        Path(".gitflow_state.txt").unlink(missing_ok=True)
    except Exception:
        print("Error unlinking .gitflow_state.txt")
        pass


def continue_release(target: str, no_verify: bool = False) -> None:
    """
    Continue a release process after resolving conflicts or issues.

    Args:
        target: The target step to continue from
        no_verify: Skip pre-commit hooks when committing
    """
    # Load saved state
    state = load_state()
    if not state:
        print(
            "Error: No saved state found. Please start the release process from the beginning."
        )
        sys.exit(1)

    release_branch = state.get("release_branch", "")
    version = state.get("version", "")

    if not release_branch or not version:
        print("Error: Invalid state file. Missing critical information.")
        sys.exit(1)

    print(
        f"Continuing release process for version {version} from branch {release_branch}"
    )

    # Make sure the working directory is clean
    if not git_is_clean() and target not in ["main", "develop"]:
        print("Error: Working directory is not clean. Commit or stash changes first.")
        sys.exit(1)

    # Continue based on target
    if target == "main":
        # We're continuing after resolving conflicts in main
        current_branch = get_current_branch()
        if current_branch != "main":
            print(
                f"Error: Expected to be on main branch, but current branch is {current_branch}"
            )
            sys.exit(1)

        # First commit any pending changes
        if not git_is_clean():
            print("Committing resolved conflicts...")
            run_command(
                "git commit --no-edit",
                "Failed to commit resolved conflicts",
                no_verify=no_verify,
            )

        # Now push to main
        run_command("git push origin main", "Failed to push main to remote")

        # Update state
        state["state"] = GitFlowState.MAIN_PUSHED.value
        save_state(state)

        # Create and push tag
        tag_name = f"v{version}"
        run_command(
            f'git tag -a {tag_name} -m "Version {version}"', "Failed to create tag"
        )
        run_command(f"git push origin {tag_name}", "Failed to push tag to remote")

        # Update state
        state["state"] = GitFlowState.TAG_PUSHED.value
        save_state(state)

        # Merge to develop
        print("\nMerging release branch to develop...")
        develop_merge_success = attempt_merge(
            release_branch,
            "develop",
            f"Merge {release_branch} back into develop",
            no_verify,
        )

        if not develop_merge_success:
            print("\n🛑 Merge conflicts detected when merging to develop!")
            print("Please follow these steps to resolve the conflicts:")
            print("1. Resolve the conflicts in the affected files")
            print("2. Stage the resolved files with 'git add <file>'")
            print("3. Commit the changes with 'git commit'")
            print("4. Run 'python gitflow_deploy.py continue-release --target=develop'")
            sys.exit(1)

        # Push develop
        run_command("git push origin develop", "Failed to push develop to remote")

        # Update state
        state["state"] = GitFlowState.DEVELOP_MERGED.value
        save_state(state)

        # Cleanup
        complete_release_process(release_branch, version, state)

    elif target == "develop":
        # We're continuing after resolving conflicts in develop
        current_branch = get_current_branch()
        if current_branch != "develop":
            print(
                f"Error: Expected to be on develop branch, but current branch is {current_branch}"
            )
            sys.exit(1)

        # First commit any pending changes
        if not git_is_clean():
            print("Committing resolved conflicts...")
            run_command(
                "git commit --no-edit",
                "Failed to commit resolved conflicts",
                no_verify=no_verify,
            )

        # Now push to develop
        run_command("git push origin develop", "Failed to push develop to remote")

        # Update state
        state["state"] = GitFlowState.DEVELOP_MERGED.value
        save_state(state)

        # Cleanup
        complete_release_process(release_branch, version, state)

    elif target == "main-push":
        # We were unable to push to main
        current_branch = get_current_branch()
        if current_branch != "main":
            run_command("git checkout main", "Failed to checkout main branch")

        # Try pushing again
        run_command("git push origin main", "Failed to push main to remote")

        # Update state
        state["state"] = GitFlowState.MAIN_PUSHED.value
        save_state(state)

        # Continue with tag
        tag_name = f"v{version}"
        run_command(
            f'git tag -a {tag_name} -m "Version {version}"', "Failed to create tag"
        )
        run_command(f"git push origin {tag_name}", "Failed to push tag to remote")

        # Update state
        state["state"] = GitFlowState.TAG_PUSHED.value
        save_state(state)

        # Continue with develop
        print("\nMerging release branch to develop...")
        develop_merge_success = attempt_merge(
            release_branch,
            "develop",
            f"Merge {release_branch} back into develop",
            no_verify,
        )

        if not develop_merge_success:
            print("\n🛑 Merge conflicts detected when merging to develop!")
            print("Please follow these steps to resolve the conflicts:")
            print("1. Resolve the conflicts in the affected files")
            print("2. Stage the resolved files with 'git add <file>'")
            print("3. Commit the changes with 'git commit'")
            print("4. Run 'python gitflow_deploy.py continue-release --target=develop'")
            sys.exit(1)

        # Push develop
        run_command("git push origin develop", "Failed to push develop to remote")

        # Update state
        state["state"] = GitFlowState.DEVELOP_MERGED.value
        save_state(state)

        # Cleanup
        complete_release_process(release_branch, version, state)

    elif target in ["tag", "tag-push", "develop-push"]:
        # Handle these specific continuation points
        if target == "tag":
            # Create tag
            tag_name = f"v{version}"
            run_command(
                f'git tag -a {tag_name} -m "Version {version}"', "Failed to create tag"
            )
            run_command(f"git push origin {tag_name}", "Failed to push tag to remote")

            # Update state
            state["state"] = GitFlowState.TAG_PUSHED.value
            save_state(state)

            # Continue with develop
            continue_with_develop(release_branch, version, state, no_verify)

        elif target == "tag-push":
            # Push tag
            tag_name = f"v{version}"
            run_command(f"git push origin {tag_name}", "Failed to push tag to remote")

            # Update state
            state["state"] = GitFlowState.TAG_PUSHED.value
            save_state(state)

            # Continue with develop
            continue_with_develop(release_branch, version, state, no_verify)

        elif target == "develop-push":
            # Push develop
            run_command("git checkout develop", "Failed to checkout develop branch")
            run_command("git push origin develop", "Failed to push develop to remote")

            # Update state
            state["state"] = GitFlowState.DEVELOP_MERGED.value
            save_state(state)

            # Cleanup
            complete_release_process(release_branch, version, state)
    else:
        print(f"Error: Unknown target '{target}'")
        print("Valid targets: main, main-push, tag, tag-push, develop, develop-push")
        sys.exit(1)


def continue_with_develop(
    release_branch: str, version: str, state: Dict[str, Any], no_verify: bool
) -> None:
    """Continue the release process with the develop branch merge."""
    print("\nMerging release branch to develop...")
    develop_merge_success = attempt_merge(
        release_branch,
        "develop",
        f"Merge {release_branch} back into develop",
        no_verify,
    )

    if not develop_merge_success:
        print("\n🛑 Merge conflicts detected when merging to develop!")
        print("Please follow these steps to resolve the conflicts:")
        print("1. Resolve the conflicts in the affected files")
        print("2. Stage the resolved files with 'git add <file>'")
        print("3. Commit the changes with 'git commit'")
        print("4. Run 'python gitflow_deploy.py continue-release --target=develop'")
        sys.exit(1)

    # Push develop
    run_command("git push origin develop", "Failed to push develop to remote")

    # Update state
    state["state"] = GitFlowState.DEVELOP_MERGED.value
    save_state(state)

    # Cleanup
    complete_release_process(release_branch, version, state)


def complete_release_process(
    release_branch: str, version: str, state: Dict[str, Any]
) -> None:
    """Complete the release process by cleaning up and showing success message."""
    # Delete release branch
    run_command(
        f"git branch -d {release_branch}",
        "Failed to delete local release branch",
        check=False,
    )
    run_command(
        f"git push origin -d {release_branch}",
        "Failed to delete remote release branch",
        check=False,
    )

    # Update state - completed
    state["state"] = GitFlowState.COMPLETED.value
    save_state(state)

    print(f"\n✅ Release v{version} finalized successfully!")
    print(f"Version tag v{version} created and pushed.")
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

    # Remove state file after successful completion
    try:
        Path(".gitflow_state.txt").unlink(missing_ok=True)
    except Exception:
        print("Error unlinking .gitflow_state.txt")
        pass


def start_hotfix(version: Optional[str] = None, no_verify: bool = False) -> None:
    """
    Start a hotfix branch from main.

    Args:
        version: Specific version to use (optional)
        no_verify: Skip pre-commit hooks when committing
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
        no_verify=no_verify,
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
        "3. Finalize the hotfix with 'python gitflow_deploy.py finalize-release' when ready"
    )


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
    release_parser.add_argument(
        "--no-verify",
        "-n",
        action="store_true",
        help="Skip pre-commit hooks when committing",
    )

    # Finalize release command
    finalize_parser = subparsers.add_parser(
        "finalize-release",
        help="Finalize a release branch by merging into main and develop",
    )
    finalize_parser.add_argument(
        "--no-verify",
        "-n",
        action="store_true",
        help="Skip pre-commit hooks when committing",
    )

    # Continue release command
    continue_parser = subparsers.add_parser(
        "continue-release",
        help="Continue a release after resolving conflicts or issues",
    )
    continue_parser.add_argument(
        "--target",
        "-t",
        required=True,
        help="Target step to continue from (main, main-push, tag, tag-push, develop, develop-push)",
    )
    continue_parser.add_argument(
        "--no-verify",
        "-n",
        action="store_true",
        help="Skip pre-commit hooks when committing",
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
    hotfix_parser.add_argument(
        "--no-verify",
        "-n",
        action="store_true",
        help="Skip pre-commit hooks when committing",
    )

    # Deploy command (legacy support for the original deploy.py script)
    deploy_parser = subparsers.add_parser(
        "deploy", help="Legacy deploy command (same as finalize-release)"
    )
    deploy_parser.add_argument(
        "--version", "-v", help="New version to deploy (X.Y.Z format)"
    )
    deploy_parser.add_argument("--message", "-m", help="Version tag message")
    deploy_parser.add_argument(
        "--no-verify",
        "-n",
        action="store_true",
        help="Skip pre-commit hooks when committing",
    )

    args = parser.parse_args()

    # Check if git is available
    try:
        run_command("git --version", "Git is not installed")
    except Exception:
        print("Error: Git is not installed or not in PATH")
        sys.exit(1)

    # Execute the selected action
    if args.action == "start-release":
        start_release(args.version_part, args.version, args.no_verify)
    elif args.action == "finalize-release":
        finalize_release(args.no_verify)
    elif args.action == "continue-release":
        continue_release(args.target, args.no_verify)
    elif args.action == "hotfix":
        start_hotfix(args.version, args.no_verify)
    elif args.action == "deploy":
        # Legacy support for deploy.py
        # Just run the finalize-release command
        finalize_release(args.no_verify)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
