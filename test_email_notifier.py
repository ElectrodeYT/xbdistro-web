#!/usr/bin/env python3
"""
Test script for the email_notifier module.
This script tests the email notification functionality.
"""

import unittest
from unittest.mock import patch, MagicMock, call

from xbdistro_tools.email_notifier import EmailNotifier, notify_package_update


class TestEmailNotifier(unittest.TestCase):
    """Test cases for the EmailNotifier class."""

    def setUp(self):
        """Set up test environment."""
        self.email_notifier = EmailNotifier(
            smtp_server="smtp.example.com",
            smtp_port=587,
            smtp_username="user",
            smtp_password="pass",
            sender_email="sender@example.com",
            fallback_email="admin@example.com",
            use_tls=True
        )

    @patch('smtplib.SMTP')
    def test_send_update_notification_with_maintainer(self, mock_smtp):
        """Test sending an update notification to a package maintainer."""
        # Set up mock
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        # Call the method
        result = self.email_notifier.send_update_notification(
            package_name="test-package",
            source_name="test-source",
            local_version="1.0.0",
            upstream_version="2.0.0",
            repository="nixos",
            maintainer_email="maintainer@example.com"
        )

        # Check the result
        self.assertTrue(result)

        # Check that the SMTP server was used correctly
        mock_smtp.assert_called_once_with("smtp.example.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user", "pass")
        
        # Check that sendmail was called with the right parameters
        self.assertEqual(mock_server.sendmail.call_count, 1)
        args = mock_server.sendmail.call_args[0]
        self.assertEqual(args[0], "sender@example.com")
        self.assertEqual(args[1], "maintainer@example.com")
        # The third argument is the email message as a string, which is harder to check directly
        self.assertIn("Package: test-package", args[2])
        self.assertIn("Source: test-source", args[2])
        self.assertIn("Current Version: 1.0.0", args[2])
        self.assertIn("New Version: 2.0.0", args[2])
        self.assertIn("Repository: nixos", args[2])
        self.assertNotIn("UNMAINTAINED", args[2])

    @patch('smtplib.SMTP')
    def test_send_update_notification_unmaintained(self, mock_smtp):
        """Test sending an update notification for an unmaintained package."""
        # Set up mock
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        # Call the method
        result = self.email_notifier.send_update_notification(
            package_name="unmaintained-package",
            source_name="unmaintained-source",
            local_version="1.0.0",
            upstream_version="2.0.0",
            repository="nixos",
            maintainer_email=None
        )

        # Check the result
        self.assertTrue(result)

        # Check that sendmail was called with the right parameters
        self.assertEqual(mock_server.sendmail.call_count, 1)
        args = mock_server.sendmail.call_args[0]
        self.assertEqual(args[0], "sender@example.com")
        self.assertEqual(args[1], "admin@example.com")
        # Check that the email contains the UNMAINTAINED tag
        self.assertIn("[UNMAINTAINED]", args[2])
        self.assertIn("Package: unmaintained-package", args[2])
        self.assertIn("This package is currently unmaintained", args[2])

    @patch('smtplib.SMTP')
    def test_send_email_failure(self, mock_smtp):
        """Test handling of email sending failures."""
        # Set up mock to raise an exception
        mock_smtp.return_value.__enter__.side_effect = Exception("SMTP error")

        # Call the method
        result = self.email_notifier.send_update_notification(
            package_name="test-package",
            source_name="test-source",
            local_version="1.0.0",
            upstream_version="2.0.0",
            repository="nixos",
            maintainer_email="maintainer@example.com"
        )

        # Check the result
        self.assertFalse(result)


