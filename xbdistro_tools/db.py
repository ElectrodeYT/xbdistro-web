import sqlite3
from pathlib import Path
from typing import Optional, List, Tuple
from functools import cmp_to_key

import libversion


class PackageDatabase:
    def __init__(self, db_path: Path | str = "packages.db"):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self._connect()
        self._create_tables()

    def __enter__(self):
        return self

    def _connect(self):
        """Establish database connection."""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def _create_tables(self):
        """Create necessary database tables if they don't exist."""
        # Create sources table if it doesn't exist
        self.cursor.execute('''
                            CREATE TABLE IF NOT EXISTS sources
                            (
                                id   INTEGER PRIMARY KEY,
                                name TEXT UNIQUE NOT NULL
                            )
                            ''')
        self.cursor.execute('''
                            CREATE TABLE IF NOT EXISTS packages
                            (
                                name         TEXT PRIMARY KEY NOT NULL,
                                source_id    INTEGER          NOT NULL,
                                maintainer   TEXT,
                                homepage_url TEXT,
                                license      TEXT,
                                category     TEXT,
                                summary      TEXT,
                                description  TEXT,
                                FOREIGN KEY (source_id) REFERENCES sources (id)
                            )
                            ''')

        # Update versions table to reference sources instead of packages
        self.cursor.execute('''
                            CREATE TABLE IF NOT EXISTS versions
                            (
                                id        INTEGER PRIMARY KEY,
                                source_id INTEGER,
                                version   TEXT NOT NULL,
                                source    TEXT NOT NULL,
                                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                                FOREIGN KEY (source_id) REFERENCES sources (id),
                                UNIQUE (source_id, version, source)
                            )
                            ''')
        self.conn.commit()

    def compare_two_versions(self, version1: tuple[str, str, str], version2: tuple[str, str, str]) -> int:
        """Compare two version strings."""
        return libversion.version_compare2(version1[0], version2[0])

    def add_source_version(self, source_name: str, version: str, source: str) -> bool:
        """Add or update a source version.

        Args:
            source_name: Name of the source
            version: Version string
            source: Source of the version (e.g., 'local', 'nixos')

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.cursor.execute('INSERT OR IGNORE INTO sources (name) VALUES (?)', (source_name,))
            self.cursor.execute('SELECT id FROM sources WHERE name = ?', (source_name,))
            source_id = self.cursor.fetchone()[0]

            self.cursor.execute('''
                INSERT OR REPLACE INTO versions (source_id, version, source)
                VALUES (?, ?, ?)
            ''', (source_id, version, source))

            self.conn.commit()
            return True
        except sqlite3.Error:
            return False

    def get_source_versions(self, source_name: str) -> List[Tuple[str, str, str]]:
        """Get all versions for a source.

        Args:
            source_name: Name of the source

        Returns:
            List of tuples containing (version, source, timestamp)
        """
        self.cursor.execute('''
                            SELECT v.version, v.source, v.timestamp
                            FROM versions v
                                     JOIN sources s ON v.source_id = s.id
                            WHERE s.name = ?
                            ORDER BY v.timestamp DESC
                            ''', (source_name,))
        return self.cursor.fetchall()

    def get_latest_versions_each_source(self, source_name: str) -> List[Tuple[str, str]]:
        """Get the latest version for a source from each repository source.

        Args:
            source_name: Name of the source

        Returns:
            List of tuples containing (repository_source, version)
            Empty list if source not found
        """
        self.cursor.execute('''
                            WITH LatestVersions AS (SELECT v.source,
                                                           v.version,
                                                           ROW_NUMBER() OVER (PARTITION BY v.source ORDER BY v.timestamp DESC) as rn
                                                    FROM versions v
                                                             JOIN sources s ON v.source_id = s.id
                                                    WHERE s.name = ?)
                            SELECT source, version
                            FROM LatestVersions
                            WHERE rn = 1
                            ORDER BY source
                            ''', (source_name,))
        return self.cursor.fetchall()

    def get_latest_version(self, source_name: str) -> tuple[str, str] | None:
        """Get the latest version of a source across all repository sources.

        Args:
            source_name: Name of the source

        Returns:
            Tuple of (repository_source, version) for the latest version,
            or None if no versions found
        """
        # Get all latest versions from each repository source
        latest_versions = self.get_latest_versions_each_source(source_name)

        if not latest_versions:
            return None

        # Convert to tuples of (version, source, "") to match the compare function's expected format
        version_tuples = [(version, source, "") for source, version in latest_versions]

        # Sort versions using libversion comparison
        sorted_versions = sorted(version_tuples,
                                 key=cmp_to_key(self.compare_two_versions),
                                 reverse=True)

        # Return the newest version and its source
        return sorted_versions[0][1], sorted_versions[0][0]

    def get_all_source_names(self) -> List[str]:
        """Get a list of all source names in the database.

        Returns:
            List of source names sorted alphabetically
        """
        self.cursor.execute('SELECT name FROM sources ORDER BY name')
        return [row[0] for row in self.cursor.fetchall()]

    def get_latest_version_from_source(self, source_name: str, repository_source: str) -> Optional[Tuple[str, str]]:
        """Get the latest version for a source from a specific repository source.

        Args:
            source_name: Name of the source
            repository_source: Repository source to check (e.g., 'local', 'nixos')

        Returns:
            Tuple of (version, timestamp) or None if no version found for the source/repository source combination
        """
        self.cursor.execute('''
                            SELECT v.version, v.timestamp
                            FROM versions v
                                     JOIN sources s ON v.source_id = s.id
                            WHERE s.name = ?
                              AND v.source = ?
                            ORDER BY v.timestamp DESC
                            LIMIT 1
                            ''', (source_name, repository_source))

        result = self.cursor.fetchone()
        return result if result else None

    def get_version_timestamp(self, source_name: str, version: str, repository_source: str) -> str | None:
        """Get the timestamp for a specific version of a source.

        Args:
            source_name: Name of the source
            version: Version string to look up
            repository_source: Repository source to check (e.g., 'local', 'nixos')

        Returns:
            Timestamp string if found, None otherwise
        """
        try:
            self.cursor.execute('''
                                SELECT v.timestamp
                                FROM versions v
                                         JOIN sources s ON v.source_id = s.id
                                WHERE s.name = ?
                                  AND v.version = ?
                                  AND v.source = ?
                                ''', (source_name, version, repository_source))

            result = self.cursor.fetchone()
            return result[0] if result else None
        except sqlite3.Error:
            return None

    def add_package_metadata(self, source_name: str, name: str = None, maintainer: str = None, homepage_url: str = None,
                             license: str = None, category: str = None, summary: str = None,
                             description: str = None) -> bool:
        """Add or update package metadata.

        Args:
            source_name: Name of the source
            name: Name of the package (if different from source name)
            maintainer: Package maintainer
            homepage_url: Package homepage URL
            license: Package license
            category: Package category
            summary: Short summary of the package
            description: Longer description of the package

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get source_id
            self.cursor.execute('SELECT id FROM sources WHERE name = ?', (source_name,))
            result = self.cursor.fetchone()
            if not result:
                return False
            source_id = result[0]

            # If package name is not provided, use source name
            if name is None:
                name = source_name

            # Check if package metadata already exists
            self.cursor.execute('SELECT name FROM packages WHERE name = ?', (name,))
            result = self.cursor.fetchone()

            if result:
                # Update existing package metadata
                self.cursor.execute('''
                                    UPDATE packages
                                    SET source_id    = ?,
                                        maintainer   = ?,
                                        homepage_url = ?,
                                        license      = ?,
                                        category     = ?,
                                        summary      = ?,
                                        description  = ?
                                    WHERE name = ?
                                    ''', (source_id, maintainer, homepage_url, license, category, summary, description,
                                          name))
            else:
                # Insert new package metadata
                self.cursor.execute('''
                                    INSERT INTO packages (name, source_id, maintainer, homepage_url, license, category,
                                                          summary, description)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                    ''', (name, source_id, maintainer, homepage_url, license, category, summary,
                                          description))

            self.conn.commit()
            return True
        except sqlite3.Error:
            return False

    def get_package_metadata(self, source_name: str) -> Optional[dict]:
        """Get package metadata.

        Args:
            source_name: Name of the source

        Returns:
            dict: Package metadata or None if not found
        """
        try:
            self.cursor.execute('''
                                SELECT p.name,
                                       p.maintainer,
                                       p.homepage_url,
                                       p.license,
                                       p.category,
                                       p.summary,
                                       p.description
                                FROM packages p
                                         JOIN sources s ON p.source_id = s.id
                                WHERE s.name = ?
                                ''', (source_name,))

            result = self.cursor.fetchone()
            if not result:
                return None

            return {
                'name': result[0],
                'maintainer': result[1],
                'homepage_url': result[2],
                'license': result[3],
                'category': result[4],
                'summary': result[5],
                'description': result[6]
            }
        except sqlite3.Error:
            return None

    def get_source_packages(self, source_id: int) -> List[dict]:
        """Get all packages and their metadata associated with a source.

        Args:
            source_id: ID of the source to get packages for

        Returns:
            List of dictionaries containing package metadata, empty list if no packages found
        """
        try:
            self.cursor.execute('''
                                SELECT p.name,
                                       p.maintainer,
                                       p.homepage_url,
                                       p.license,
                                       p.category,
                                       p.summary,
                                       p.description
                                FROM packages p
                                WHERE p.source_id = ?
                                ''', (source_id,))

            results = self.cursor.fetchall()
            packages = []

            for result in results:
                packages.append({
                    'name': result[0],
                    'maintainer': result[1],
                    'homepage_url': result[2],
                    'license': result[3],
                    'category': result[4],
                    'summary': result[5],
                    'description': result[6]
                })

            return packages
        except sqlite3.Error:
            return []

    def get_packages_by_source_name(self, source_name: str) -> List[dict]:
        """Get all packages and their metadata associated with a source name.

        Args:
            source_name: Name of the source to get packages for

        Returns:
            List of dictionaries containing package metadata, empty list if no packages found
        """
        try:
            self.cursor.execute('SELECT id FROM sources WHERE name = ?', (source_name,))
            result = self.cursor.fetchone()
            if not result:
                return []

            return self.get_source_packages(result[0])
        except sqlite3.Error:
            return []

    def get_package_by_name(self, package_name: str) -> Optional[dict]:
        """Get package metadata by package name.

        Args:
            package_name: Name of the package

        Returns:
            dict: Package metadata or None if not found
        """
        try:
            self.cursor.execute('''
                                SELECT p.name,
                                       p.maintainer,
                                       p.homepage_url,
                                       p.license,
                                       p.category,
                                       p.summary,
                                       p.description,
                                       s.name
                                FROM packages p
                                         JOIN sources s ON p.source_id = s.id
                                WHERE p.name = ?
                                ''', (package_name,))

            result = self.cursor.fetchone()
            if not result:
                return None

            return {
                'name': result[0],
                'maintainer': result[1],
                'homepage_url': result[2],
                'license': result[3],
                'category': result[4],
                'summary': result[5],
                'description': result[6],
                'source_name': result[7]
            }
        except sqlite3.Error:
            return None

    def search_sources(self, search_term: str) -> List[dict]:
        """Search for sources by name.

        Args:
            search_term: Term to search for in source names

        Returns:
            List of dictionaries containing source information
        """
        try:
            # Use LIKE for partial matching with wildcards on both sides
            search_pattern = f"%{search_term}%"
            self.cursor.execute('''
                                SELECT s.name
                                FROM sources s
                                WHERE s.name LIKE ?
                                ORDER BY s.name
                                ''', (search_pattern,))

            results = self.cursor.fetchall()
            sources = []

            for result in results:
                source_name = result[0]
                sources.append({
                    'name': source_name,
                    'local_version': self.get_latest_version_from_source(source_name, 'local')[0],
                    'latest_version': self.get_latest_version(source_name)[1]
                })

            return sources
        except sqlite3.Error:
            return []

    def get_packages_missing_maintainer(self) -> List[dict]:
        """Get all packages that are missing a maintainer.

        Returns:
            List of dictionaries containing package information
        """
        try:
            self.cursor.execute('''
                                SELECT p.name, s.name as source_name
                                FROM packages p
                                         JOIN sources s ON p.source_id = s.id
                                WHERE p.maintainer IS NULL
                                   OR p.maintainer = ''
                                ORDER BY p.name
                                ''')

            results = self.cursor.fetchall()
            packages = []

            for result in results:
                packages.append({
                    'name': result[0],
                    'source_name': result[1]
                })

            return packages
        except sqlite3.Error:
            return []

    def get_all_package_names(self) -> List[str]:
        """Get a list of all package names in the database.

        Returns:
            List of package names sorted alphabetically
        """
        try:
            self.cursor.execute('SELECT name FROM packages ORDER BY name')
            return [row[0] for row in self.cursor.fetchall()]
        except sqlite3.Error:
            return []

    def delete_package(self, package_name: str) -> bool:
        """Delete a package from the database.

        Args:
            package_name: Name of the package to delete

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.cursor.execute('DELETE FROM packages WHERE name = ?', (package_name,))
            self.conn.commit()
            return True
        except sqlite3.Error:
            return False

    def delete_source(self, source_name: str) -> bool:
        """Delete a source and all its associated versions from the database.

        Args:
            source_name: Name of the source to delete

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get source ID
            self.cursor.execute('SELECT id FROM sources WHERE name = ?', (source_name,))
            result = self.cursor.fetchone()
            if not result:
                return False

            source_id = result[0]

            # Delete associated versions
            self.cursor.execute('DELETE FROM versions WHERE source_id = ?', (source_id,))

            # Delete the source
            self.cursor.execute('DELETE FROM sources WHERE id = ?', (source_id,))

            self.conn.commit()
            return True
        except sqlite3.Error:
            return False

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
