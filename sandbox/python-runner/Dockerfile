# Small, recent Python
FROM python:3.11-slim

# Create a non-root user
RUN useradd -m -u 1000 runner

# Install minimal build deps for potential native wheels (kept lean)
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash ca-certificates tini \
 && rm -rf /var/lib/apt/lists/*

# Copy runner assets
WORKDIR /opt/runner
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY run_tests.sh /usr/local/bin/run_tests.sh
RUN chmod +x /usr/local/bin/run_tests.sh

# Work inside /workspace (mounted from host at runtime)
WORKDIR /workspace

# Drop privileges
USER runner

# init + script
ENTRYPOINT ["/usr/bin/tini","--"]
CMD ["/usr/local/bin/run_tests.sh"]
