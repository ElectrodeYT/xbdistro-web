# XBDistro Version Checker

A tool for checking and comparing versions of packages in an xbstrap distribution.

## Features

- Check versions of sources in an xbstrap distribution
- Compare local versions with upstream sources (currently only NixOS)
- Export version information to a SQLite database
- Web frontend for browsing package information
- Cron job for automatically updating the package database and cleaning up removed packages
- Git repository updates for keeping the xbstrap distribution up-to-date

## Installation

```bash
pip install -e .
```

## Usage

### Command-line Tool

```bash
# Check all sources and print version information
xbdistro_tools --path /path/to/xbstrap/distribution --all-sources --print-version

# Check specific sources
xbdistro_tools --sources source1,source2 --print-version

# Check all packages
xbdistro_tools --all-packages --print-version

# Compare with upstream (NixOS)
xbdistro_tools --all-sources --upstream nixos --print-version

# Export to database
xbdistro_tools --all-sources --all-packages --upstream nixos --export-db packages.db
```

### Cron Job

The package includes a command-line tool designed to be run as a cron job to automatically update the package database, clean up removed packages, and send email notifications when packages go out of date.

```bash
# Basic usage
xbdistro_cron --db-path packages.db --xbstrap-path /path/to/xbstrap/distribution

# Check upstream versions
xbdistro_cron --db-path packages.db --upstream nixos

# Log to a file
xbdistro_cron --db-path packages.db --log-file /path/to/logfile.log

# Enable email notifications
xbdistro_cron --db-path packages.db --upstream nixos --email-notifications --smtp-server smtp.example.com --smtp-username user --smtp-password pass --fallback-email admin@example.com

# Update git repository before checking for package updates
xbdistro_cron --db-path packages.db --update-git --xbstrap-path /path/to/xbstrap/distribution

# Update git repository with specific remote and branch
xbdistro_cron --db-path packages.db --update-git --git-remote upstream --git-branch develop
```

#### Git Repository Updates

The cron job can update the git repository containing the xbstrap distribution before checking for package updates. This ensures that the package database is always up-to-date with the latest changes in the repository.

Git update options:
- `--update-git`: Enable git repository updates
- `--git-remote`: Git remote to pull from (default: origin)
- `--git-branch`: Git branch to pull (default: current branch)

The system checks if the xbstrap path is a git repository by verifying the existence of the .git directory and running `git status`. If it is a git repository, it pulls the latest changes from the specified remote and branch.

#### Email Notifications

The cron job can send email notifications to package maintainers when their packages go out of date. For unmaintained packages, notifications are sent to a fallback email address.

Email notification options:
- `--email-notifications`: Enable email notifications
- `--smtp-server`: SMTP server address (required for email notifications)
- `--smtp-port`: SMTP server port (default: 587)
- `--smtp-username`: SMTP username for authentication
- `--smtp-password`: SMTP password for authentication
- `--sender-email`: Email address to use as sender (default: noreply@xbdistro-version-checker.org)
- `--fallback-email`: Email address to use for unmaintained packages (default: admin@xbdistro-version-checker.org)
- `--use-tls`: Use TLS for SMTP connection (default: enabled)

The system extracts maintainer email addresses from the package metadata. If a package doesn't have a maintainer or the maintainer field doesn't contain an email address, notifications are sent to the fallback email address.

#### Setting up as a Cron Job

To set up the tool as a cron job, add an entry to your crontab:

```bash
# Edit your crontab
crontab -e

# Add a line to run the job daily at 2 AM
0 2 * * * /path/to/xbdistro_cron --db-path /path/to/packages.db --xbstrap-path /path/to/xbstrap/distribution --upstream nixos --log-file /path/to/logfile.log --update-git
```

## Callbacks

The cron job module includes callbacks for various package-related events:

- When new packages are added
- When packages are removed
- When local versions are updated
- When upstream versions are updated

By default, these callbacks log the events. You can customize them by extending the `PackageDatabaseUpdater` class and providing your own callback functions.

### Automatic Cleanup

The cron job automatically detects and removes packages and sources that no longer exist in the xbstrap distribution. This helps keep the database clean and up-to-date. When a package or source is removed from the distribution, the cron job will:

1. Detect that the package or source is missing
2. Call the appropriate callback function
3. Delete the package or source from the database

This ensures that your database only contains information about packages and sources that actually exist in the distribution.

### Custom Callback Examples

#### Basic Custom Callback

```python
from xbdistro_tools.cron import PackageDatabaseUpdater

def my_package_added_callback(package_name, source_name):
    # Custom logic for when a package is added
    print(f"New package added: {package_name} (source: {source_name})")
    # Send an email, Slack notification, etc.

updater = PackageDatabaseUpdater(
    db_path="packages.db",
    xbstrap_path="/path/to/xbstrap/distribution",
    upstream_sources=["nixos"],
    on_package_added=my_package_added_callback
)

updater.update_database()
```

