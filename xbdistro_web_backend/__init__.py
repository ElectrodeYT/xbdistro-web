import os
from typing import List, Tuple, Optional
from fastapi import FastAPI, HTTPException
from starlette.responses import RedirectResponse

from xbdistro_tools.db import PackageDatabase, Version, compare_two_versions
from pathlib import Path
from functools import cmp_to_key
import libversion

app = FastAPI(title="Source Version API")

# Initialize database connection
db = PackageDatabase(Path(os.getenv('DB_PATH', 'packages.db')))


@app.get("/")
async def root():
    return RedirectResponse('docs')

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
        'local_version': local_version,
        'latest_version': latest_version,
        'is_outdated': compare_two_versions(local_version, latest_version) < 0
    }

def _version_list_to_dict(versions: List[Version]) -> List[dict]:
    return [
        {
            "version": version,
            "source": source,
            "timestamp": timestamp
        }
        # This works as the Version object is iterable.
        for version, source, timestamp in versions
    ]


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

@app.get("/sources/{name}/extended-info")
async def get_source_extended_info(name: str) -> dict:
    ret = {
        'info': _get_source_info(name),
        'all_versions': _version_list_to_dict(db.get_source_versions(name)),
        'latest_versions': _version_list_to_dict(db.get_latest_versions_each_source(name)),
        'packages': db.get_packages_by_source_name(name)
    }
    return ret


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

