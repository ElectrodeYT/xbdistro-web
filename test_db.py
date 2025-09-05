#!/usr/bin/env python3

import os
from xbdistro_tools.db import PackageDatabase

def main():
    # Remove the test database if it exists
    if os.path.exists("test_packages.db"):
        os.remove("test_packages.db")
    # Create a new database
    db = PackageDatabase("test_packages.db")

    # Add a source version
    print("Adding source version...")
    result = db.add_source_version("test-package", "1.0.0", "test-source")
    print(f"Result: {result}")

    # Add package metadata
    print("\nAdding package metadata...")
    result = db.add_package_metadata(
        source_name="test-package",
        name="Test Package Display Name",
        maintainer="Test Maintainer",
        homepage_url="https://example.com",
        license="MIT",
        category="Test",
        summary="A test package",
        description="This is a test package for testing the database schema changes."
    )
    print(f"Result: {result}")

    # Get package metadata
    print("\nGetting package metadata...")
    metadata = db.get_package_metadata("test-package")
    print("Package metadata:")
    for key, value in metadata.items():
        print(f"  {key}: {value}")

    # Get source versions
    print("\nGetting source versions...")
    versions = db.get_source_versions("test-package")
    print("Source versions:")
    for version in versions:
        print(f"  {version}")

    # Get latest versions from each source
    print("\nGetting latest versions from each source...")
    latest_versions = db.get_latest_versions_each_source("test-package")
    print("Latest versions:")
    for source, version in latest_versions:
        print(f"  {source}: {version}")

    # Get all source names
    print("\nGetting all source names...")
    source_names = db.get_all_source_names()
    print("Source names:")
    for name in source_names:
        print(f"  {name}")

    # Close the database
    db.close()
    print("\nTest completed successfully!")

if __name__ == "__main__":
    main()
