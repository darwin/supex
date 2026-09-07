#!/usr/bin/env bash

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source common utilities
source "$SCRIPT_DIR/helpers/common.sh"

# Version files to update (every component shares the supex version)
VERSION_FILES=(
    "driver/pyproject.toml"
    "tests/pyproject.toml"
    "devtools/radar/pyproject.toml"
    "runtime/src/supex_runtime/version.rb"
    "stdlib/src/supex_stdlib.rb"
    "vcad/sidecar/Cargo.toml"
    "vcad/viewer/src-tauri/Cargo.toml"
    "vcad/viewer/package.json"
)

# Lockfiles that record the root package version and are refreshed after the bump.
# tauri.conf.json carries no version on purpose: Tauri falls back to Cargo.toml.
LOCK_FILES=(
    "driver/uv.lock"
    "tests/uv.lock"
    "devtools/radar/uv.lock"
    "vcad/sidecar/Cargo.lock"
    "vcad/viewer/src-tauri/Cargo.lock"
    "vcad/viewer/package-lock.json"
)

show_help() {
    cat << EOF
Usage: $(basename "$0") [--bump-only] [--yes] <version>

Create a new release by updating version numbers, committing, tagging,
and fast-forwarding main to dev.

ARGUMENTS:
    version     New version in semver format (e.g., 0.2.0)

OPTIONS:
    --bump-only Only update version files and lockfiles, no git operations
                (useful to preview the diff; revert with git checkout)
    --yes, -y   Skip the confirmation prompt (required when stdin is not a
                terminal, e.g. when run through an agent's ! command)

EXAMPLES:
    $(basename "$0") 0.2.0
    $(basename "$0") 1.0.0
    $(basename "$0") --bump-only 0.3.0

WORKFLOW:
    1. Validates version format and git state
    2. Updates version in all component files and refreshes lockfiles
    3. Commits changes with "Release vX.Y.Z"
    4. Creates signed tag vX.Y.Z (requires GPG key)
    5. Fast-forwards main to dev
    6. Returns to dev branch

After running, push with:
    git push origin main dev --tags

EOF
}

# Validate semver format
validate_version() {
    local version="$1"
    if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        log_error "Invalid version format: $version"
        log_error "Expected semver format: X.Y.Z (e.g., 0.2.0)"
        exit 1
    fi
}

# Get current version from pyproject.toml
get_current_version() {
    grep -m1 '^version = "' "$PROJECT_ROOT/driver/pyproject.toml" | sed 's/version = "\(.*\)"/\1/'
}

# Compare versions (returns 0 if $1 > $2)
version_gt() {
    local v1="$1"
    local v2="$2"

    local v1_major v1_minor v1_patch
    local v2_major v2_minor v2_patch

    IFS='.' read -r v1_major v1_minor v1_patch <<< "$v1"
    IFS='.' read -r v2_major v2_minor v2_patch <<< "$v2"

    if (( v1_major > v2_major )); then return 0; fi
    if (( v1_major < v2_major )); then return 1; fi
    if (( v1_minor > v2_minor )); then return 0; fi
    if (( v1_minor < v2_minor )); then return 1; fi
    if (( v1_patch > v2_patch )); then return 0; fi
    return 1
}

# Update version in a file
update_version_file() {
    local file="$1"
    local version="$2"
    local filepath="$PROJECT_ROOT/$file"

    case "$file" in
        *.toml)
            # pyproject.toml / Cargo.toml: version = "X.Y.Z" (first match only, i.e. [project]/[package])
            sed -i '' "1,/^version = \"[0-9]*\.[0-9]*\.[0-9]*\"/ s/^version = \"[0-9]*\.[0-9]*\.[0-9]*\"/version = \"$version\"/" "$filepath"
            ;;
        *.rb)
            # Ruby: VERSION = 'X.Y.Z'
            sed -i '' "s/^  VERSION = '[0-9]*\.[0-9]*\.[0-9]*'/  VERSION = '$version'/" "$filepath"
            ;;
        *package.json)
            # npm updates package.json and package-lock.json together
            (cd "$(dirname "$filepath")" && npm version "$version" --no-git-tag-version --allow-same-version > /dev/null)
            ;;
    esac
}

