#!/usr/bin/env bash

set -e  # Exit on error
set -u  # Exit on undefined variable

# Re-exec under mise if available and not already running under mise
if [[ -z "${MISE_SHELL:-}" ]] && command -v mise &> /dev/null; then
    exec mise exec -- "$0" "$@"
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
RUN_E2E=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Parse command line arguments
show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Run all tests in all subprojects.

OPTIONS:
    -e, --e2e       Include E2E tests (requires SketchUp running)
    -h, --help      Show this help message

EXAMPLES:
    $(basename "$0")            # Run unit tests only
    $(basename "$0") --e2e      # Run all tests including E2E

EOF
}

while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--e2e)
            RUN_E2E=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Error: Unknown option: $1${NC}" >&2
            show_help
            exit 1
            ;;
    esac
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

# Main execution
main() {
    cd "$PROJECT_ROOT"

    echo -e "${BLUE}Starting test run...${NC}"
    if [ "$RUN_E2E" = true ]; then
        echo -e "${YELLOW}E2E tests will be included${NC}"
    else
        echo -e "${YELLOW}E2E tests will be skipped (use --e2e to include)${NC}"
    fi
    echo ""

    # Check required tools
    if ! command -v uv &> /dev/null; then
        echo -e "${RED}Error: 'uv' command not found. Please install UV.${NC}" >&2
        exit 1
    fi

    if ! command -v bundle &> /dev/null; then
        echo -e "${RED}Error: 'bundle' command not found. Please install Bundler.${NC}" >&2
        exit 1
    fi

    # Run Python Driver tests
    run_test_suite \
        "Python Driver Tests" \
        "${PROJECT_ROOT}/driver" \
        "uv run pytest tests/" \
        || true  # Continue even if failed

    # Run Ruby Runtime tests
    run_test_suite \
        "Ruby Runtime Tests" \
        "${PROJECT_ROOT}/runtime" \
        "bundle exec rake test" \
        || true  # Continue even if failed

    # Run E2E tests if flag is set
    if [ "$RUN_E2E" = true ]; then
        run_test_suite \
            "E2E Tests" \
            "${PROJECT_ROOT}/tests" \
            "uv run pytest e2e/ -v" \
            || true  # Continue even if failed
    fi

    # Print summary and exit with appropriate code
    if print_summary; then
        exit 0
    else
        exit 1
    fi
}

main
