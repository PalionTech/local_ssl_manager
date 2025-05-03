"""
Tests for the certificate utility functions.
"""

from unittest import mock

import pytest

from local_ssl_manager.utils.certificate import (
    check_certificate_validity,
    create_certificate,
    create_multi_domain_certificate,
    extract_domains,
    extract_field,
    get_certificate_expiry,
)


class TestCertificateUtils:
    """Test the certificate utility functions."""

    @mock.patch("local_ssl_manager.utils.certificate.check_command_exists")
    @mock.patch("local_ssl_manager.utils.certificate.install_mkcert")
    @mock.patch("subprocess.run")
    def test_create_certificate(
        self, mock_subprocess_run, mock_install_mkcert, mock_check_command, tmp_path
    ):
        """Test creating a certificate."""
        # Configure mocks
        mock_check_command.return_value = True  # mkcert is available
        mock_install_mkcert.return_value = True  # mkcert install would succeed

        # Mock successful subprocess run
        mock_subprocess_run.return_value.returncode = 0

        # Create test files to simulate successful certificate creation
        cert_dir = tmp_path / "certs"
        cert_dir.mkdir()
        cert_path = cert_dir / "test.local.crt"
        key_path = cert_dir / "test.local.key"
        cert_path.touch()
        key_path.touch()

        # Call the function
        result_cert_path, result_key_path = create_certificate("test.local", cert_dir)

        # Check the subprocess call
        mock_subprocess_run.assert_called_once()
        cmd_args = mock_subprocess_run.call_args[0][0]
        assert cmd_args[0] == "mkcert"
        assert "test.local" in cmd_args

        # Check the results
        assert result_cert_path == cert_path
        assert result_key_path == key_path

    @mock.patch("local_ssl_manager.utils.certificate.check_command_exists")
    @mock.patch("subprocess.run")
    def test_create_certificate_failure(
        self, mock_subprocess_run, mock_check_command, tmp_path
    ):
        """Test certificate creation failure."""
        # Configure mocks
        mock_check_command.return_value = True  # mkcert is available

        # Mock subprocess failure
        mock_subprocess_run.side_effect = Exception("Command failed")

        # Call the function and check exception
        with pytest.raises(RuntimeError):
            create_certificate("test.local", tmp_path / "certs")

    @mock.patch("local_ssl_manager.utils.certificate.check_command_exists")
    @mock.patch("local_ssl_manager.utils.certificate.install_mkcert")
    @mock.patch("subprocess.run")
    def test_create_multi_domain_certificate(
        self, mock_subprocess_run, mock_install_mkcert, mock_check_command, tmp_path
    ):
        """Test creating a multi-domain certificate."""
        # Configure mocks
        mock_check_command.return_value = True  # mkcert is available
        mock_install_mkcert.return_value = True  # mkcert install would succeed

        # Mock successful subprocess run
        mock_subprocess_run.return_value.returncode = 0

        # Create test files to simulate successful certificate creation
        cert_dir = tmp_path / "certs"
        cert_dir.mkdir()
        cert_path = cert_dir / "multi-domain.crt"
        key_path = cert_dir / "multi-domain.key"
        cert_path.touch()
        key_path.touch()

        # Call the function
        domains = ["test1.local", "test2.local", "test3.local"]
        result_cert_path, result_key_path = create_multi_domain_certificate(
            domains, cert_dir
        )

        # Check the subprocess call
        mock_subprocess_run.assert_called_once()
        cmd_args = mock_subprocess_run.call_args[0][0]
        assert cmd_args[0] == "mkcert"
        for domain in domains:
            assert domain in cmd_args

        # Check the results
        assert result_cert_path == cert_path
        assert result_key_path == key_path

    @mock.patch("subprocess.run")
    def test_check_certificate_validity(self, mock_subprocess_run, tmp_path):
        """Test checking certificate validity."""
        # Create a test certificate file
        cert_path = tmp_path / "test.crt"
        cert_path.touch()

        # Mock openssl output
        mock_subprocess_run.return_value.stdout = """
        Certificate:
            Data:
                Version: 3 (0x2)
                Serial Number: 12345 (0x3039)
            Signature Algorithm: sha256WithRSAEncryption
                Issuer: CN=mkcert development CA
                Validity
                    Not Before: Jan 1 00:00:00 2023 GMT
                    Not After : Dec 31 23:59:59 2023 GMT
                Subject: CN=test.local
                Subject Public Key Info:
                    Public Key Algorithm: rsaEncryption
                X509v3 extensions:
                    X509v3 Subject Alternative Name:
                        DNS:test.local, DNS:*.test.local
        """

        # Call the function
        result = check_certificate_validity(cert_path)

        # Check the result
        assert result["status"] == "valid"
        assert "test.local" in result["subject"]
        assert "mkcert development CA" in result["issuer"]
        assert "Jan 1 00:00:00 2023 GMT" in result["valid_from"]
        assert "Dec 31 23:59:59 2023 GMT" in result["valid_to"]
        assert "test.local" in result["domains"]

    def test_extract_field(self):
        """Test extracting fields from certificate text."""
        text = """
        Subject: CN=test.local
        Issuer: CN=mkcert development CA
        Validity
            Not Before: Jan 1 00:00:00 2023 GMT
            Not After : Dec 31 23:59:59 2023 GMT
        """

        assert extract_field(text, "Subject:") == "CN=test.local"
        assert extract_field(text, "Issuer:") == "CN=mkcert development CA"
        assert extract_field(text, "Not Before:") == "Jan 1 00:00:00 2023 GMT"
        assert extract_field(text, "Not After :") == "Dec 31 23:59:59 2023 GMT"
        assert extract_field(text, "Not Present:") == ""

    def test_extract_domains(self):
        """Test extracting domains from certificate text."""
        text = """
        Subject: CN=test.local
        X509v3 Subject Alternative Name:
            DNS:test.local, DNS:*.test.local, DNS:another.local
        """

        domains = extract_domains(text)
        assert "test.local" in domains
        assert "*.test.local" in domains
        assert "another.local" in domains

    @mock.patch("local_ssl_manager.utils.certificate.check_certificate_validity")
    def test_get_certificate_expiry(self, mock_check_validity, tmp_path):
        """Test getting certificate expiry date."""
        # Create a test certificate file
        cert_path = tmp_path / "test.crt"
        cert_path.touch()

        # Mock validity check
        mock_check_validity.return_value = {
            "status": "valid",
            "valid_to": "Dec 31 23:59:59 2023 GMT",
        }

        # Call the function
        expiry = get_certificate_expiry(cert_path)

        # Check the result
        assert expiry == "Dec 31 23:59:59 2023 GMT"

        # Test with invalid certificate
        mock_check_validity.return_value = {
            "status": "invalid",
            "error": "Certificate not found",
        }

        expiry = get_certificate_expiry(cert_path)
        assert expiry is None
