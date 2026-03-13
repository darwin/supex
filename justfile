# Launch SketchUp with Supex extension for development
sketchup:
    ./scripts/launch-sketchup.sh

# Run all tests (Python driver + Ruby runtime)
test:
    ./scripts/launch-test.sh

# Run E2E tests only (requires SketchUp running)
test-e2e:
    ./scripts/launch-test.sh --e2e

# Regenerate SketchUp API documentation
docs:
    ./scripts/regenerate-sketchup-api-docs.sh

# Clear stale Cargo check cache (fixes false errors after vendor roll)
clear-rust-caches:
    cargo clean --manifest-path vcad/sidecar/Cargo.toml
    cargo clean --manifest-path vcad/viewer/src-tauri/Cargo.toml

# Run all linters (RuboCop, ruff, mypy)
lint:
    ./scripts/lint.sh
