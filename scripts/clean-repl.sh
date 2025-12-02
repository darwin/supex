#!/usr/bin/env bash
# Clean up REPL session directories

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
REPL_DIR="$PROJECT_ROOT/.tmp/repl"

if [[ ! -d "$REPL_DIR" ]]; then
  echo "No REPL sessions to clean (directory does not exist)"
  exit 0
fi

count=$(find "$REPL_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')

if [[ "$count" -eq 0 ]]; then
  echo "No REPL sessions to clean"
  exit 0
fi

rm -rf "$REPL_DIR"/*
echo "Cleaned $count REPL session(s)"
