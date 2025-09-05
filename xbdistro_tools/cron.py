import os
import logging
import argparse
import subprocess
from typing import Callable, Dict, List, Optional, Set, Tuple

import xbstrap.base
from xbdistro_tools.db import PackageDatabase
from xbdistro_tools.upstream_fetchers.nixos import NixOSVersionProvider
from xbdistro_tools.email_notifier import EmailNotifier, notify_package_update

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('xbdistro_cron')

# Type definitions for callbacks
PackageCallback = Callable[[str, Optional[str]], None]
VersionCallback = Callable[[str, str, str], None]


class PackageDatabaseUpdater:
    """Class to handle updating the package database and triggering callbacks for changes."""

    def __init__(
        self,
        db_path: str = "packages.db",
        xbstrap_path: str = "bootstrap-managarm",
        upstream_sources: List[str] = None,
        on_package_added: PackageCallback = None,
        on_package_removed: PackageCallback = None,
        on_local_version_updated: VersionCallback = None,
        on_upstream_version_updated: VersionCallback = None
    ):
        """Initialize the updater with the given parameters and callbacks.

        Args:
            db_path: Path to the SQLite database file
            xbstrap_path: Path to the xbstrap distribution
            upstream_sources: List of upstream sources to check (e.g., ['nixos'])
            on_package_added: Callback for when a new package is added
            on_package_removed: Callback for when a package is removed
            on_local_version_updated: Callback for when a local version is updated
            on_upstream_version_updated: Callback for when an upstream version is updated
        """
        self.db_path = db_path
        self.xbstrap_path = xbstrap_path
        self.upstream_sources = upstream_sources or []

        # Callbacks
        self.on_package_added = on_package_added
        self.on_package_removed = on_package_removed
        self.on_local_version_updated = on_local_version_updated
        self.on_upstream_version_updated = on_upstream_version_updated

        # Initialize database
        self.db = PackageDatabase(db_path)

        # Initialize xbstrap distribution
        self.distro = xbstrap.base.Config(
            path=xbstrap_path, 
            changed_source_root=xbstrap_path
        )

    def update_database(self):
        """Update the package database with the latest information."""
        logger.info("Starting database update")

        # Get existing sources and packages from the database
        existing_sources = set(self.db.get_all_source_names())
        existing_packages = set(self.db.get_all_package_names())

        # Track current sources and packages
        current_sources = set()
        current_packages = set()

        # Process all sources
        for source in self.distro.all_sources():
            source_name = source.name
            current_sources.add(source_name)

            # Check if this is a new source
            is_new_source = source_name not in existing_sources

            # Get local version
            try:
                local_version = source.version
            except xbstrap.base.RollingIdUnavailableError:
                local_version = 'RollingIDUnavailable'
            except Exception as e:
                logger.warning(f"Error getting version for source {source_name}: {e}")
                local_version = f"Error: {type(e).__name__}"

            # Check if local version has changed
            current_local_version = self._get_latest_version(source_name, 'local')
            if current_local_version != local_version:
                # Add the new version to the database
                self.db.add_source_version(source_name, local_version, 'local')

                # Call the callback if this is not a new source
                if not is_new_source and self.on_local_version_updated:
                    self.on_local_version_updated(source_name, local_version, 'local')
                    logger.info(f"Local version updated for {source_name}: {local_version}")

            # Check upstream versions
            for upstream in self.upstream_sources:
                if upstream == 'nixos':
                    provider = NixOSVersionProvider()
                    try:
                        upstream_version = provider.get_version(source_name)
                        if upstream_version:
                            # Check if upstream version has changed
                            current_upstream_version = self._get_latest_version(source_name, upstream)
                            if current_upstream_version != upstream_version:
                                # Add the new version to the database
                                self.db.add_source_version(source_name, upstream_version, upstream)

                                # Call the callback if this is not a new source
                                if not is_new_source and self.on_upstream_version_updated:
                                    self.on_upstream_version_updated(source_name, upstream_version, upstream)
                                    logger.info(f"Upstream version updated for {source_name}: {upstream_version} ({upstream})")
                    except Exception as e:
                        logger.warning(f"Error getting upstream version for {source_name} from {upstream}: {e}")

        # Process all packages
        for package in self.distro.all_pkgs():
            package_name = package.name
            source_name = package.source

            # Add to current packages set
            current_packages.add(package_name)

            # Get package metadata
            metadata = self._extract_package_metadata(package)

            # Check if this is a new package
            existing_package = self.db.get_package_by_name(package_name)
            if not existing_package and self.on_package_added:
                self.on_package_added(package_name, source_name)
                logger.info(f"New package added: {package_name} (source: {source_name})")

            # Add package metadata to the database
            self.db.add_package_metadata(
                source_name,
                package_name,
                maintainer=metadata.get('maintainer'),
                homepage_url=metadata.get('homepage_url'),
                license=metadata.get('license'),
                category=metadata.get('category'),
                summary=metadata.get('summary'),
                description=metadata.get('description')
            )

        # Check for removed packages
        removed_packages = existing_packages - current_packages
        for package_name in removed_packages:
            # Get package info before deleting
            package_info = self.db.get_package_by_name(package_name)
            if package_info and self.on_package_removed:
                source_name = package_info.get('source_name', 'unknown')
                self.on_package_removed(package_name, source_name)
                logger.info(f"Package removed: {package_name} (source: {source_name})")

            # Delete the package from the database
            if self.db.delete_package(package_name):
                logger.info(f"Deleted package from database: {package_name}")
            else:
                logger.warning(f"Failed to delete package from database: {package_name}")

        # Check for removed sources
        removed_sources = existing_sources - current_sources
        for source_name in removed_sources:
            # Get packages associated with this source
            packages = self.db.get_packages_by_source_name(source_name)
            for package in packages:
                if self.on_package_removed:
                    self.on_package_removed(package['name'], source_name)
                    logger.info(f"Package removed: {package['name']} (source: {source_name})")

                # Delete the package from the database
                if self.db.delete_package(package['name']):
                    logger.info(f"Deleted package from database: {package['name']}")
                else:
                    logger.warning(f"Failed to delete package from database: {package['name']}")

            # Delete the source from the database
            if self.db.delete_source(source_name):
                logger.info(f"Deleted source from database: {source_name}")
            else:
                logger.warning(f"Failed to delete source from database: {source_name}")

        logger.info("Database update completed")

    def _get_latest_version(self, source_name: str, repository_source: str) -> Optional[str]:
        """Get the latest version for a source from a specific repository source."""
        result = self.db.get_latest_version_from_source(source_name, repository_source)
        return result[0] if result else None

    def _extract_package_metadata(self, package: xbstrap.base.TargetPackage) -> Dict[str, str]:
        """Extract metadata from a package."""
        metadata = {}

        if hasattr(package, '_subpkg_yml') and package._subpkg_yml:
            package_yml = package._subpkg_yml
        else:
            package_yml = package._this_yml

        if 'metadata' in package_yml:
            metadata_yml = package_yml['metadata']
            if 'maintainer' in metadata_yml:
                metadata['maintainer'] = metadata_yml['maintainer']
            if 'website' in metadata_yml:
                metadata['homepage_url'] = metadata_yml['website']
            if 'spdx' in metadata_yml:
                metadata['license'] = metadata_yml['spdx']
            if 'categories' in metadata_yml:
                metadata['category'] = ', '.join(metadata_yml['categories'])
            if 'summary' in metadata_yml:
                metadata['summary'] = metadata_yml['summary']
            if 'description' in metadata_yml:
                metadata['description'] = metadata_yml['description']

        return metadata

    def is_git_repository(self) -> bool:
        """Check if the xbstrap_path is a git repository.

        Returns:
            bool: True if the xbstrap_path is a git repository, False otherwise
        """
        try:
            # Check if the .git directory exists
            git_dir = os.path.join(self.xbstrap_path, '.git')
            if not os.path.isdir(git_dir):
                return False

            # Run git status to verify it's a valid git repository
            result = subprocess.run(
                ['git', '-C', self.xbstrap_path, 'status'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                text=True
            )
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"Error checking if {self.xbstrap_path} is a git repository: {e}")
            return False

    def update_git_repository(self, remote: str = 'origin', branch: str = None) -> bool:
        """Update the git repository by pulling the latest changes.

        Args:
            remote: The remote to pull from (default: 'origin')
            branch: The branch to pull (default: current branch)

        Returns:
            bool: True if the update was successful, False otherwise
        """
        if not self.is_git_repository():
            logger.warning(f"{self.xbstrap_path} is not a git repository, skipping update")
            return False

        try:
            logger.info(f"Updating git repository at {self.xbstrap_path}")

            # Construct the git pull command
            cmd = ['git', '-C', self.xbstrap_path, 'pull', remote]
            if branch:
                cmd.append(branch)

            # Run the git pull command
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                text=True
            )

            if result.returncode == 0:
                logger.info(f"Git repository updated successfully: {result.stdout.strip()}")
                return True
            else:
                logger.error(f"Failed to update git repository: {result.stderr.strip()}")
                return False
        except Exception as e:
            logger.error(f"Error updating git repository: {e}")
            return False

    def close(self):
        """Close the database connection."""
        if self.db:
            self.db.close()


