#!/usr/bin/env bash
# test-fs-trace.sh - Run tests with filesystem write tracing
#
# Uses macOS fs_usage to monitor filesystem writes during test execution.
# Produces a report of all write paths, highlighting any writes outside
# the expected workspace (.tmp/).
#
# The script runs as normal user; only fs_usage is elevated via sudo.
# You will be prompted for your password once at the start.
#
# Usage:
#   ./scripts/test-fs-trace.sh [test args...]
#   ./scripts/test-fs-trace.sh --e2e
#   ./scripts/test-fs-trace.sh e2e

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

source "$SCRIPT_DIR/helpers/common.sh"

# ---------------------------------------------------------------------------
# Preflight — acquire sudo upfront (for fs_usage)
# ---------------------------------------------------------------------------

log_info "fs_usage requires root — requesting sudo..."
sudo -v || { log_error "sudo authentication failed"; exit 1; }

# ---------------------------------------------------------------------------
# Output paths
# ---------------------------------------------------------------------------

TRACE_DIR="$PROJECT_ROOT/.tmp/fs-trace"
# Fix ownership if left behind by a previous sudo run
if [[ -d "$TRACE_DIR" && ! -w "$TRACE_DIR" ]]; then
    sudo chown -R "$(id -u):$(id -g)" "$TRACE_DIR"
fi
mkdir -p "$TRACE_DIR"

TS=$(date +%Y%m%d-%H%M%S)
RAW="$TRACE_DIR/raw-$TS.log"
WRITES="$TRACE_DIR/writes-$TS.txt"
OUTSIDE="$TRACE_DIR/outside-$TS.txt"

# Pre-create files so they're owned by current user
touch "$RAW" "$WRITES" "$OUTSIDE"

# ---------------------------------------------------------------------------
# Allowed write roots (writes here are expected / harmless)
# ---------------------------------------------------------------------------

ALLOWED=(
    "$PROJECT_ROOT/.tmp/"
    "/private/var/folders/"
    "/private/tmp/"
    "/tmp/"
    "/dev/"
    "/Library/"
    "$HOME/Library/"
)

# Known noise — not our code, but harmless system/app writes.
# Reported in their own section, excluded from the "outside" alert.
KNOWN_NOISE=(
    "/Applications/SketchUp"
    "/private/var/root/"
    "/users/"
)

# ---------------------------------------------------------------------------
# Start tracing
# ---------------------------------------------------------------------------

# Track SketchUp (Ruby runtime writes) and python (test runner writes).
# -w  = wide output (full paths)
# -f filesys = filesystem events only
log_info "Starting fs_usage trace..."
log_info "Raw trace → $RAW"

# shellcheck disable=SC2024  # redirect is intentionally by current user, not sudo
sudo fs_usage -w -f filesys SketchUp python3 python3.14 2>/dev/null > "$RAW" &
FS_PID=$!