#### Email Notification Callback

```python
from xbdistro_tools.cron import PackageDatabaseUpdater
from xbdistro_tools.db import PackageDatabase
from xbdistro_tools.email_notifier import EmailNotifier, notify_package_update

# Create an email notifier
email_notifier = EmailNotifier(
    smtp_server="smtp.example.com",
    smtp_port=587,
    smtp_username="user",
    smtp_password="pass",
    fallback_email="admin@example.com"
)

# Create a database instance
db = PackageDatabase("packages.db")

# Define a custom callback that sends email notifications
def upstream_version_updated_callback(source_name, version, repository):
    print(f"Upstream version updated for {source_name}: {version} ({repository})")
    # Send email notification
    notify_package_update(source_name, version, repository, db, email_notifier)

# Create the updater with the custom callback
updater = PackageDatabaseUpdater(
    db_path="packages.db",
    xbstrap_path="/path/to/xbstrap/distribution",
    upstream_sources=["nixos"],
    on_upstream_version_updated=upstream_version_updated_callback
)

updater.update_database()
```

## Docker

The project includes a Dockerfile for easy deployment. The Docker image runs the backend API server, frontend web interface, and daily cron job for updating package information.

### Building the Docker Image

```bash
docker build -t xbdistro-version-checker .
```

### Running the Container

Basic usage:

```bash
docker run -d -p 8000:8000 -p 8001:8001 --name xbdistro-checker xbdistro-version-checker
```

With a Git repository:

```bash
docker run -d -p 8000:8000 -p 8001:8001 \
  -e GIT_REPO_URL=https://github.com/yourusername/bootstrap-managarm.git \
  -e GIT_BRANCH=main \
  --name xbdistro-checker xbdistro-version-checker
```

With email notifications:

```bash
docker run -d -p 8000:8000 -p 8001:8001 \
  -e SMTP_SERVER=smtp.example.com \
  -e SMTP_PORT=587 \
  -e SMTP_USERNAME=user \
  -e SMTP_PASSWORD=password \
  -e SENDER_EMAIL=noreply@example.com \
  -e FALLBACK_EMAIL=admin@example.com \
  --name xbdistro-checker xbdistro-version-checker
```

### Environment Variables

#### Basic Configuration
- `API_BASE_URL`: URL of the backend API (default: http://localhost:8000)
- `DB_PATH`: Path to the SQLite database file (default: /app/packages.db)
- `XBSTRAP_PATH`: Path to the xbstrap distribution (default: /app/bootstrap-managarm)

#### Git Repository Configuration
- `GIT_REPO_URL`: URL of the Git repository to clone (default: empty)
- `GIT_BRANCH`: Branch to clone (default: main)

#### Email Notification Configuration
- `SMTP_SERVER`: SMTP server address for sending emails (default: empty)
- `SMTP_PORT`: SMTP server port (default: 587)
- `SMTP_USERNAME`: SMTP username for authentication (default: empty)
- `SMTP_PASSWORD`: SMTP password for authentication (default: empty)
- `SENDER_EMAIL`: Email address to use as sender (default: noreply@xbdistro-version-checker.org)
- `FALLBACK_EMAIL`: Email address to use for unmaintained packages (default: admin@xbdistro-version-checker.org)
- `USE_TLS`: Use TLS for SMTP connection (default: true)

#### Upstream Sources Configuration
- `UPSTREAM_SOURCES`: Upstream sources to check (e.g., nixos) (default: empty)

### Accessing the Application

- Backend API: http://localhost:8000
- Frontend Web Interface: http://localhost:8001

### Volumes

You may want to mount volumes for persistent data:

```bash
docker run -d -p 8000:8000 -p 8001:8001 \
  -v /path/to/data:/app/packages.db \
  -v /path/to/bootstrap-managarm:/app/bootstrap-managarm \
  --name xbdistro-checker xbdistro-version-checker
```

### Logs

Logs are available in the container at:
- `/var/log/supervisor/` - Supervisor logs
- `/var/log/cron.log` - Cron job logs

You can view them using:

```bash
docker exec -it xbdistro-checker cat /var/log/supervisor/backend.log
docker exec -it xbdistro-checker cat /var/log/supervisor/frontend.log
docker exec -it xbdistro-checker cat /var/log/cron.log
```

## Development

### Running Tests

```bash
python -m unittest test_db.py
python -m unittest test_cron.py
python -m unittest test_email_notifier.py
```

## License

[License information]
