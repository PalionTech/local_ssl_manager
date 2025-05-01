"""
Tests for the validators module.
"""

from local_ssl_manager.utils.validators import (
    validate_domain,
    validate_ip_address,
    validate_path,
)


class TestDomainValidator:
    """Tests for the domain validator function."""

    def test_valid_domains(self):
        """Test that valid domain names are accepted."""
        valid_domains = [
            "example.com",
            "test.local",
            "my-project.test",
            "sub.domain.example.com",
            "xn--80aswg.xn--p1ai",  # Internationalized domain
            "a" * 63 + ".com",  # Maximum label length
        ]

        for domain in valid_domains:
            is_valid, error = validate_domain(domain)
            assert is_valid is True
            assert error is None

    def test_invalid_domains(self):
        """Test that invalid domain names are rejected."""
        invalid_domains = [
            "",  # Empty string
            "domain",  # Missing TLD
            "-example.com",  # Starting with hyphen
            "example-.com",  # Ending with hyphen
            "exam ple.com",  # Contains space
            "exam_ple.com",  # Contains underscore
            "a" * 64 + ".com",  # Label too long
            "a" * 256,  # Domain too long
            ".example.com",  # Empty label
            "example..com",  # Empty label
        ]

        for domain in invalid_domains:
            is_valid, error = validate_domain(domain)
            assert is_valid is False
            assert error is not None


class TestIPValidator:
    """Tests for the IP address validator function."""

    def test_valid_ip_addresses(self):
        """Test that valid IP addresses are accepted."""
        valid_ips = [
            "127.0.0.1",
            "192.168.1.1",
            "10.0.0.1",
            "0.0.0.0",
            "255.255.255.255",
        ]

        for ip in valid_ips:
            is_valid, error = validate_ip_address(ip)
            assert is_valid is True
            assert error is None

    def test_invalid_ip_addresses(self):
        """Test that invalid IP addresses are rejected."""
        invalid_ips = [
            "",  # Empty string
            "127.0.0",  # Too few octets
            "127.0.0.1.1",  # Too many octets
            "127.0.0.256",  # Octet too large
            "127.0.0.-1",  # Negative octet
            "127.0.0.1a",  # Non-numeric character
            "127.0.0,1",  # Invalid separator
            "localhost",  # Not an IP address
        ]

        for ip in invalid_ips:
            is_valid, error = validate_ip_address(ip)
            assert is_valid is False
            assert error is not None


class TestPathValidator:
    """Tests for the path validator function."""

    def test_valid_paths(self):
        """Test that valid paths are accepted."""
        valid_paths = [
            "/path/to/file",
            "relative/path",
            "file.txt",
            "C:\\Windows\\System32",
            "/usr/local/bin/",
        ]

        for path in valid_paths:
            is_valid, error = validate_path(path)
            print(f"HERE: {is_valid} | {error} | {path}")
            assert is_valid is True
            assert error is None

    def test_invalid_paths(self):
        """Test that invalid paths are rejected."""
        invalid_paths = [
            "",  # Empty string
            "path/with|pipe",  # Invalid pipe character
            "path/with?question",  # Invalid question mark
            'path/with"quotes',  # Invalid quotes
            "path/with*asterisk",  # Invalid asterisk
            "path/with>gt",  # Invalid greater than
            "path/with<lt",  # Invalid less than
        ]

        for path in invalid_paths:
            is_valid, error = validate_path(path)
            assert is_valid is False
            assert error is not None