# Ensure cleanup on exit
cleanup() {
    if kill -0 "$FS_PID" 2>/dev/null; then
        sudo kill "$FS_PID" 2>/dev/null || true
        wait "$FS_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

sleep 0.5

# ---------------------------------------------------------------------------
# Run tests (as current user — no sudo wrapping)
# ---------------------------------------------------------------------------

echo ""
log_info "Running: ./test $*"
echo ""

TEST_RC=0
"$PROJECT_ROOT/test" "$@" || TEST_RC=$?

# ---------------------------------------------------------------------------
# Stop tracing
# ---------------------------------------------------------------------------

sleep 0.5
sudo kill "$FS_PID" 2>/dev/null || true
wait "$FS_PID" 2>/dev/null || true

# ---------------------------------------------------------------------------
# Extract write paths
# ---------------------------------------------------------------------------

# Write-related fs_usage operations:
#   WrData       — actual data write
#   mkdir        — directory creation
#   rename       — file rename/move
#   create       — file creation
#   link/symlink — link creation
#   unlink/rmdir — deletion
#   truncate     — truncation
#   open (W)     — open for writing (matched via W flag)

# Step 1: filter write-like operations
grep -iE 'WrData|mkdir|rename|create|truncat|\blink\b|unlink|rmdir' "$RAW" \
    | grep -oE ' /[^ ]+' \
    | sed 's/^ //' \
    | sort -u > "$WRITES" || true

# Also capture open-for-write (flag contains W)
grep -E 'open.*W' "$RAW" \
    | grep -oE ' /[^ ]+' \
    | sed 's/^ //' \
    | sort -u >> "$WRITES" || true

# Deduplicate
sort -u -o "$WRITES" "$WRITES"

# Normalize APFS firmlink paths: /System/Volumes/Data/Users/… → /Users/…
sed -i '' 's|^/System/Volumes/Data/|/|' "$WRITES"
sort -u -o "$WRITES" "$WRITES"

TOTAL=$(wc -l < "$WRITES" | tr -d ' ')

# ---------------------------------------------------------------------------
# Classify paths
# ---------------------------------------------------------------------------

# Build a grep pattern for allowed roots
ALLOWED_PATTERN=""
for root in "${ALLOWED[@]}"; do
    escaped=$(printf '%s' "$root" | sed 's/[.[\*^$()+?{|]/\\&/g')
    if [[ -z "$ALLOWED_PATTERN" ]]; then
        ALLOWED_PATTERN="^${escaped}"
    else
        ALLOWED_PATTERN="${ALLOWED_PATTERN}|^${escaped}"
    fi
done

# Build a grep pattern for known noise roots
NOISE_PATTERN=""
for root in "${KNOWN_NOISE[@]}"; do
    escaped=$(printf '%s' "$root" | sed 's/[.[\*^$()+?{|]/\\&/g')
    if [[ -z "$NOISE_PATTERN" ]]; then
        NOISE_PATTERN="^${escaped}"
    else
        NOISE_PATTERN="${NOISE_PATTERN}|^${escaped}"
    fi
done

# Find writes outside allowed roots
grep -vE "$ALLOWED_PATTERN" "$WRITES" > "$OUTSIDE" || true

# Split outside into known noise vs truly unexpected
NOISE_FILE="${OUTSIDE%.txt}-noise.txt"
grep -E "$NOISE_PATTERN" "$OUTSIDE" > "$NOISE_FILE" || true
NOISE_COUNT=$(wc -l < "$NOISE_FILE" | tr -d ' ')

# Remove known noise from outside list
grep -vE "$NOISE_PATTERN" "$OUTSIDE" > "${OUTSIDE}.tmp" || true
mv "${OUTSIDE}.tmp" "$OUTSIDE"
OUTSIDE_COUNT=$(wc -l < "$OUTSIDE" | tr -d ' ')

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Filesystem Write Trace Report${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "  Total unique write paths: ${CYAN}$TOTAL${NC}"
echo ""

# Writes under .tmp/
TMP_COUNT=$(grep -c "^$PROJECT_ROOT/.tmp/" "$WRITES" 2>/dev/null || echo 0)
echo -e "  ${GREEN}$PROJECT_ROOT/.tmp/${NC}  ($TMP_COUNT paths)"
if [[ $TMP_COUNT -gt 0 ]]; then
    grep "^$PROJECT_ROOT/.tmp/" "$WRITES" | sed 's/^/    /'
fi
echo ""

# System temp
SYS_COUNT=$(grep -cE "^/private/(var/folders|tmp)/" "$WRITES" 2>/dev/null || echo 0)
echo -e "  ${GRAY}System temp${NC}  ($SYS_COUNT paths)"
if [[ $SYS_COUNT -gt 0 && $SYS_COUNT -le 20 ]]; then
    grep -E "^/private/(var/folders|tmp)/" "$WRITES" | sed 's/^/    /'
elif [[ $SYS_COUNT -gt 20 ]]; then
    grep -E "^/private/(var/folders|tmp)/" "$WRITES" | head -20 | sed 's/^/    /'
    echo "    ... and $((SYS_COUNT - 20)) more"
fi
echo ""

# Known noise (system/app writes, not ours)
if [[ $NOISE_COUNT -gt 0 ]]; then
    echo -e "  ${GRAY}Known noise${NC}  ($NOISE_COUNT paths)"
    sed 's/^/    /' "$NOISE_FILE"
    echo ""
fi

# Writes outside allowed roots
if [[ $OUTSIDE_COUNT -eq 0 ]]; then
    echo -e "  ${GREEN}No writes outside allowed roots${NC}"
else
    echo -e "  ${RED}WRITES OUTSIDE ALLOWED ROOTS ($OUTSIDE_COUNT):${NC}"
    sed 's/^/    /' "$OUTSIDE"
fi

echo ""
echo -e "${BLUE}----------------------------------------${NC}"
echo -e "  Raw trace:    $RAW"
echo -e "  Write paths:  $WRITES"
if [[ $OUTSIDE_COUNT -gt 0 ]]; then
    echo -e "  ${RED}Outside:      $OUTSIDE${NC}"
fi
echo -e "  Test exit:    $TEST_RC"
echo -e "${BLUE}========================================${NC}"

exit "$TEST_RC"
