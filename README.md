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
