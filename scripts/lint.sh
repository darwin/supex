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
echo "--- Ruby: mock ---"
cd "$PROJECT_ROOT/mock"
bundle exec rubocop

echo ""
echo "--- Ruby: docgen ---"
cd "$PROJECT_ROOT/devtools/docgen"
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
echo "--- Python: radar (ruff) ---"
cd "$PROJECT_ROOT/devtools/radar"
uv run ruff check src/ tests/

echo ""
echo "--- Python: radar (mypy) ---"
uv run mypy src/

echo ""
echo "--- Python: tests (ruff) ---"
cd "$PROJECT_ROOT/tests"
uv run ruff check .

# Rust linting - sidecar and viewer backend
echo ""
echo "--- Rust: sidecar (fmt + clippy) ---"
cd "$PROJECT_ROOT/vcad/sidecar"
cargo fmt --check
cargo clippy --all-targets --quiet -- -D warnings

echo ""
echo "--- Rust: viewer backend (fmt + clippy) ---"
cd "$PROJECT_ROOT/vcad/viewer/src-tauri"
cargo fmt --check
cargo clippy --all-targets --quiet -- -D warnings

# TypeScript viewer frontend (tsc + eslint)
echo ""
echo "--- TypeScript: viewer (tsc + eslint) ---"
cd "$PROJECT_ROOT/vcad/viewer"
npm run --silent lint

# Markdown docs
echo ""
echo "--- Markdown: docs ---"
bash "$SCRIPT_DIR/check-docs.sh"

echo ""
echo "=== All linters passed ==="
