import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List

logger = logging.getLogger('xbdistro_email')

class EmailNotifier:
    """Class to handle sending email notifications for package updates."""

    def __init__(
        self,
        smtp_server: str,
        smtp_port: int = 587,
        smtp_username: Optional[str] = None,
        smtp_password: Optional[str] = None,
        sender_email: str = "noreply@xbdistro-version-checker.org",
        fallback_email: str = "admin@xbdistro-version-checker.org",
        use_tls: bool = True
    ):
        """Initialize the email notifier with SMTP settings.

        Args:
            smtp_server: SMTP server address
            smtp_port: SMTP server port (default: 587 for TLS)
            smtp_username: SMTP username for authentication (optional)
            smtp_password: SMTP password for authentication (optional)
            sender_email: Email address to use as sender
            fallback_email: Email address to use for unmaintained packages
            use_tls: Whether to use TLS for SMTP connection (default: True)
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.sender_email = sender_email
        self.fallback_email = fallback_email
        self.use_tls = use_tls

    def send_update_notification(
        self,
        package_name: str,
        source_name: str,
        local_version: str,
        upstream_version: str,
        repository: str,
        maintainer_email: Optional[str] = None
    ) -> bool:
        """Send an email notification about an out-of-date package.

        Args:
            package_name: Name of the package
            source_name: Name of the source
            local_version: Current local version
            upstream_version: New upstream version
            repository: Repository where the new version was found
            maintainer_email: Email of the package maintainer (if None, uses fallback)

        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        # Determine recipient email
        recipient = maintainer_email if maintainer_email else self.fallback_email
        is_unmaintained = maintainer_email is None

        # Create email subject
        if is_unmaintained:
            subject = f"[UNMAINTAINED] Package update available: {package_name}"
        else:
            subject = f"Package update available: {package_name}"

        # Create email body
        body = self._create_email_body(
            package_name, 
            source_name, 
            local_version, 
            upstream_version, 
            repository, 
            is_unmaintained
        )

        # Send the email
        return self._send_email(recipient, subject, body)

    def _create_email_body(
        self,
        package_name: str,
        source_name: str,
        local_version: str,
        upstream_version: str,
        repository: str,
        is_unmaintained: bool
    ) -> str:
        """Create the email body for an update notification.

        Args:
            package_name: Name of the package
            source_name: Name of the source
            local_version: Current local version
            upstream_version: New upstream version
            repository: Repository where the new version was found
            is_unmaintained: Whether the package is unmaintained

        Returns:
            str: The email body
        """
        if is_unmaintained:
            greeting = "Hello Administrator,"
            unmaintained_note = (
                "This package is currently unmaintained. "
                "Please consider assigning a maintainer to it.\n\n"
            )
        else:
            greeting = "Hello Package Maintainer,"
            unmaintained_note = ""

        body = f"""
{greeting}

A new version of a package you maintain is available:

Package: {package_name}
Source: {source_name}
Current Version: {local_version}
New Version: {upstream_version}
Repository: {repository}

{unmaintained_note}Please update the package to the latest version.

Thank you,
XBDistro Version Checker
"""
        return body

    def _send_email(self, recipient: str, subject: str, body: str) -> bool:
        """Send an email using the configured SMTP settings.

        Args:
            recipient: Email address of the recipient
            subject: Email subject
            body: Email body

        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        try:
            # Create message
            message = MIMEMultipart()
            message["From"] = self.sender_email
            message["To"] = recipient
            message["Subject"] = subject
            message.attach(MIMEText(body, "plain"))

            # Connect to SMTP server
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                
                # Login if credentials are provided
                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                
                # Send email
                server.sendmail(self.sender_email, recipient, message.as_string())
            
            logger.info(f"Email notification sent to {recipient} about {subject}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False

def notify_package_update(
    source_name: str,
    version: str,
    repository: str,
    db,
    email_notifier: Optional[EmailNotifier] = None
) -> None:
    """Send email notification for package update.
    
    This function can be used as a callback for the PackageDatabaseUpdater.
    
    Args:
        source_name: Name of the source
        version: New upstream version
        repository: Repository where the new version was found
        db: Database instance to get package information
        email_notifier: EmailNotifier instance to send emails
    """
    if not email_notifier:
        logger.info(f"Email notifier not configured, skipping notification for {source_name}")
        return

    # Get local version
    local_version_result = db.get_latest_version_from_source(source_name, 'local')
    if not local_version_result:
        logger.warning(f"No local version found for {source_name}, skipping notification")
        return
    
    local_version = local_version_result[0]
    
    # Get packages associated with this source
    packages = db.get_packages_by_source_name(source_name)
    if not packages:
        # If no packages are associated, use the source name as the package name
        package_info = {
            'name': source_name,
            'maintainer': None
        }
        packages = [package_info]
    
    # Send notification for each package
    for package in packages:
        package_name = package.get('name', source_name)
        maintainer = package.get('maintainer')
        
        # Extract email from maintainer field if it exists
        maintainer_email = None
        if maintainer and '@' in maintainer:
            # Simple extraction - assumes maintainer field contains an email
            maintainer_email = maintainer.split('<')[-1].split('>')[0] if '<' in maintainer else maintainer
        
        # Send notification
        email_notifier.send_update_notification(
            package_name=package_name,
            source_name=source_name,
            local_version=local_version,
            upstream_version=version,
            repository=repository,
            maintainer_email=maintainer_email
        )