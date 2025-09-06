from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pathlib import Path
import httpx
import os
import libversion

# Create FastAPI app
app = FastAPI(title="XBDistro Source Explorer")

# Set up templates and static files
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
os.makedirs(BASE_DIR / "static", exist_ok=True)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# API base URL
API_BASE_URL = "http://localhost:8000"  # Assuming the FastAPI runs on this URL

# Helper function to get API client
async def get_api_client():
    async with httpx.AsyncClient(base_url=API_BASE_URL) as client:
        yield client

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, page: int = 1, limit: int = 10, client: httpx.AsyncClient = Depends(get_api_client)):
    """
    Home page showing a paginated list of sources
    """
    # Calculate skip value for pagination
    skip = (page - 1) * limit

    # Get paginated sources from API
    response = await client.get(f"/meta/sources/paged-info?skip={skip}&limit={limit}")
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch sources")

    data = response.json()
    sources_with_versions = data["items"]
    total = data["total"]

    # Calculate pagination values
    total_pages = (total + limit - 1) // limit

    return templates.TemplateResponse(
        "index.html.j2",
        {
            "request": request,
            "sources": sources_with_versions,
            "page": page,
            "total_pages": total_pages,
            "limit": limit,
            "total": total
        }
    )

@app.get("/source/{name}", response_class=HTMLResponse)
async def source_detail(
    request: Request, 
    name: str = None,
    client: httpx.AsyncClient = Depends(get_api_client)
):
    """
    Source detail page showing version information and associated packages
    """

    # Get latest version
    latest_response = await client.get(f"/sources/{name}/latest")
    if latest_response.status_code != 200:
        raise HTTPException(status_code=latest_response.status_code, detail="Failed to fetch source details")

    latest_version = latest_response.json()

    # Get all versions
    versions_response = await client.get(f"/sources/{name}/versions")
    if versions_response.status_code != 200:
        raise HTTPException(status_code=versions_response.status_code, detail="Failed to fetch source versions")

    versions = versions_response.json()

    # Get latest versions by source
    sources_response = await client.get(f"/sources/{name}/latest-by-source")
    if sources_response.status_code != 200:
        raise HTTPException(status_code=sources_response.status_code, detail="Failed to fetch source repository sources")

    sources = sources_response.json()

    # Add is_outdated flag to each source
    if "error" not in latest_version:
        latest_ver = latest_version["version"]
        for source in sources:
            # Compare source version with latest version
            if source["version"] and latest_ver:
                comparison = libversion.version_compare(source["version"], latest_ver)
                source["is_outdated"] = comparison < 0

    # Get packages associated with this source
    packages_response = await client.get(f"/sources/{name}/packages")
    if packages_response.status_code != 200:
        packages = {"source": name, "packages": []}
    else:
        packages = packages_response.json()

    return templates.TemplateResponse(
        "source_detail.html.j2",
        {
            "request": request,
            "source_name": name,
            "latest_version": latest_version,
            "versions": versions,
            "sources": sources,
            "packages": packages["packages"]
        }
    )

@app.get("/search", response_class=HTMLResponse)
async def search(
    request: Request,
    q: str = "",
    client: httpx.AsyncClient = Depends(get_api_client)
):
    """
    Search for sources by name
    """
    if not q or len(q.strip()) == 0:
        return templates.TemplateResponse(
            "search_results.html.j2",
            {
                "request": request,
                "query": q,
                "results": [],
                "count": 0
            }
        )

    # Call the search API endpoint
    response = await client.get(f"/sources/search?q={q}")
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to search sources")

    data = response.json()

    return templates.TemplateResponse(
        "search_results.html.j2",
        {
            "request": request,
            "query": data["query"],
            "results": data["results"],
            "count": data["count"]
        }
    )

@app.get("/missing-maintainers", response_class=HTMLResponse)
async def missing_maintainers(
    request: Request,
    client: httpx.AsyncClient = Depends(get_api_client)
):
    """
    Display packages missing maintainers
    """
    # Call the missing maintainers API endpoint
    response = await client.get("/meta/missing-maintainer")
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch packages missing maintainers")

    data = response.json()

    return templates.TemplateResponse(
        "missing_maintainers.html.j2",
        {
            "request": request,
            "packages": data["packages"],
            "count": data["count"]
        }
    )

@app.get("/packages/{package_name}", response_class=HTMLResponse)
async def package_detail(
    request: Request,
    package_name: str,
    client: httpx.AsyncClient = Depends(get_api_client)
):
    """
    Package detail page showing package metadata
    """
    # Call the package metadata API endpoint
    response = await client.get(f"/packages/{package_name}")
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail="Failed to fetch package details")

    package = response.json()

    return templates.TemplateResponse(
        "package_detail.html.j2",
        {
            "request": request,
            "package": package
        }
    )
