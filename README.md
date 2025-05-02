# Local SSL Manager

A command-line tool to create and manage local SSL certificates for development environments.

## Features

- Create self-signed SSL certificates for local domains
- Automatically update /etc/hosts file
- Set up browser trust for the certificates
- Domain-specific logging
- Interactive domain management

## Installation

```bash
pip install local-ssl-manager
```

## Requirements

- Python 3.8 or higher
- `mkcert` tool (will be installed automatically if possible)
- Admin/sudo privileges (for /etc/hosts and certificate installation)

## Usage

### Create a new local domain with SSL certificate

```bash
ssl-manager create --domain myproject.local
```

### Create a single certificate for multiple domains

```bash
ssl-manager create-multi --domains "app.local,api.local,admin.local"
```

### Delete a domain and its certificate

```bash
ssl-manager delete
```

This will show an interactive selector to choose which domain to delete.

### List all managed domains

```bash
ssl-manager list
```

### Export a certificate for use elsewhere

```bash
ssl-manager export --domain myproject.local --output /path/to/export/dir
```

### Import an existing certificate

```bash
ssl-manager import-cert --domain myproject.local --cert /path/to/cert.crt --key /path/to/key.key
```

### View help

```bash
ssl-manager --help
```

## Configuration

By default, Local SSL Manager stores all certificates and configuration in `~/.local-ssl-manager/`.
You can customize the location by setting the `SSL_MANAGER_HOME` environment variable.

## How it works

1. Creates a local Certificate Authority (CA) using mkcert
2. Installs the CA certificate in your system and browser trust stores
3. Creates domain-specific certificates signed by your local CA
4. Updates your hosts file to point the domains to 127.0.0.1
5. Maintains metadata about your certificates for easy management

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup

1. Clone the repository
2. Install development dependencies:

   ```bash
   pip install -e ".[dev]"
   ```

3. Install pre-commit hooks:

   ```bash
   pip install pre-commit
   pre-commit install
   ```

## Release Process

This project uses semantic versioning and releases from tags. The package is automatically built and published to PyPI when a new version tag is pushed using GitHub Actions.

### Using the Deployment Script (Recommended)

The easiest way to deploy a new version is to use the included deployment script:

1. Ensure you're on the main branch with a clean working directory
2. Run the deployment script:

   ```bash
   # Option 1: Interactive mode (will prompt for version and tag message)
   python deploy.py

   # Option 2: Non-interactive mode
   python deploy.py --version 0.1.1 --message "Add new features X and Y"
   ```

3. The script will:
   - Update the version in pyproject.toml
   - Commit the change
   - Create and push a Git tag
   - Push changes to GitHub
   - GitHub Actions will automatically build and publish to PyPI

### Manual Deployment

If you prefer to deploy manually:

1. Update the version in `pyproject.toml`
2. Commit the change:

   ```bash
   git commit -am "Bump version to 0.1.1"
   ```

3. Create a tag with a message:

   ```bash
   git tag -a v0.1.1 -m "Version 0.1.1: Add new features X and Y"
   ```

4. Push the changes and tag:

   ```bash
   git push origin main
   git push origin v0.1.1
   ```

5. GitHub Actions will detect the new tag and publish to PyPI

### Verifying Deployment

After pushing the tag:

1. Check the GitHub Actions workflow at: `https://github.com/PalionTech/local-ssl-manager/actions`
2. Verify the new version appears on PyPI: `https://pypi.org/project/local-ssl-manager/`