class TestNotifyPackageUpdate(unittest.TestCase):
    """Test cases for the notify_package_update function."""

    def setUp(self):
        """Set up test environment."""
        self.mock_db = MagicMock()
        self.mock_email_notifier = MagicMock()

    def test_notify_package_update_with_maintainer(self):
        """Test notifying about a package update with a maintainer."""
        # Set up mocks
        self.mock_db.get_latest_version_from_source.return_value = ["1.0.0"]
        self.mock_db.get_packages_by_source_name.return_value = [
            {
                'name': 'test-package',
                'maintainer': 'Test Maintainer <maintainer@example.com>'
            }
        ]

        # Call the function
        notify_package_update(
            source_name="test-source",
            version="2.0.0",
            repository="nixos",
            db=self.mock_db,
            email_notifier=self.mock_email_notifier
        )

        # Check that the email notifier was called correctly
        self.mock_email_notifier.send_update_notification.assert_called_once_with(
            package_name='test-package',
            source_name='test-source',
            local_version='1.0.0',
            upstream_version='2.0.0',
            repository='nixos',
            maintainer_email='maintainer@example.com'
        )

    def test_notify_package_update_unmaintained(self):
        """Test notifying about an unmaintained package update."""
        # Set up mocks
        self.mock_db.get_latest_version_from_source.return_value = ["1.0.0"]
        self.mock_db.get_packages_by_source_name.return_value = [
            {
                'name': 'unmaintained-package',
                'maintainer': None
            }
        ]

        # Call the function
        notify_package_update(
            source_name="unmaintained-source",
            version="2.0.0",
            repository="nixos",
            db=self.mock_db,
            email_notifier=self.mock_email_notifier
        )

        # Check that the email notifier was called correctly
        self.mock_email_notifier.send_update_notification.assert_called_once_with(
            package_name='unmaintained-package',
            source_name='unmaintained-source',
            local_version='1.0.0',
            upstream_version='2.0.0',
            repository='nixos',
            maintainer_email=None
        )

    def test_notify_package_update_multiple_packages(self):
        """Test notifying about multiple packages for one source."""
        # Set up mocks
        self.mock_db.get_latest_version_from_source.return_value = ["1.0.0"]
        self.mock_db.get_packages_by_source_name.return_value = [
            {
                'name': 'package1',
                'maintainer': 'Maintainer 1 <maintainer1@example.com>'
            },
            {
                'name': 'package2',
                'maintainer': 'Maintainer 2 <maintainer2@example.com>'
            }
        ]

        # Call the function
        notify_package_update(
            source_name="shared-source",
            version="2.0.0",
            repository="nixos",
            db=self.mock_db,
            email_notifier=self.mock_email_notifier
        )

        # Check that the email notifier was called for both packages
        expected_calls = [
            call(
                package_name='package1',
                source_name='shared-source',
                local_version='1.0.0',
                upstream_version='2.0.0',
                repository='nixos',
                maintainer_email='maintainer1@example.com'
            ),
            call(
                package_name='package2',
                source_name='shared-source',
                local_version='1.0.0',
                upstream_version='2.0.0',
                repository='nixos',
                maintainer_email='maintainer2@example.com'
            )
        ]
        self.mock_email_notifier.send_update_notification.assert_has_calls(expected_calls)
        self.assertEqual(self.mock_email_notifier.send_update_notification.call_count, 2)

    def test_notify_package_update_no_local_version(self):
        """Test handling when no local version is found."""
        # Set up mocks
        self.mock_db.get_latest_version_from_source.return_value = None

        # Call the function
        notify_package_update(
            source_name="test-source",
            version="2.0.0",
            repository="nixos",
            db=self.mock_db,
            email_notifier=self.mock_email_notifier
        )

        # Check that the email notifier was not called
        self.mock_email_notifier.send_update_notification.assert_not_called()

    def test_notify_package_update_no_email_notifier(self):
        """Test handling when no email notifier is provided."""
        # Call the function
        notify_package_update(
            source_name="test-source",
            version="2.0.0",
            repository="nixos",
            db=self.mock_db,
            email_notifier=None
        )

        # Check that the database was not queried
        self.mock_db.get_latest_version_from_source.assert_not_called()


if __name__ == "__main__":
    unittest.main()