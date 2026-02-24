#!/usr/bin/env bash

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source common utilities
source "$SCRIPT_DIR/helpers/common.sh"

# Build target registry: slug|display name|directory|command
TARGETS=(
    "sidecar|VCAD Sidecar|vcad/sidecar|cargo build --release"
    "viewer|VCAD Viewer|vcad/viewer|npm run tauri build"
)

# Parse a target entry field by index (0-based)
target_field() {
    echo "$1" | cut -d'|' -f"$(($2 + 1))"
}

list_targets() {
    echo "Available build targets:"
    echo ""
    for entry in "${TARGETS[@]}"; do
        local slug display
        slug=$(target_field "$entry" 0)
        display=$(target_field "$entry" 1)
        printf "  %-12s %s\n" "$slug" "$display"
    done
}

show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS] [TARGET...]

Rebuild project binaries. Without TARGET arguments, rebuilds all targets.

TARGETS:
$(list_targets)

OPTIONS:
    -l, --list      List available build targets
    -h, --help      Show this help message

EXAMPLES:
    $(basename "$0")                # Rebuild all
    $(basename "$0") sidecar        # Rebuild only sidecar
    $(basename "$0") sidecar viewer # Rebuild both

EOF
}

SELECTED_TARGETS=()

while [[ $# -gt 0 ]]; do
    case $1 in
        -l|--list)
            list_targets
            exit 0
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        -*)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
        *)
            SELECTED_TARGETS+=("$1")
            shift
            ;;
    esac
done

# Validate selected target slugs
for slug in "${SELECTED_TARGETS[@]}"; do
    found=false
    for entry in "${TARGETS[@]}"; do
        if [ "$(target_field "$entry" 0)" = "$slug" ]; then
            found=true
            break
        fi
    done
    if [ "$found" = false ]; then
        log_error "Unknown build target: $slug"
        echo ""
        list_targets
        exit 1
    fi
done

should_build() {
    local slug="$1"
    if [ ${#SELECTED_TARGETS[@]} -eq 0 ]; then
        return 0
    fi
    for s in "${SELECTED_TARGETS[@]}"; do
        if [ "$s" = "$slug" ]; then
            return 0
        fi
    done
    return 1
}

main() {
    cd "$PROJECT_ROOT"

    require_command "cargo" "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    require_command "npm" "brew install node"

    local failed=0

    for entry in "${TARGETS[@]}"; do
        local slug display dir command
        slug=$(target_field "$entry" 0)
        display=$(target_field "$entry" 1)
        dir=$(target_field "$entry" 2)
        command=$(target_field "$entry" 3)

        if ! should_build "$slug"; then
            continue
        fi

        log_info "Building $display..."
        if (cd "$dir" && eval "$command"); then
            log_success "$display built"
        else
            log_error "$display build failed"
            failed=1
        fi
    done

    if [[ $failed -ne 0 ]]; then
        log_error "Build failed"
        exit 1
    fi

    log_success "All binaries rebuilt"
}

main
