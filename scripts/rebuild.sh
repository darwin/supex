#!/usr/bin/env bash

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source common utilities
source "$SCRIPT_DIR/helpers/common.sh"

show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Rebuild all project binaries (sidecar + viewer).

OPTIONS:
    -h, --help      Show this help message

BUILDS:
    1. VCAD Sidecar (Rust)   — cargo build --release
    2. VCAD Viewer  (Tauri)  — npm run tauri build

EOF
}

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

main() {
    cd "$PROJECT_ROOT"

    require_command "cargo" "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    require_command "npm" "brew install node"

    local failed=0

    # 1. VCAD Sidecar
    log_info "Building VCAD Sidecar..."
    if (cd vcad/sidecar && cargo build --release); then
        log_success "VCAD Sidecar built"
    else
        log_error "VCAD Sidecar build failed"
        failed=1
    fi

    # 2. VCAD Viewer
    if [[ $failed -eq 0 ]]; then
        log_info "Building VCAD Viewer..."
        if (cd vcad/viewer && npm run tauri build); then
            log_success "VCAD Viewer built"
        else
            log_error "VCAD Viewer build failed"
            failed=1
        fi
    fi

    if [[ $failed -ne 0 ]]; then
        log_error "Build failed"
        exit 1
    fi

    log_success "All binaries rebuilt"
}

main
