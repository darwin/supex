#!/usr/bin/env bash

set -euo pipefail

# Re-exec under mise if available and not already running under mise
if [[ -z "${MISE_SHELL:-}" ]] && command -v mise &> /dev/null; then
    exec mise exec -- "$0" "$@"
fi

# Configuration
RUN_E2E=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source common utilities (colors and logging)
source "$SCRIPT_DIR/helpers/common.sh"

# Test suite registry: slug|display name|directory|command|requires_e2e
SUITES=(
    "driver|Python Driver Tests|driver|uv run python -m pytest tests/|false"
    "stdlib|Ruby Stdlib Tests|stdlib|bundle exec rake test|false"
    "runtime|Ruby Runtime Tests|runtime|bundle exec rake test|false"
    "mock|Ruby Mock Tests|mock|bundle exec rake test|false"
    "sidecar|VCAD Sidecar Tests|vcad/sidecar|cargo test|false"
    "viewer|VCAD Viewer Tests|vcad/viewer|npx vitest run|false"
    "radar|Radar Tests|devtools/radar|uv run python -m pytest tests/|false"
    "e2e|E2E Tests|tests|uv run python -m pytest e2e/ -v|true"
)

# Parse a suite entry field by index (0-based)
suite_field() {
    echo "$1" | cut -d'|' -f"$(($2 + 1))"
}

list_suites() {
    echo "Available test suites:"
    echo ""
    for entry in "${SUITES[@]}"; do
        local slug display e2e_flag
        slug=$(suite_field "$entry" 0)
        display=$(suite_field "$entry" 1)
        e2e_flag=$(suite_field "$entry" 4)
        if [ "$e2e_flag" = "true" ]; then
            printf "  %-12s %s (requires --e2e)\n" "$slug" "$display"
        else
            printf "  %-12s %s\n" "$slug" "$display"
        fi
    done
}

# Parse command line arguments
show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS] [SUITE...]

Run tests for specified subsystems. Without SUITE arguments, runs all
non-E2E test suites.

SUITES:
$(list_suites)

OPTIONS:
    -e, --e2e       Run E2E tests only (requires SketchUp running)
    -l, --list      List available test suites
    -h, --help      Show this help message

EXAMPLES:
    $(basename "$0")                    # Run all headless tests
    $(basename "$0") driver viewer      # Run only driver and viewer tests
    $(basename "$0") --e2e              # Run E2E tests only
    $(basename "$0") sidecar            # Run only sidecar tests

EOF
}

SELECTED_SUITES=()

while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--e2e)
            RUN_E2E=true
            shift
            ;;
        -l|--list)
            list_suites
            exit 0
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        -*)
            echo -e "${RED}Error: Unknown option: $1${NC}" >&2
            show_help
            exit 1
            ;;
        *)
            SELECTED_SUITES+=("$1")
            shift
            ;;
    esac
done

# Validate selected suite slugs
for slug in "${SELECTED_SUITES[@]}"; do
    found=false
    for entry in "${SUITES[@]}"; do
        if [ "$(suite_field "$entry" 0)" = "$slug" ]; then
            found=true
            break
        fi
    done
    if [ "$found" = false ]; then
        echo -e "${RED}Error: Unknown test suite: $slug${NC}" >&2
        echo ""
        list_suites
        exit 1
    fi
done

# Track test results
FAILED_SUITES=()
PASSED_SUITES=()

print_section() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

run_test_suite() {
    local name="$1"
    local dir="$2"
    local command="$3"

    print_section "Running $name"

    if [ ! -d "$dir" ]; then
        echo -e "${RED}Error: Directory not found: $dir${NC}" >&2
        FAILED_SUITES+=("$name (directory not found)")
        return 1
    fi

    # Change to directory and run command
    # uv run and bundle exec handle their own environments
    if (cd "$dir" && eval "$command"); then
        echo -e "${GREEN}✓ $name passed${NC}"
        PASSED_SUITES+=("$name")
        return 0
    else
        echo -e "${RED}✗ $name failed${NC}" >&2
        FAILED_SUITES+=("$name")
        return 1
    fi
}

print_summary() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Test Summary${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    if [ ${#PASSED_SUITES[@]} -gt 0 ]; then
        echo -e "${GREEN}Passed (${#PASSED_SUITES[@]}):${NC}"
        for suite in "${PASSED_SUITES[@]}"; do
            echo -e "${GREEN}  ✓ $suite${NC}"
        done
        echo ""
    fi

    if [ ${#FAILED_SUITES[@]} -gt 0 ]; then
        echo -e "${RED}Failed (${#FAILED_SUITES[@]}):${NC}"
        for suite in "${FAILED_SUITES[@]}"; do
            echo -e "${RED}  ✗ $suite${NC}"
        done
        echo ""
        return 1
    fi

    echo -e "${GREEN}All test suites passed!${NC}"
    return 0
}

# Determine if a suite should run
should_run() {
    local slug="$1"
    local e2e_flag="$2"

    # Explicit selection: run exactly what was requested
    if [ ${#SELECTED_SUITES[@]} -gt 0 ]; then
        for s in "${SELECTED_SUITES[@]}"; do
            if [ "$s" = "$slug" ]; then
                return 0
            fi
        done
        return 1
    fi

    # --e2e: run only e2e suites
    if [ "$RUN_E2E" = true ]; then
        [ "$e2e_flag" = "true" ] && return 0 || return 1
    fi

    # Default: run only non-e2e suites
    [ "$e2e_flag" = "true" ] && return 1
    return 0
}

# Main execution
main() {
    cd "$PROJECT_ROOT"

    echo -e "${BLUE}Starting test run...${NC}"
    if [ ${#SELECTED_SUITES[@]} -gt 0 ]; then
        echo -e "${YELLOW}Running selected suites: ${SELECTED_SUITES[*]}${NC}"
    elif [ "$RUN_E2E" = true ]; then
        echo -e "${YELLOW}Running E2E tests only${NC}"
    else
        echo -e "${YELLOW}Tip: use ./test --e2e to run E2E tests (requires SketchUp running)${NC}"
    fi
    echo ""

    # Check required tools
    require_command "uv" "pip install uv"
    require_command "bundle" "gem install bundler"
    require_command "cargo" "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    require_command "npx" "brew install node"

    for entry in "${SUITES[@]}"; do
        local slug display dir command e2e_flag
        slug=$(suite_field "$entry" 0)
        display=$(suite_field "$entry" 1)
        dir=$(suite_field "$entry" 2)
        command=$(suite_field "$entry" 3)
        e2e_flag=$(suite_field "$entry" 4)

        if should_run "$slug" "$e2e_flag"; then
            run_test_suite "$display" "${PROJECT_ROOT}/${dir}" "$command" || true
        fi
    done

    # Print summary and exit with appropriate code
    if print_summary; then
        exit 0
    else
        exit 1
    fi
}

main
