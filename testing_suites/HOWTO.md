# Linux Testing Suite for local-ssl-manager

This directory contains testing environments for validating the `local-ssl-manager` package across different Linux distributions.

## Ubuntu Testing

The `Dockerfile.ubuntu` provides a containerized Ubuntu environment for testing the package functionality.

### Prerequisites
- Docker installed on your system

### Testing Steps

1. **Build the Docker image**:
   ```bash
   docker build -t ssl-manager-ubuntu -f Dockerfile.ubuntu .
   ```

2. **Run the container**:
   ```bash
   docker run -it --name ssl-manager-test ssl-manager-ubuntu
   ```

3. **Core functionality tests**:
   ```bash
   # Check package version
   ssl-manager --version

   # Create a certificate for a local domain
   ssl-manager create --domain test.local

   # List certificates
   ssl-manager list

   # Verify hosts file update
   cat /etc/hosts | grep test.local

   # Check certificate files
   ls -la ~/.local-ssl-manager/certs/
   ```

4. **Testing with sudo privileges**:
   ```bash
   # The testuser has sudo access with password 'password'
   sudo -E env "PATH=$PATH" ssl-manager create --domain sudo-test.local
   ```

5. **Testing domain removal**:
   ```bash
   ssl-manager delete --domain test.local --force
   ```

6. **Verify browser trust**:
   ```bash
   # Check CA certificate location and contents
   mkcert -CAROOT
   ls -la $(mkcert -CAROOT)
   ```

### Common Issues

- If `mkcert` isn't available, the package should attempt to install it automatically on Ubuntu
- Check that hosts file modifications work correctly both with and without sudo
- Verify that certificate files are created with correct permissions

### Exit the container

```bash
exit
```

### Clean up

```bash
# Stop and remove the container
docker stop ssl-manager-test
docker rm ssl-manager-test

# Optionally remove the image
docker rmi ssl-manager-ubuntu
```

## Adding More Linux Distributions

To test on additional Linux distributions, create new Dockerfiles following the same pattern:

1. Use the appropriate base image
2. Install Python and dependencies
3. Create a test user with sudo access
4. Set up a virtual environment
5. Install the package

Example naming convention: `Dockerfile.fedora`, `Dockerfile.alpine`, etc.
