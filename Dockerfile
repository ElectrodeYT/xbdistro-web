FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV API_BASE_URL=http://localhost:8000
ENV DB_PATH=/app/packages.db
ENV XBSTRAP_PATH=/app/bootstrap-managarm
ENV GIT_REPO_URL=""
ENV GIT_BRANCH="main"
ENV SMTP_SERVER=""
ENV SMTP_PORT=587
ENV SMTP_USERNAME=""
ENV SMTP_PASSWORD=""
ENV SENDER_EMAIL="noreply@xbdistro-version-checker.org"
ENV FALLBACK_EMAIL="admin@xbdistro-version-checker.org"
ENV USE_TLS=true
ENV UPSTREAM_SOURCES=""

# Install system dependencies
# GCC is only needed to compile libversion
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    cron \
    supervisor \
    pkg-config \
    build-essential \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Clone and build libversion
RUN git clone https://github.com/repology/libversion.git /tmp/libversion \
    && cd /tmp/libversion \
    && mkdir build && cd build \
    && cmake .. -DCMAKE_BUILD_TYPE=Release \
    && make -j$(nproc) \
    && make install \
    && ldconfig \
    && rm -rf /tmp/libversion

# Set up working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Delete building prereqs now (We still need them to build the python libversion module)
RUN apt purge build-essential cmake -y && apt autoremove -y

# Copy the project files
COPY . .

# Install the project modules
RUN pip install --no-cache-dir .

# Create a cron job file
RUN echo "0 0 * * * /usr/local/bin/python /app/xbdistro_tools/cron.py --db-path $DB_PATH --xbstrap-path $XBSTRAP_PATH --update-git --git-remote origin --git-branch \$GIT_BRANCH \${UPSTREAM_SOURCES:+--upstream \$UPSTREAM_SOURCES} \${SMTP_SERVER:+--email-notifications --smtp-server \$SMTP_SERVER --smtp-port \$SMTP_PORT --smtp-username \$SMTP_USERNAME --smtp-password \$SMTP_PASSWORD --sender-email \$SENDER_EMAIL --fallback-email \$FALLBACK_EMAIL --use-tls \$USE_TLS} >> /var/log/cron.log 2>&1" > /etc/cron.d/xbdistro-cron
RUN chmod 0644 /etc/cron.d/xbdistro-cron
RUN crontab /etc/cron.d/xbdistro-cron

# Create supervisor configuration
RUN mkdir -p /var/log/supervisor
COPY <<EOF /etc/supervisor/conf.d/supervisord.conf
[supervisord]
nodaemon=true
user=root
logfile=/var/log/supervisor/supervisord.log
logfile_maxbytes=50MB
logfile_backups=10

[program:cron]
command=/usr/sbin/cron -f
autostart=true
autorestart=true
stdout_logfile=/var/log/supervisor/cron.log
stderr_logfile=/var/log/supervisor/cron.err

[program:backend]
command=uvicorn xbdistro_web_backend:app --host 0.0.0.0 --port 8000
directory=/app
autostart=true
autorestart=true
stdout_logfile=/var/log/supervisor/backend.log
stderr_logfile=/var/log/supervisor/backend.err

[program:frontend]
command=uvicorn xbdistro_web_frontend.main:app --host 0.0.0.0 --port 8001
directory=/app
autostart=true
autorestart=true
stdout_logfile=/var/log/supervisor/frontend.log
stderr_logfile=/var/log/supervisor/frontend.err
EOF

# Create entrypoint script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Clone git repository if GIT_REPO_URL is provided and directory does not exist\n\
if [ -n "$GIT_REPO_URL" ] && [ ! -d "$XBSTRAP_PATH" ]; then\n\
    echo "Cloning repository from $GIT_REPO_URL..."\n\
    git clone --branch "$GIT_BRANCH" "$GIT_REPO_URL" "$XBSTRAP_PATH"\n\
    echo "Repository cloned successfully."\n\
fi\n\
\n\
# Run initial cron job to populate database\n\
echo "Running initial database update..."\n\
python /app/xbdistro_tools/cron.py --db-path "$DB_PATH" --xbstrap-path "$XBSTRAP_PATH" --update-git --git-remote origin --git-branch "$GIT_BRANCH" ${UPSTREAM_SOURCES:+--upstream $UPSTREAM_SOURCES} ${SMTP_SERVER:+--email-notifications --smtp-server $SMTP_SERVER --smtp-port $SMTP_PORT --smtp-username $SMTP_USERNAME --smtp-password $SMTP_PASSWORD --sender-email $SENDER_EMAIL --fallback-email $FALLBACK_EMAIL --use-tls $USE_TLS}\n\
echo "Initial database update completed."\n\
\n\
# Start supervisord\n\
echo "Starting services..."\n\
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf\n\
' > /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose ports
EXPOSE 8000 8001

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]