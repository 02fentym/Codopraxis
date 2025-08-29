# JDK 21
FROM eclipse-temurin:21-jdk-jammy

# Non-root user
RUN useradd -m -u 1000 runner

# Basics
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash ca-certificates curl tini \
 && rm -rf /var/lib/apt/lists/*

# Fetch JUnit Platform Console (standalone fat jar)
ARG JUNIT_VERSION=1.10.2
RUN mkdir -p /opt/junit && \
    curl -fsSL "https://repo1.maven.org/maven2/org/junit/platform/junit-platform-console-standalone/${JUNIT_VERSION}/junit-platform-console-standalone-${JUNIT_VERSION}.jar" \
      -o /opt/junit/junit-platform-console-standalone.jar

# Runner script
COPY run_tests.sh /usr/local/bin/run_tests.sh
RUN chmod +x /usr/local/bin/run_tests.sh

# Work in /workspace (mounted)
WORKDIR /workspace

# Drop privileges
USER runner

ENTRYPOINT ["/usr/bin/tini","--"]
CMD ["/usr/local/bin/run_tests.sh"]