# Refresh lockfiles so they record the new root package version
refresh_lockfiles() {
    local dir
    for dir in driver tests devtools/radar; do
        (cd "$PROJECT_ROOT/$dir" && uv lock --quiet)
        log_success "Refreshed $dir/uv.lock"
    done
    for dir in vcad/sidecar vcad/viewer/src-tauri; do
        (cd "$PROJECT_ROOT/$dir" && cargo update --workspace --offline --quiet)
        log_success "Refreshed $dir/Cargo.lock"
    done
}

# Update every version file and lockfile
bump_versions() {
    local version="$1"
    local file
    for file in "${VERSION_FILES[@]}"; do
        update_version_file "$file" "$version"
        log_success "Updated $file"
    done
    refresh_lockfiles
}

# Main
main() {
    cd "$PROJECT_ROOT"

    # Check for version argument
    if [[ $# -lt 1 ]]; then
        show_help
        exit 1
    fi

    if [[ "$1" == "-h" || "$1" == "--help" ]]; then
        show_help
        exit 0
    fi

    local bump_only=0
    local assume_yes=0
    while [[ $# -gt 0 && "$1" == -* ]]; do
        case "$1" in
            --bump-only) bump_only=1 ;;
            --yes|-y) assume_yes=1 ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
        shift
    done
    if [[ $# -lt 1 ]]; then
        show_help
        exit 1
    fi

    local new_version="$1"

    # === VALIDATION ===
    log_info "Validating..."

    # Validate version format
    validate_version "$new_version"

    if (( bump_only )); then
        log_info "Bumping version files to $new_version (no git operations)"
        bump_versions "$new_version"
        echo ""
        log_info "Review with: git diff"
        exit 0
    fi

    # Check we're on dev branch
    local current_branch
    current_branch=$(git branch --show-current)
    if [[ "$current_branch" != "dev" ]]; then
        log_error "Must be on 'dev' branch (currently on '$current_branch')"
        exit 1
    fi

    # Check for clean working tree
    if ! git diff --quiet || ! git diff --cached --quiet; then
        log_error "Working tree is not clean. Commit or stash changes first."
        exit 1
    fi

    # Check for untracked files in version locations
    if [[ -n "$(git status --porcelain)" ]]; then
        log_warn "There are untracked files in the repository"
    fi

    # Check version is greater than current
    local current_version
    current_version=$(get_current_version)
    if ! version_gt "$new_version" "$current_version"; then
        log_error "New version ($new_version) must be greater than current ($current_version)"
        exit 1
    fi

    # Check that main is ancestor of dev (fast-forward possible)
    if ! git merge-base --is-ancestor main dev; then
        log_error "Cannot fast-forward: 'main' is not an ancestor of 'dev'"
        log_error "This means 'main' has commits not in 'dev'. Resolve manually."
        exit 1
    fi

    log_success "Validation passed"

    # === DRY RUN OUTPUT ===
    echo ""
    log_info "Release plan:"
    echo "  Version:  $current_version -> $new_version"
    echo "  Tag:      v$new_version"
    echo "  Files to update:"
    for file in "${VERSION_FILES[@]}"; do
        echo "    - $file"
    done
    echo "  Lockfiles to refresh:"
    for file in "${LOCK_FILES[@]}"; do
        echo "    - $file"
    done
    echo ""

    # Confirm
    if (( ! assume_yes )) && ! confirm "Proceed with release?"; then
        log_warn "Aborted"
        exit 0
    fi

    # === UPDATE VERSIONS ===
    echo ""
    log_info "Updating version files..."
    bump_versions "$new_version"

    # === COMMIT ===
    # Stage only the known files: never git add -A, which would sweep in
    # vendor submodule pointer changes or stray files.
    log_info "Committing changes..."
    git add "${VERSION_FILES[@]}" "${LOCK_FILES[@]}"
    git commit -m "Release v$new_version"
    log_success "Created commit"

    # === TAG ===
    log_info "Creating signed tag..."
    git tag -s "v$new_version" -m "Release $new_version"
    log_success "Created signed tag v$new_version"

    # === FAST-FORWARD MAIN ===
    log_info "Fast-forwarding main..."
    git checkout main
    git merge dev --ff-only
    git checkout dev
    log_success "Main fast-forwarded to dev"

    # === DONE ===
    echo ""
    log_success "Release v$new_version complete!"
    echo ""
    log_info "Next steps:"
    echo "  1. Generate changelog for GitHub Release:"
    echo "     ./scripts/changelog.sh v$new_version"
    echo ""
    echo "  2. Push to remote:"
    echo "     git push origin main dev --tags"
    echo ""
}

main "$@"