def default_package_added_callback(package_name: str, source_name: Optional[str]):
    """Default callback for when a package is added."""
    logger.info(f"Package added: {package_name} (source: {source_name}) (Callback)")


def default_package_removed_callback(package_name: str, source_name: Optional[str]):
    """Default callback for when a package is removed."""
    logger.info(f"Package removed: {package_name} (source: {source_name}) (Callback)")


def default_local_version_updated_callback(source_name: str, version: str, repository: str):
    """Default callback for when a local version is updated."""
    logger.info(f"Local version updated for {source_name}: {version} (Callback)")


def default_upstream_version_updated_callback(source_name: str, version: str, repository: str):
    """Default callback for when an upstream version is updated."""
    logger.info(f"Upstream version updated for {source_name}: {version} ({repository}) (Callback)")


def main():
    """Main entry point for the cron job."""
    parser = argparse.ArgumentParser(description='Update the package database (designed to be run as a cron job)')
    parser.add_argument('--db-path', default='packages.db', help='Path to the SQLite database file')
    parser.add_argument('--xbstrap-path', default='bootstrap-managarm', help='Path to the xbstrap distribution')
    parser.add_argument('--upstream', action='append', choices=['nixos'], help='Upstream sources to check')
    parser.add_argument('--log-file', help='Path to the log file')

    # Git update arguments
    git_group = parser.add_argument_group('Git Repository Updates')
    git_group.add_argument('--update-git', action='store_true', help='Update the xbstrap git repository before checking for package updates')
    git_group.add_argument('--git-remote', default='origin', help='Git remote to pull from (default: origin)')
    git_group.add_argument('--git-branch', help='Git branch to pull (default: current branch)')

    # Email notification arguments
    email_group = parser.add_argument_group('Email Notifications')
    email_group.add_argument('--email-notifications', action='store_true', help='Enable email notifications for out-of-date packages')
    email_group.add_argument('--smtp-server', help='SMTP server address for sending emails')
    email_group.add_argument('--smtp-port', type=int, default=587, help='SMTP server port (default: 587)')
    email_group.add_argument('--smtp-username', help='SMTP username for authentication')
    email_group.add_argument('--smtp-password', help='SMTP password for authentication')
    email_group.add_argument('--sender-email', default='noreply@xbdistro-version-checker.org', help='Email address to use as sender')
    email_group.add_argument('--fallback-email', default='admin@xbdistro-version-checker.org', help='Email address to use for unmaintained packages')
    email_group.add_argument('--use-tls', action='store_true', default=True, help='Use TLS for SMTP connection')

    args = parser.parse_args()

    # Configure file logging if specified
    if args.log_file:
        file_handler = logging.FileHandler(args.log_file)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)

    # Initialize email notifier if enabled
    email_notifier = None
    if args.email_notifications:
        if not args.smtp_server:
            logger.error("SMTP server is required for email notifications. Use --smtp-server")
            return

        email_notifier = EmailNotifier(
            smtp_server=args.smtp_server,
            smtp_port=args.smtp_port,
            smtp_username=args.smtp_username,
            smtp_password=args.smtp_password,
            sender_email=args.sender_email,
            fallback_email=args.fallback_email,
            use_tls=args.use_tls
        )
        logger.info(f"Email notifications enabled. Using SMTP server: {args.smtp_server}")

    # Create custom callback for upstream version updates if email notifications are enabled
    upstream_version_callback = default_upstream_version_updated_callback
    if email_notifier:
        def email_upstream_version_callback(source_name, version, repository):
            # Call the default callback first
            default_upstream_version_updated_callback(source_name, version, repository)
            # Then send email notification
            notify_package_update(source_name, version, repository, db=PackageDatabase(args.db_path), email_notifier=email_notifier)

        upstream_version_callback = email_upstream_version_callback

    # Create the updater with callbacks
    updater = PackageDatabaseUpdater(
        db_path=args.db_path,
        xbstrap_path=args.xbstrap_path,
        upstream_sources=args.upstream,
        on_package_added=default_package_added_callback,
        on_package_removed=default_package_removed_callback,
        on_local_version_updated=default_local_version_updated_callback,
        on_upstream_version_updated=upstream_version_callback
    )

    try:
        # Update git repository if requested
        if args.update_git:
            if updater.is_git_repository():
                logger.info(f"Updating git repository at {args.xbstrap_path}")
                if updater.update_git_repository(remote=args.git_remote, branch=args.git_branch):
                    logger.info("Git repository updated successfully")
                else:
                    logger.warning("Failed to update git repository")
            else:
                logger.warning(f"{args.xbstrap_path} is not a git repository, skipping update")

        # Update the database
        updater.update_database()
    finally:
        # Close the database connection
        updater.close()


if __name__ == "__main__":
    main()
