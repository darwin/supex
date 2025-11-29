#!/bin/bash

# Launch MCP server with logging
# This script runs the supex-mcp server using uv and logs execution details

set -e

# Script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MCP_DIR="$PROJECT_ROOT/src/driver"
LOG_DIR="$PROJECT_ROOT/.tmp"
LOG_FILE="$LOG_DIR/supex.log"

# Create log directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Start logging
log "=== MCP Server Launch ==="
log "Project root: $PROJECT_ROOT"
log "MCP directory: $MCP_DIR"
log "Log file: $LOG_FILE"

# Check if src/driver directory exists
if [ ! -d "$MCP_DIR" ]; then
    log "ERROR: MCP directory not found: $MCP_DIR"
    exit 1
fi

# Change to MCP directory
cd "$MCP_DIR"
log "Changed to directory: $(pwd)"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    log "ERROR: uv is not installed. Please install uv first."
    log "Visit: https://github.com/astral-sh/uv"
    exit 1
fi

log "Using uv: $(which uv)"
log "uv version: $(uv --version)"

# Check if dependencies are installed
if [ ! -d ".venv" ]; then
    log "Virtual environment not found. Running 'uv sync --dev' to install dependencies..."
    uv sync --dev 2>&1 | tee -a "$LOG_FILE"
    log "Dependencies installed successfully"
fi

# Run the MCP server
log "Starting MCP server..."
log "Command: uv run supex-mcp"
log "----------------------------------------"

# Run server and capture output
uv run supex-mcp 2>&1 | while IFS= read -r line; do
    echo "$line"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $line" >> "$LOG_FILE"
done

# This code runs when the server exits
EXIT_CODE=${PIPESTATUS[0]}
log "----------------------------------------"
log "MCP server exited with code: $EXIT_CODE"

exit $EXIT_CODE