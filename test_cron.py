#!/usr/bin/env python3
"""
Test script for the xbdistro_cron module.
This script tests the basic functionality of the cron job.
"""

import os
import sys
import tempfile
import unittest
import subprocess
from unittest.mock import patch, MagicMock, call

from xbdistro_tools.cron import PackageDatabaseUpdater


class TestPackageDatabaseUpdater(unittest.TestCase):
    """Test cases for the PackageDatabaseUpdater class."""

    def setUp(self):
        """Set up test environment."""
        # Create a temporary database file
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()

        # Mock callbacks
        self.mock_package_added = MagicMock()
        self.mock_package_removed = MagicMock()
        self.mock_local_version_updated = MagicMock()
        self.mock_upstream_version_updated = MagicMock()

        # Path to xbstrap distribution
        self.xbstrap_path = "bootstrap-managarm"

        # Create patcher for xbstrap.base.Config
        self.mock_config_patcher = patch('xbdistro_tools.cron.xbstrap.base.Config')
        self.mock_config = self.mock_config_patcher.start()

        # Set up mock distro
        self.mock_distro = MagicMock()
        self.mock_config.return_value = self.mock_distro

        # Set up mock sources and packages
        self.mock_source1 = MagicMock()
        self.mock_source1.name = "source1"
        self.mock_source1.version = "1.0.0"

        self.mock_source2 = MagicMock()
        self.mock_source2.name = "source2"
        self.mock_source2.version = "2.0.0"

        self.mock_package1 = MagicMock()
        self.mock_package1.name = "package1"
        self.mock_package1.source = "source1"
        self.mock_package1._this_yml = {"metadata": {
            "maintainer": "Test Maintainer",
            "website": "https://example.com",
            "spdx": "MIT",
            "categories": ["test"],
            "summary": "Test package",
            "description": "A test package"
        }}
        self.mock_package1._subpkg_yml = None

        self.mock_package2 = MagicMock()
        self.mock_package2.name = "package2"
        self.mock_package2.source = "source2"
        self.mock_package2._this_yml = {"metadata": {
            "maintainer": "Another Maintainer",
            "website": "https://example.org",
            "spdx": "Apache-2.0",
            "categories": ["test", "example"],
            "summary": "Another test package",
            "description": "Another test package for testing"
        }}
        self.mock_package2._subpkg_yml = None

        # Set up mock NixOSVersionProvider
        self.mock_nixos_patcher = patch('xbdistro_tools.cron.NixOSVersionProvider')
        self.mock_nixos = self.mock_nixos_patcher.start()
        self.mock_nixos_instance = MagicMock()
        self.mock_nixos.return_value = self.mock_nixos_instance
        self.mock_nixos_instance.get_version.side_effect = lambda name: {"source1": "1.1.0", "source2": "2.1.0"}.get(name)

    def tearDown(self):
        """Clean up after tests."""
        # Remove temporary database file
        os.unlink(self.temp_db.name)

        # Stop patchers
        self.mock_config_patcher.stop()
        self.mock_nixos_patcher.stop()

        # Stop any additional patchers that might have been created in tests
        for patcher in getattr(self, '_additional_patchers', []):
            patcher.stop()

    def test_update_database_new_sources(self):
        """Test updating the database with new sources."""
        # Set up mock distro to return our mock sources and packages
        self.mock_distro.all_sources.return_value = [self.mock_source1, self.mock_source2]
        self.mock_distro.all_pkgs.return_value = [self.mock_package1, self.mock_package2]

        # Mock database functions
        with patch('xbdistro_tools.db.PackageDatabase.get_all_source_names') as mock_get_all_source_names, \
             patch('xbdistro_tools.db.PackageDatabase.get_all_package_names') as mock_get_all_package_names, \
             patch('xbdistro_tools.db.PackageDatabase.get_package_by_name') as mock_get_package_by_name, \
             patch('xbdistro_tools.db.PackageDatabase.add_source_version') as mock_add_source_version, \
             patch('xbdistro_tools.db.PackageDatabase.add_package_metadata') as mock_add_package_metadata, \
             patch('xbdistro_tools.db.PackageDatabase.get_latest_version_from_source') as mock_get_latest_version:

            # Setup mocks
            mock_get_all_source_names.return_value = []
            mock_get_all_package_names.return_value = []
            mock_get_package_by_name.return_value = None
            mock_add_source_version.return_value = True
            mock_add_package_metadata.return_value = True
            mock_get_latest_version.return_value = None

            # Create updater with mock callbacks
            updater = PackageDatabaseUpdater(
                db_path=self.temp_db.name,
                xbstrap_path=self.xbstrap_path,
                upstream_sources=["nixos"],
                on_package_added=self.mock_package_added,
                on_package_removed=self.mock_package_removed,
                on_local_version_updated=self.mock_local_version_updated,
                on_upstream_version_updated=self.mock_upstream_version_updated
            )

            # Update the database
            updater.update_database()

            # Check that the callbacks were called correctly
            self.mock_package_added.assert_any_call("package1", "source1")
            self.mock_package_added.assert_any_call("package2", "source2")
            self.assertEqual(self.mock_package_added.call_count, 2)

            # Local version updates should not be called for new sources
            self.assertEqual(self.mock_local_version_updated.call_count, 0)

            # Upstream version updates should not be called for new sources
            self.assertEqual(self.mock_upstream_version_updated.call_count, 0)

            # Package removed should not be called
            self.assertEqual(self.mock_package_removed.call_count, 0)

            # Update again to test version updates
            self.mock_source1.version = "1.0.1"  # Change local version

            # Update mock for second run
            mock_get_all_source_names.return_value = ["source1", "source2"]
            mock_get_all_package_names.return_value = ["package1", "package2"]
            mock_get_latest_version.side_effect = lambda name, source: {
                ("source1", "local"): ["1.0.0"],
                ("source2", "local"): ["2.0.0"],
                ("source1", "nixos"): None,
                ("source2", "nixos"): None
            }.get((name, source))

            # Reset callbacks
            self.mock_local_version_updated.reset_mock()
            self.mock_upstream_version_updated.reset_mock()

            # Update again
            updater.update_database()

            # Now local version update should be called
            self.mock_local_version_updated.assert_called_once_with("source1", "1.0.1", "local")

            # Upstream version update should be called for both sources
            self.assertEqual(self.mock_upstream_version_updated.call_count, 2)
            self.mock_upstream_version_updated.assert_any_call("source1", "1.1.0", "nixos")
            self.mock_upstream_version_updated.assert_any_call("source2", "2.1.0", "nixos")

    def test_update_database_removed_packages(self):
        """Test updating the database with removed packages."""
        # First update with both sources
        self.mock_distro.all_sources.return_value = [self.mock_source1, self.mock_source2]
        self.mock_distro.all_pkgs.return_value = [self.mock_package1, self.mock_package2]

        # Mock database functions for package deletion
        with patch('xbdistro_tools.db.PackageDatabase.get_all_source_names') as mock_get_all_source_names, \
             patch('xbdistro_tools.db.PackageDatabase.get_all_package_names') as mock_get_all_package_names, \
             patch('xbdistro_tools.db.PackageDatabase.get_package_by_name') as mock_get_package_by_name, \
             patch('xbdistro_tools.db.PackageDatabase.get_packages_by_source_name') as mock_get_packages_by_source_name, \
             patch('xbdistro_tools.db.PackageDatabase.add_source_version') as mock_add_source_version, \
             patch('xbdistro_tools.db.PackageDatabase.add_package_metadata') as mock_add_package_metadata, \
             patch('xbdistro_tools.db.PackageDatabase.get_latest_version_from_source') as mock_get_latest_version, \
             patch('xbdistro_tools.db.PackageDatabase.delete_package') as mock_delete_package, \
             patch('xbdistro_tools.db.PackageDatabase.delete_source') as mock_delete_source, \
             patch('xbdistro_tools.db.PackageDatabase.close') as mock_close:

            # Setup mocks for first update
            mock_get_all_source_names.return_value = []
            mock_get_all_package_names.return_value = []
            mock_get_package_by_name.return_value = None
            mock_get_packages_by_source_name.return_value = []
            mock_add_source_version.return_value = True
            mock_add_package_metadata.return_value = True
            mock_get_latest_version.return_value = None
            mock_delete_package.return_value = True
            mock_delete_source.return_value = True

            updater = PackageDatabaseUpdater(
                db_path=self.temp_db.name,
                xbstrap_path=self.xbstrap_path,
                upstream_sources=["nixos"],
                on_package_added=self.mock_package_added,
                on_package_removed=self.mock_package_removed,
                on_local_version_updated=self.mock_local_version_updated,
                on_upstream_version_updated=self.mock_upstream_version_updated
            )

            # First update
            updater.update_database()

            # Then update with only one source
            self.mock_distro.all_sources.return_value = [self.mock_source1]
            self.mock_distro.all_pkgs.return_value = [self.mock_package1]

            # Setup mocks for second update
            mock_get_all_source_names.return_value = ["source1", "source2"]
            mock_get_all_package_names.return_value = ["package1", "package2"]
            mock_get_package_by_name.side_effect = lambda name: {
                "package1": {"name": "package1", "source_name": "source1"},
                "package2": {"name": "package2", "source_name": "source2"}
            }.get(name)
            # No packages associated with source2 to avoid double removal
            mock_get_packages_by_source_name.side_effect = lambda name: {
                "source1": [{"name": "package1"}],
                "source2": []
            }.get(name, [])

            # Reset mock callbacks
            self.mock_package_added.reset_mock()
            self.mock_package_removed.reset_mock()
            self.mock_local_version_updated.reset_mock()
            self.mock_upstream_version_updated.reset_mock()
            mock_delete_package.reset_mock()
            mock_delete_source.reset_mock()

            # Update again
            updater.update_database()

            # Package removed should be called for package2 (only once)
            self.mock_package_removed.assert_called_once_with("package2", "source2")

            # Delete package should be called for package2
            mock_delete_package.assert_called_once_with("package2")

            # Delete source should be called for source2
            mock_delete_source.assert_called_once_with("source2")

            # Make sure close is called
            updater.close()
            mock_close.assert_called_once()

    def test_delete_nonexistent_packages_and_sources(self):
        """Test deleting packages and sources that no longer exist."""
        # Setup mock database functions
        with patch('xbdistro_tools.db.PackageDatabase.get_all_source_names') as mock_get_all_source_names, \
             patch('xbdistro_tools.db.PackageDatabase.get_all_package_names') as mock_get_all_package_names, \
             patch('xbdistro_tools.db.PackageDatabase.get_package_by_name') as mock_get_package_by_name, \
             patch('xbdistro_tools.db.PackageDatabase.get_packages_by_source_name') as mock_get_packages_by_source_name, \
             patch('xbdistro_tools.db.PackageDatabase.add_source_version') as mock_add_source_version, \
             patch('xbdistro_tools.db.PackageDatabase.add_package_metadata') as mock_add_package_metadata, \
             patch('xbdistro_tools.db.PackageDatabase.get_latest_version_from_source') as mock_get_latest_version, \
             patch('xbdistro_tools.db.PackageDatabase.delete_package') as mock_delete_package, \
             patch('xbdistro_tools.db.PackageDatabase.delete_source') as mock_delete_source, \
             patch('xbdistro_tools.db.PackageDatabase.close') as mock_close:

            # Setup mocks
            mock_get_all_source_names.return_value = ["source1", "source2", "source3"]
            mock_get_all_package_names.return_value = ["package1", "package2", "package3"]
            mock_get_package_by_name.side_effect = lambda name: {
                "package1": {"name": "package1", "source_name": "source1"},
                "package2": {"name": "package2", "source_name": "source2"},
                "package3": {"name": "package3", "source_name": "source3"}
            }.get(name)
            mock_get_packages_by_source_name.side_effect = lambda name: {
                "source1": [{"name": "package1"}],
                "source2": [{"name": "package2"}],
                "source3": [{"name": "package3"}]
            }.get(name, [])
            mock_add_source_version.return_value = True
            mock_add_package_metadata.return_value = True
            mock_get_latest_version.return_value = None
            mock_delete_package.return_value = True
            mock_delete_source.return_value = True

            # Setup mock distro
            self.mock_distro.all_sources.return_value = [self.mock_source1]  # Only source1 exists
            self.mock_distro.all_pkgs.return_value = [self.mock_package1]    # Only package1 exists

            updater = PackageDatabaseUpdater(
                db_path=self.temp_db.name,
                xbstrap_path=self.xbstrap_path,
                upstream_sources=["nixos"],
                on_package_added=self.mock_package_added,
                on_package_removed=self.mock_package_removed,
                on_local_version_updated=self.mock_local_version_updated,
                on_upstream_version_updated=self.mock_upstream_version_updated
            )

            # Reset mock callbacks
            self.mock_package_added.reset_mock()
            self.mock_package_removed.reset_mock()
            self.mock_local_version_updated.reset_mock()
            self.mock_upstream_version_updated.reset_mock()

            # Update database
            updater.update_database()

            # Package removed should be called for package2 and package3
            self.assertEqual(self.mock_package_removed.call_count, 4)  # 2 from direct package removal + 2 from source removal
            self.mock_package_removed.assert_any_call("package2", "source2")
            self.mock_package_removed.assert_any_call("package3", "source3")

            # Delete package should be called for package2 and package3
            self.assertEqual(mock_delete_package.call_count, 4)  # 2 from direct package removal + 2 from source removal
            mock_delete_package.assert_any_call("package2")
            mock_delete_package.assert_any_call("package3")

            # Delete source should be called for source2 and source3
            self.assertEqual(mock_delete_source.call_count, 2)
            mock_delete_source.assert_any_call("source2")
            mock_delete_source.assert_any_call("source3")

            # Make sure close is called
            updater.close()
            mock_close.assert_called_once()

    def test_git_repository_update(self):
        """Test git repository update functionality."""
        # Initialize _additional_patchers if not already initialized
        if not hasattr(self, '_additional_patchers'):
            self._additional_patchers = []

        # Create patchers for os.path.isdir and subprocess.run
        self.mock_isdir_patcher = patch('os.path.isdir')
        self.mock_isdir = self.mock_isdir_patcher.start()
        self._additional_patchers.append(self.mock_isdir_patcher)

        self.mock_subprocess_run_patcher = patch('subprocess.run')
        self.mock_subprocess_run = self.mock_subprocess_run_patcher.start()
        self._additional_patchers.append(self.mock_subprocess_run_patcher)

        # Create a mock CompletedProcess object
        mock_completed_process = MagicMock()
        mock_completed_process.returncode = 0
        mock_completed_process.stdout = "Already up to date."
        self.mock_subprocess_run.return_value = mock_completed_process

        # Create updater
        updater = PackageDatabaseUpdater(
            db_path=self.temp_db.name,
            xbstrap_path=self.xbstrap_path,
            upstream_sources=["nixos"]
        )

        # Test is_git_repository method
        # First, test when .git directory exists and git status succeeds
        self.mock_isdir.return_value = True
        self.assertTrue(updater.is_git_repository())
        self.mock_isdir.assert_called_once_with(os.path.join(self.xbstrap_path, '.git'))
        self.mock_subprocess_run.assert_called_once_with(
            ['git', '-C', self.xbstrap_path, 'status'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            text=True
        )

        # Reset mocks
        self.mock_isdir.reset_mock()
        self.mock_subprocess_run.reset_mock()

        # Test when .git directory doesn't exist
        self.mock_isdir.return_value = False
        self.assertFalse(updater.is_git_repository())
        self.mock_isdir.assert_called_once_with(os.path.join(self.xbstrap_path, '.git'))
        self.mock_subprocess_run.assert_not_called()

        # Reset mocks
        self.mock_isdir.reset_mock()
        self.mock_subprocess_run.reset_mock()

        # Test when git status fails
        self.mock_isdir.return_value = True
        mock_completed_process.returncode = 1
        self.assertFalse(updater.is_git_repository())
        self.mock_isdir.assert_called_once_with(os.path.join(self.xbstrap_path, '.git'))
        self.mock_subprocess_run.assert_called_once()

        # Reset mocks
        self.mock_isdir.reset_mock()
        self.mock_subprocess_run.reset_mock()
        mock_completed_process.returncode = 0

        # Test update_git_repository method
        # First, test successful update
        self.mock_isdir.return_value = True
        self.assertTrue(updater.update_git_repository())
        # Check that the last call to subprocess.run was with the expected arguments
        self.assertEqual(self.mock_subprocess_run.call_args_list[-1], call(
            ['git', '-C', self.xbstrap_path, 'pull', 'origin'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            text=True
        ))

        # Reset mocks
        self.mock_isdir.reset_mock()
        self.mock_subprocess_run.reset_mock()

        # Test update with specific remote and branch
        self.mock_isdir.return_value = True
        self.assertTrue(updater.update_git_repository(remote='upstream', branch='develop'))
        # Check that the last call to subprocess.run was with the expected arguments
        self.assertEqual(self.mock_subprocess_run.call_args_list[-1], call(
            ['git', '-C', self.xbstrap_path, 'pull', 'upstream', 'develop'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            text=True
        ))

        # Reset mocks
        self.mock_isdir.reset_mock()
        self.mock_subprocess_run.reset_mock()

        # Test update when not a git repository
        self.mock_isdir.return_value = False
        self.assertFalse(updater.update_git_repository())
        self.mock_isdir.assert_called_once_with(os.path.join(self.xbstrap_path, '.git'))
        self.mock_subprocess_run.assert_not_called()

        # Reset mocks
        self.mock_isdir.reset_mock()
        self.mock_subprocess_run.reset_mock()

        # Test update when git pull fails
        self.mock_isdir.return_value = True
        mock_completed_process.returncode = 1
        mock_completed_process.stderr = "error: could not pull"
        self.assertFalse(updater.update_git_repository())
        self.mock_isdir.assert_called_once_with(os.path.join(self.xbstrap_path, '.git'))
        self.mock_subprocess_run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
