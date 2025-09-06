import os
from typing import List, Tuple, Optional
from fastapi import FastAPI, HTTPException
from xbdistro_tools.db import PackageDatabase, Version, compare_two_versions
from pathlib import Path
from functools import cmp_to_key
import libversion

app = FastAPI(title="Source Version API")

# Initialize database connection
db = PackageDatabase(Path(os.getenv('DB_PATH', 'packages.db')))


@app.get("/")
async def root():
    return {"message": "Source Version API"}

def _paginated_response(list, skip, limit, total):
    return {
        "items": list,
        "total": total,
        "skip": skip,
        "limit": limit
    }

def _do_pagination(list_to_page: list, skip: int, limit: int):
    return _paginated_response(list_to_page[skip:skip + limit], skip, limit)

def _get_source_info(name: str) -> dict:
    latest_version = db.get_latest_version(name)
    local_version = db.get_latest_version_from_source(name, 'local')
    return {
        'name': name,
        'local_version': local_version.version,
        'latest_version': latest_version.version,
        'is_outdated': compare_two_versions(local_version, latest_version) < 0
    }

def _version_list_to_dict(versions: List[Version]):
    return [
        {
            "version": version,
            "source": source,
            "timestamp": timestamp
        }
        # This works as the Version object is iterable.
        for version, source, timestamp in versions
    ]

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
    return _do_pagination(db.get_all_source_names(), skip, limit)

@app.get("/meta/sources/paged-info")
async def get_sources_info_paged(
    skip: int = 0,
    limit: int = 10
) -> dict:
    all_sources_names = db.get_all_source_names()
    sources_to_get = all_sources_names[skip:skip + limit]
    sources_info = list(map(_get_source_info, sources_to_get))
    return _paginated_response(sources_info, skip, limit, len(all_sources_names))

@app.get("/meta/missing-maintainer")
async def get_packages_missing_maintainer() -> dict:
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

@app.get("/meta/missing-maintainer/paged")
async def get_packages_missing_maintainer_paged(
        skip: int = 0,
        limit: int = 10
) -> dict:
    """
    Get paginated list of packages that are missing a maintainer

    Args:
        skip: Number of items to skip (offset)
        limit: Maximum number of items to return

    Returns:
        Dictionary containing:
        - items: List of packages missing a maintainer
        - total: Total number of packages
        - skip: Current offset
        - limit: Current limit
    """
    packages = db.get_packages_missing_maintainer()
    return _do_pagination(packages, skip, limit)

@app.get("/sources/{name}/info")
async def get_source_info(name: str) -> dict:
    return _get_source_info(name)

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
    return _version_list_to_dict(db.get_source_versions(name))


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
    return db.get_latest_version(name).to_dict()


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
    return _version_list_to_dict(db.get_latest_versions_each_source(name))

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

