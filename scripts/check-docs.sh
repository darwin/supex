#!/usr/bin/env bash
# Lint markdown docs and check guide self-containment

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
GUIDE_DIR="$PROJECT_ROOT/docs/agents/guide"

errors=0

# --- markdownlint ---
echo "Running markdownlint..."
if ! (cd "$PROJECT_ROOT" && markdownlint .) 2>&1; then
  errors=1
fi

# --- Self-containment check for docs/agents/guide/ ---
echo ""
echo "Checking guide self-containment..."

# Find markdown link targets that escape the guide directory (contain ../)
# Ignore web links (http:// https://) and anchor-only links (#)
while IFS= read -r file; do
  while IFS= read -r line; do
    lineno="${line%%:*}"
    content="${line#*:}"
    # Extract markdown link targets [text](target)
    echo "$content" | grep -oE '\[[^]]*\]\([^)]+\)' | while IFS= read -r match; do
      target="${match##*(}"
      target="${target%)}"
      # Skip web links and anchors
      case "$target" in
        http://*|https://*|mailto:*|\#*) continue ;;
      esac
      # Flag links that escape the guide dir
      if [[ "$target" == *"../"* ]]; then
        echo "  $file:$lineno: link escapes guide: $match"
        # Signal error via a temp file (subshell can't set parent var)
        touch "$PROJECT_ROOT/.tmp/_selfcontain_err"
      fi
    done
  done < <(grep -n '\[.*\](.*\.\./.*)' "$file" 2>/dev/null || true)
done < <(find "$GUIDE_DIR" -name '*.md' -not -type l 2>/dev/null)

if [ -f "$PROJECT_ROOT/.tmp/_selfcontain_err" ]; then
  rm -f "$PROJECT_ROOT/.tmp/_selfcontain_err"
  errors=1
fi

# Repository-relative paths (docs/..., driver/..., runtime/...) do not resolve
# through the supex-guide/ symlink, even as plain text. Fenced code blocks are
# skipped: shell commands there are documented as run from a supex checkout.
while IFS= read -r hit; do
  echo "  $hit: repository-relative path in guide"
  errors=1
done < <(find "$GUIDE_DIR" -name '*.md' -not -type l -print0 2>/dev/null | xargs -0 awk '
  /^```/ { fence = !fence; next }
  !fence && /(^|[^A-Za-z0-9_.\/-])(docs|driver|runtime|vcad|scripts|devtools|tests)\/[A-Za-z0-9_.\/-]+/ \
    && !/\.tmp\// && !/supex-guide\// { print FILENAME ":" FNR ":" $0 }
')

if [ "$errors" -ne 0 ]; then
  echo ""
  echo "Docs check failed."
  exit 1
fi

echo ""
echo "Docs check passed."
