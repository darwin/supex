#!/usr/bin/env bash

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

echo "==> Cleaning previous documentation output..."
rm -rf generated-sketchup-docs-md/

echo "==> Checking for sketchup-api-stubs submodule..."
if [ ! -d "sketchup-api-stubs/lib" ]; then
    echo "ERROR: sketchup-api-stubs submodule not found!"
    echo "Please initialize it first:"
    echo "  git submodule update --init --recursive"
    exit 1
fi

echo "==> Generating Markdown documentation with YARD..."
bundle exec yardoc

echo "==> Cleaning up excluded namespaces..."
# Remove excluded namespace directories (belt-and-suspenders with YARD --exclude)
rm -rf generated-sketchup-docs-md/Layout/
rm -rf generated-sketchup-docs-md/UI/

echo "==> Building INDEX.md for Claude Code..."
bundle exec ruby scripts/build_index.rb

echo ""
echo "==> Documentation generated successfully!"
echo "    Output: generated-sketchup-docs-md/"
echo "    Index: generated-sketchup-docs-md/INDEX.md"
