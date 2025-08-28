#!/usr/bin/env bash
set -euo pipefail

# configurable limits via env (defaults are conservative)
: "${RUN_TIMEOUT:=5}"      # seconds; hard per-test limit enforced by pytest-timeout
: "${REPORT_PATH:=/workspace/report.xml}"

cd /workspace

# ensure report dir exists even in read-only rootfs world
mkdir -p "$(dirname "$REPORT_PATH")"

# We use --maxfail=1 to bail on the first failing test.
# We also keep it quiet-ish but preserve failures in JUnit.
pytest -q \
  --maxfail=1 \
  --disable-warnings \
  --timeout="$RUN_TIMEOUT" \
  --junitxml="$REPORT_PATH" \
  tests/ || true

# Always exit 0 so host can still read report.xml and decide status
# (non-zero would short-circuit host-side collection).
exit 0
