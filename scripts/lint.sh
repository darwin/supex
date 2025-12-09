#!/usr/bin/env bash
# Run all linters across the repository

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== Linting supex repository ==="

# Ruby linting - each directory uses its own bundled rubocop
echo ""
echo "--- Ruby: runtime ---"
cd "$PROJECT_ROOT/runtime"
bundle exec rubocop

echo ""
echo "--- Ruby: stdlib ---"
cd "$PROJECT_ROOT/stdlib"
bundle exec rubocop

echo ""
echo "--- Ruby: docgen ---"
cd "$PROJECT_ROOT/docgen"
bundle exec rubocop

echo ""
echo "--- Ruby: tests/snippets ---"
cd "$PROJECT_ROOT/tests/snippets"
bundle exec rubocop

# Python linting
echo ""
echo "--- Python: driver (ruff) ---"
cd "$PROJECT_ROOT/driver"
uv run ruff check src/ tests/

echo ""
echo "--- Python: driver (mypy) ---"
uv run mypy src/

echo ""
echo "=== All linters passed ==="
