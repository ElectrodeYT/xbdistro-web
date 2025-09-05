# XBDistro Web Frontend

A web front-end for the XBDistro Version Explorer API. This application provides a user-friendly interface to browse packages, view their latest versions, and explore version history.

## Features

- Paginated view of all packages
- Detailed view of package information
- Latest version display
- Version history
- Latest versions by source

## Requirements

- Python 3.7+
- FastAPI
- Jinja2
- httpx
- uvicorn

## Installation

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Running the API Backend

First, you need to run the FastAPI backend:

```bash
cd /path/to/xbdistro-version-checker
python -m uvicorn xbdistro_version_explorer_fastapi:app --host 0.0.0.0 --port 8000
```

### Running the Web Frontend

Then, in a separate terminal, run the web frontend:

```bash
cd /path/to/xbdistro-version-checker
python -m xbdistro_web_frontend.main
```

The web frontend will be available at http://localhost:8001

## Configuration

By default, the web frontend connects to the API at http://localhost:8000. If your API is running on a different host or port, you can modify the `API_BASE_URL` in `xbdistro_web_frontend/__init__.py`.

## Development

### Project Structure

- `__init__.py`: Main application file with FastAPI routes
- `main.py`: Entry point for running the application
- `templates/`: Jinja2 templates for rendering HTML
  - `base.html`: Base template with common layout
  - `index.html`: Home page with package list
  - `package_detail.html`: Package detail page

### Adding New Features

To add new features:

1. Add new routes in `__init__.py`
2. Create new templates in the `templates/` directory
3. Update existing templates as needed