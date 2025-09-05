import os
from typing import List, Tuple, Optional
from fastapi import FastAPI, HTTPException
from xbdistro_tools.db import PackageDatabase
from pathlib import Path
from functools import cmp_to_key
import libversion

app = FastAPI(title="Source Version API")

# Initialize database connection
db = PackageDatabase(Path(os.getenv('DB_PATH', 'packages.db')))


@app.get("/")
async def root():
    return {"message": "Source Version API"}


@app.get("/sources/all")
async def get_all_sources() -> List[str]:
    """
    Get all sources known to the database

    Returns:
        List of source names sorted alphabetically
    """
    return db.get_all_source_names()


@app.get("/sources/paged")
async def get_sources_paged(
        skip: int = 0,
        limit: int = 10
) -> dict:
    """
    Get sources known to the database with pagination

    Args:
        skip: Number of items to skip (offset)
        limit: Maximum number of items to return

    Returns:
        Dictionary containing:
        - items: List of source names sorted alphabetically
        - total: Total number of sources
        - skip: Current offset
        - limit: Current limit
    """
    all_sources = db.get_all_source_names()
    total = len(all_sources)
    sources = all_sources[skip:skip + limit]

    return {
        "items": sources,
        "total": total,
        "skip": skip,
        "limit": limit
    }

@app.get("/sources/{name}/versions")
async def get_versions(name: str) -> List[dict]:
    """
    Get all versions for a specific source

    Args:
        source_name: Name of the source to query
        package_name: Deprecated, use source_name instead

    Returns:
        List of dictionaries containing version information
    """
    versions = db.get_source_versions(name)
    return [
        {
            "version": version,
            "source": source,
            "timestamp": timestamp
        }
        for version, source, timestamp in versions
    ]


@app.get("/sources/{name}/latest")
async def get_latest_version(name: str) -> dict:
    """
    Get the latest version for a specific source

    Args:
        source_name: Name of the source to query
        package_name: Deprecated, use source_name instead

    Returns:
        Dictionary containing the latest version information
    """
    versions = db.get_source_versions(name)
    if not versions:
        return {"error": "Source not found"}

    print(versions)
    sorted_versions = sorted(versions, key=cmp_to_key(db.compare_two_versions), reverse=True)
    print(sorted_versions)
    version, source, timestamp = sorted_versions[0]
    return {
        "version": version,
        "source": source,
        "timestamp": timestamp
    }


@app.get("/sources/{name}/latest-by-source")
async def get_latest_versions_by_source(name: str) -> List[dict]:
    """
    Get the latest version for a source from each repository source

    Args:
        source_name: Name of the source to query
        package_name: Deprecated, use source_name instead

    Returns:
        List of dictionaries containing the latest version from each repository source
    """
    versions = db.get_latest_versions_each_source(name)
    return [
        {
            "source": source,
            "version": version
        }
        for source, version in versions
    ]


@app.get("/sources/{name}/source/{source}")
async def get_version_from_source(source: str, name) -> dict:
    """
    Get the latest version of a source from a specific repository source

    Args:
        source: Name of the repository source to query
        source_name: Name of the source to query
        package_name: Deprecated, use source_name instead

    Returns:
        Dictionary containing version information
    """
    result = db.get_latest_version_from_source(name, source)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No version found for source '{name}' from repository source '{source}'"
        )

    version, timestamp = result
    return {
        "source": name,
        "repository_source": source,
        "version": version,
        "timestamp": timestamp
    }


@app.get("/sources/{source_name}/packages")
async def get_source_packages(source_name: str) -> dict:
    """
    Get all packages and their metadata associated with a source

    Args:
        source_name: Name of the source to get packages for

    Returns:
        Dictionary containing source name and list of packages with their metadata
    """
    packages = db.get_packages_by_source_name(source_name)
    if not packages:
        return {
            "source": source_name,
            "packages": []
        }

    return {
        "source": source_name,
        "packages": packages
    }


@app.get("/packages/{package_name}")
async def get_package_metadata(package_name: str) -> dict:
    """
    Get package metadata by package name

    Args:
        package_name: Name of the package to get metadata for

    Returns:
        Dictionary containing package metadata
    """
    package = db.get_package_by_name(package_name)
    if not package:
        raise HTTPException(
            status_code=404,
            detail=f"Package '{package_name}' not found"
        )

    return package


@app.get("/sources/search")
async def search_sources(q: str) -> dict:
    """
    Search for sources by name

    Args:
        q: Search query string

    Returns:
        Dictionary containing search results
    """
    if not q or len(q.strip()) == 0:
        return {
            "query": q,
            "results": [],
            "count": 0
        }

    results = db.search_sources(q)
    return {
        "query": q,
        "results": results,
        "count": len(results)
    }


@app.get("/meta/missing-maintainer")
async def get_packages_missing_maintainer() -> dict:
    print('A')
    """
    Get all packages that are missing a maintainer

    Returns:
        Dictionary containing packages missing a maintainer
    """
    packages = db.get_packages_missing_maintainer()
    return {
        "packages": packages,
        "count": len(packages)
    }
