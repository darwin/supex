#!/bin/bash
# Generate AGENTS.override.md with resolved @references
# This is needed for AI agents that don't support @ syntax (e.g., Codex CLI)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

INPUT_FILE="$PROJECT_DIR/AGENTS.md"
OUTPUT_FILE="$PROJECT_DIR/AGENTS.override.md"

if [[ ! -f "$INPUT_FILE" ]]; then
    echo "Error: $INPUT_FILE not found"
    exit 1
fi

# Process AGENTS.md and expand @references
expand_references() {
    while IFS= read -r line || [[ -n "$line" ]]; do
        if [[ "$line" =~ ^@(.+)$ ]]; then
            ref_file="${BASH_REMATCH[1]}"
            ref_path="$PROJECT_DIR/$ref_file"
            if [[ -f "$ref_path" ]]; then
                cat "$ref_path"
            else
                echo "# Warning: Could not resolve @$ref_file"
                echo "$line"
            fi
        else
            echo "$line"
        fi
    done < "$INPUT_FILE"
}

expand_references > "$OUTPUT_FILE"

echo "Generated: $OUTPUT_FILE"
