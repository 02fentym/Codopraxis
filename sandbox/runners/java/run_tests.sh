#!/usr/bin/env bash
# Java runner: compile student + tests, run JUnit (fail-fast), write /workspace/report.xml
# Works with the Dockerfile that bundles junit-platform-console-standalone.jar
set -euo pipefail

# -------- Config (overridable via env) -----------------------------------------
: "${REPORT_PATH:=/workspace/report.xml}"
: "${BUILD_DIR:=/workspace/build}"
: "${REPORTS_DIR:=/workspace/reports}"
: "${JUNIT_JAR:=/opt/junit/junit-platform-console-standalone.jar}"

# -------- Helpers --------------------------------------------------------------
emit_single_suite_xml() {
  # $1=status label, $2=name, $3=message, $4=details
  local status="$1" name="$2" msg="$3" det="$4"
  mkdir -p "$(dirname "$REPORT_PATH")"
  case "$status" in
    compile_error|sandbox_error)
      # Synthesize a single-suite, single-test JUnit XML with an <error/>
      cat > "$REPORT_PATH" <<XML
<testsuites>
  <testsuite name="junit-console" tests="1" failures="0" errors="1" time="0">
    <testcase classname="runner" name="${name}">
      <error message="${msg}"><![CDATA[${det}]]></error>
    </testcase>
  </testsuite>
</testsuites>
XML
      ;;
    no_tests)
      cat > "$REPORT_PATH" <<XML
<testsuites>
  <testsuite name="junit-console" tests="0" failures="0" errors="0" time="0"/>
</testsuites>
XML
      ;;
    *)
      cat > "$REPORT_PATH" <<XML
<testsuites>
  <testsuite name="junit-console" tests="0" failures="0" errors="0" time="0"/>
</testsuites>
XML
      ;;
  esac
}

merge_reports_to_single() {
  # Wrap *all* <testsuite> blocks from $REPORTS_DIR/*.xml inside one <testsuites>
  mkdir -p "$(dirname "$REPORT_PATH")"
  : > "$REPORT_PATH"
  echo "<testsuites>" >> "$REPORT_PATH"
  shopt -s nullglob
  for f in "$REPORTS_DIR"/*.xml; do
    # copy each <testsuite>...</testsuite> block
    awk '/<testsuite/{on=1} on{print} /<\/testsuite>/{on=0}' "$f" >> "$REPORT_PATH" || true
  done
  echo "</testsuites>" >> "$REPORT_PATH"
}

has_failures_or_errors() {
  # Return 0 if *any* report shows failures>0 or errors>0
  shopt -s nullglob
  grep -Eq 'failures="([1-9][0-9]*)"|errors="([1-9][0-9]*)"' "$REPORTS_DIR"/*.xml 2>/dev/null
}

# -------- Prep -----------------------------------------------------------------
mkdir -p "$BUILD_DIR" "$REPORTS_DIR"
cd /workspace

# -------- Compile --------------------------------------------------------------
SOURCES_FILE="/tmp/java_sources.txt"
# Collect *all* .java sources from student and tests trees
find /workspace/student /workspace/tests -type f -name '*.java' > "$SOURCES_FILE" || true

if [[ ! -s "$SOURCES_FILE" ]]; then
  emit_single_suite_xml "no_tests" "no_sources" "No .java sources found" ""
  exit 0
fi

compile_log="$(mktemp)"
if ! javac -encoding UTF-8 -d "$BUILD_DIR" -cp "$JUNIT_JAR" @"$SOURCES_FILE" 2> "$compile_log"; then
  emit_single_suite_xml "compile_error" "compile" "javac failed" "$(cat "$compile_log")"
  exit 0
fi

# -------- Discover tests -------------------------------------------------------
# Prefer conventional JUnit 5 class names: *Test or *Tests (already compiled)
mapfile -t CLASSES < <(find "$BUILD_DIR" -type f \( -name '*Test.class' -o -name '*Tests.class' \) \
  | sed -E "s#^$BUILD_DIR/##; s#/#.#g; s#\.class\$##")

# If naming doesn't match conventions, fall back to scanning the whole classpath once.
if [[ ${#CLASSES[@]} -eq 0 ]]; then
  rm -rf "$REPORTS_DIR" && mkdir -p "$REPORTS_DIR"
  java -jar "$JUNIT_JAR" \
    --class-path="$BUILD_DIR" \
    --scan-classpath \
    --reports-dir="$REPORTS_DIR" \
    --disable-banner \
    --details=summary || true

  shopt -s nullglob
  if compgen -G "$REPORTS_DIR/*.xml" > /dev/null; then
    merge_reports_to_single
  else
    emit_single_suite_xml "no_tests" "no_tests" "No test classes discovered" ""
  fi
  exit 0
fi

# -------- Run per-class with bail-fast ----------------------------------------
rm -rf "$REPORTS_DIR" && mkdir -p "$REPORTS_DIR"

for cls in "${CLASSES[@]}"; do
  # Run this class only; do not fail the script on test failures
  java -jar "$JUNIT_JAR" \
    --class-path="$BUILD_DIR" \
    --select-class="$cls" \
    --reports-dir="$REPORTS_DIR" \
    --disable-banner \
    --details=summary || true

  # Stop immediately if any failure/error appears
  if has_failures_or_errors; then
    break
  fi
done

# -------- Merge to canonical report -------------------------------------------
merge_reports_to_single

# Always exit 0 so the host can parse /workspace/report.xml regardless of test results
exit 0
