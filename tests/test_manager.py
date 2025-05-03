"""
Tests for the LocalSSLManager class.
"""

import json
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

import pytest

from local_ssl_manager.manager import LocalSSLManager


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def ssl_manager(temp_dir):
    """Create a LocalSSLManager instance with a temporary base directory."""
    manager = LocalSSLManager(base_dir=temp_dir)
    return manager


class TestLocalSSLManager:
    """Tests for the LocalSSLManager class."""

    def test_initialization(self, ssl_manager, temp_dir):
        """Test that the manager initializes with the correct directory structure."""
        # Check that directories were created
        assert (temp_dir / "certs").exists()
        assert (temp_dir / "logs").exists()
        assert (temp_dir / "config").exists()

        # Check that metadata file was created
        assert (temp_dir / "config" / "certificates.json").exists()

        # Check that metadata file contains an empty dict
        with open(temp_dir / "config" / "certificates.json", "r") as f:
            metadata = json.load(f)
            assert metadata == {}

    def test_save_load_metadata(self, ssl_manager, temp_dir):
        """Test saving and loading metadata."""
        # Create test metadata
        test_metadata = {
            "test.local": {
                "created_at": datetime.now().isoformat(),
                "cert_path": "/path/to/cert.crt",
                "key_path": "/path/to/key.key",
            }
        }

        # Save metadata
        ssl_manager._save_metadata(test_metadata)

        # Check that metadata file was updated
        with open(temp_dir / "config" / "certificates.json", "r") as f:
            saved_metadata = json.load(f)
            assert "test.local" in saved_metadata
            assert saved_metadata["test.local"]["cert_path"] == "/path/to/cert.crt"

        # Load metadata
        loaded_metadata = ssl_manager._load_metadata()

        # Check that loaded metadata matches saved metadata
        assert loaded_metadata == saved_metadata

    def test_check_domain_exists(self, ssl_manager):
        """Test checking if a domain exists."""
        # Save test metadata with a domain
        test_metadata = {
            "test.local": {
                "created_at": datetime.now().isoformat(),
                "cert_path": "/path/to/cert.crt",
                "key_path": "/path/to/key.key",
            }
        }
        ssl_manager._save_metadata(test_metadata)

        # Check that the domain exists
        assert ssl_manager.check_domain_exists("test.local") is True

        # Check that a non-existent domain doesn't exist
        # Mock the check_domain_in_hosts function to avoid actual system calls
        with mock.patch(
            "local_ssl_manager.utils.system.check_domain_in_hosts", return_value=False
        ):
            assert ssl_manager.check_domain_exists("nonexistent.local") is False

    @mock.patch("local_ssl_manager.manager.setup_browser_trust")
    @mock.patch("local_ssl_manager.manager.backup_hosts_file")
    @mock.patch("local_ssl_manager.manager.update_hosts_file")
    @mock.patch("local_ssl_manager.manager.create_certificate")
    def test_setup_local_domain(
        self,
        mock_create_cert,
        mock_update_hosts,
        mock_backup_hosts,
        mock_setup_trust,
        ssl_manager,
        temp_dir,
    ):
        """Test setting up a local domain with mocked dependencies."""
        # Configure mocks
        mock_setup_trust.return_value = True
        mock_create_cert.return_value = (
            temp_dir / "certs" / "example.local.crt",
            temp_dir / "certs" / "example.local.key",
        )

        # Mock check_domain_exists to return False (domain doesn't exist)
        with mock.patch.object(ssl_manager, "check_domain_exists", return_value=False):
            # Call the method under test
            result = ssl_manager.setup_local_domain("example.local")

            # Check that browser trust was set up
            mock_setup_trust.assert_called_once()

            # Check that hosts file was backed up
            mock_backup_hosts.assert_called_once()

            # Check that hosts file was updated
            mock_update_hosts.assert_called_once_with("example.local", "127.0.0.1")

            # Check that certificate was created
            mock_create_cert.assert_called_once_with(
                "example.local", ssl_manager.certs_dir
            )

            # Check the result
            assert result["domain"] == "example.local"
            assert "cert_path" in result
            assert "key_path" in result

            # Check that metadata was updated
            metadata = ssl_manager._load_metadata()
            assert "example.local" in metadata

    def test_get_domain_hierarchy(self, ssl_manager):
        """Test getting the domain hierarchy."""
        # Create test metadata with domains
        now = datetime.now()
        yesterday = now - timedelta(days=1)

        test_metadata = {
            "example.com": {
                "created_at": yesterday.isoformat(),
                "cert_path": "/path/to/cert1.crt",
                "key_path": "/path/to/key1.key",
            },
            "sub.example.com": {
                "created_at": now.isoformat(),
                "cert_path": "/path/to/cert2.crt",
                "key_path": "/path/to/key2.key",
            },
            "test.local": {
                "created_at": now.isoformat(),
                "cert_path": "/path/to/cert3.crt",
                "key_path": "/path/to/key3.key",
            },
        }
        ssl_manager._save_metadata(test_metadata)

        # Get domain hierarchy
        domains = ssl_manager.get_domain_hierarchy()

        # Check the result
        assert len(domains) == 3

        # Check that domains are sorted by hierarchy (number of dots) and then alphabetically
        # First should be domains with 1 dot
        assert domains[0][0] in ["example.com", "test.local"]
        assert domains[1][0] in ["example.com", "test.local"]
        # Last should be the subdomain
        assert domains[2][0] == "sub.example.com"

    @mock.patch("pathlib.Path.unlink")
    @mock.patch("local_ssl_manager.manager.update_hosts_file")
    def test_delete_certificate(self, mock_update_hosts, mock_unlink, ssl_manager):
        """Test deleting a certificate with mocked dependencies."""
        # Create test metadata with a domain
        test_metadata = {
            "test.local": {
                "created_at": datetime.now().isoformat(),
                "cert_path": "/path/to/cert.crt",
                "key_path": "/path/to/key.key",
                "ip_address": "127.0.0.1",
            }
        }
        ssl_manager._save_metadata(test_metadata)

        # Mock Path.exists to return True
        with mock.patch("pathlib.Path.exists", return_value=True):
            # Call the method under test
            result = ssl_manager.delete_certificate("test.local")

            # Check that certificate files were deleted
            assert mock_unlink.call_count == 2

            # Check that hosts file was updated
            mock_update_hosts.assert_called_once_with(
                "test.local", "127.0.0.1", remove=True
            )

            # Check the result
            assert result is True

            # Check that metadata was updated
            metadata = ssl_manager._load_metadata()
            assert "test.local" not in metadata

    def test_delete_nonexistent_certificate(self, ssl_manager):
        """Test deleting a certificate that doesn't exist."""
        # Call the method under test with a non-existent domain
        with pytest.raises(ValueError):
            ssl_manager.delete_certificate("nonexistent.local")
