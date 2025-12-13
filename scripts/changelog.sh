#!/usr/bin/env bash

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROMPT_FILE="$SCRIPT_DIR/changelog-prompt.md"
PROMPT_OUTPUT="$PROJECT_ROOT/.tmp/last-changelog-prompt.md"

# Source common utilities
source "$SCRIPT_DIR/helpers/common.sh"

show_help() {
    cat << EOF
Usage: $(basename "$0") [TAG]

Prepare a changelog prompt for a GitHub Release page.

ARGUMENTS:
    TAG         Version tag to generate changelog for (default: latest tag)

EXAMPLES:
    $(basename "$0")            # Prompt for latest release
    $(basename "$0") v0.2.0     # Prompt for specific version

OUTPUT:
    Saves prompt to .tmp/last-changelog-prompt.md
    Run the prompt in your preferred AI agent (Claude Code, Cursor, etc.)

EOF
}

# Get commit range for a tag
get_commit_range() {
    local target_tag="$1"
    local all_tags
    local previous_tag=""

    # Get all version tags sorted by version (newest first)
    all_tags=$(git tag -l 'v*' --sort=-v:refname)

    # Find the tag before target_tag
    local found_target=false
    while IFS= read -r tag; do
        if [[ "$found_target" == true ]]; then
            previous_tag="$tag"
            break
        fi
        if [[ "$tag" == "$target_tag" ]]; then
            found_target=true
        fi
    done <<< "$all_tags"

    # If no previous tag, use first commit
    if [[ -z "$previous_tag" ]]; then
        local first_commit
        first_commit=$(git rev-list --max-parents=0 HEAD)
        echo "${first_commit}..${target_tag}"
    else
        echo "${previous_tag}..${target_tag}"
    fi
}

# Build the prompt for Claude
build_prompt() {
    local target_tag="$1"
    local range="$2"

    if [[ ! -f "$PROMPT_FILE" ]]; then
        log_error "Prompt file not found: $PROMPT_FILE"
        exit 1
    fi

    # Read template and substitute placeholders
    local template
    template=$(<"$PROMPT_FILE")
    template="${template//\{VERSION\}/$target_tag}"
    template="${template//\{RANGE\}/$range}"

    echo "$template"
}

# Main
main() {
    cd "$PROJECT_ROOT"

    # Handle help
    if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
        show_help
        exit 0
    fi

    # Get target tag
    local target_tag="${1:-}"
    if [[ -z "$target_tag" ]]; then
        target_tag=$(git tag -l 'v*' --sort=-v:refname | head -1)
        if [[ -z "$target_tag" ]]; then
            log_error "No version tags found. Create a tag first (e.g., git tag v0.1.0)"
            exit 1
        fi
    fi

    # Validate tag exists
    if ! git rev-parse "$target_tag" &>/dev/null; then
        log_error "Tag '$target_tag' does not exist"
        exit 1
    fi

    log_info "Generating changelog for $target_tag..."

    # Get commit range
    local range
    range=$(get_commit_range "$target_tag")
    log_info "Commit range: $range"

    # Check there are commits in range
    local commit_count
    commit_count=$(git rev-list --count "$range" 2>/dev/null || echo "0")
    if [[ "$commit_count" == "0" ]]; then
        log_warn "No commits found in range $range"
        exit 0
    fi
    log_info "Found $commit_count commits"

    # Create output directory
    mkdir -p "$(dirname "$PROMPT_OUTPUT")"

    # Build and save prompt
    local prompt
    prompt=$(build_prompt "$target_tag" "$range")
    echo "$prompt" > "$PROMPT_OUTPUT"

    # Done
    echo ""
    log_success "Prompt saved to .tmp/last-changelog-prompt.md"
    echo ""
    log_info "Paste this into your AI agent:"
    echo ""
    echo "  Read .tmp/last-changelog-prompt.md and follow its instructions. Save the result to .tmp/last-changelog.md"
    echo ""
}

main "$@"
