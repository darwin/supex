FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

# Base system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    curl \
    git \
    gnupg \
    libyaml-dev \
    && rm -rf /var/lib/apt/lists/*

# Tauri (viewer backend) native build deps, needed by clippy in the lint stage
RUN apt-get update && apt-get install -y --no-install-recommends \
    libwebkit2gtk-4.1-dev \
    libgtk-3-dev \
    libayatana-appindicator3-dev \
    librsvg2-dev \
    libssl-dev \
    libxdo-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# --- Ruby 3.2.2 (precompiled, into /usr/local/ where shebangs expect it) ---
COPY --from=ruby:3.2.2-slim-bookworm /usr/local/ /usr/local/

# --- Rust toolchain (into /usr/local/cargo, no conflict with Ruby) ---
# Keep the minor in sync with rust-version in vcad/sidecar/Cargo.toml and vcad/viewer/src-tauri/Cargo.toml
COPY --from=rust:1.96-bookworm /usr/local/rustup /usr/local/rustup
COPY --from=rust:1.96-bookworm /usr/local/cargo /usr/local/cargo
ENV RUSTUP_HOME=/usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo
ENV PATH="/usr/local/cargo/bin:$PATH"
RUN rustup component add rustfmt clippy

# --- Python 3.14 via uv ---
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
RUN uv python install 3.14

# --- Node.js 22 LTS ---
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/* && \
    npm install -g markdownlint-cli

# --- Copy project sources ---
WORKDIR /app
COPY . .

# --- Font required by vcad-kernel-text (include_bytes! at compile time) ---
# Extract just the .ttf from the next npm tarball — avoids full workspace install.
RUN mkdir -p vcad/vendor/vcad/node_modules/next && \
    npm pack next@15 --pack-destination /tmp --silent && \
    tar xzf /tmp/next-*.tgz -C vcad/vendor/vcad/node_modules/next \
        --strip-components=1 \
        package/dist/compiled/@vercel/og/noto-sans-v27-latin-regular.ttf && \
    rm /tmp/next-*.tgz

# --- Fetch Rust dependencies (cached unless Cargo.lock changes) ---
RUN cd vcad/sidecar && cargo fetch
RUN cd vcad/viewer/src-tauri && cargo fetch

# --- Install dependencies for each test suite ---

# Python: driver + radar + e2e tests (lint only)
RUN cd driver && uv sync
RUN cd devtools/radar && uv sync
RUN cd tests && uv sync

# Ruby: stdlib, runtime, mock + docgen and snippets (lint only)
RUN cd stdlib && bundle install
RUN cd runtime && bundle install
RUN cd mock && bundle install
RUN cd devtools/docgen && bundle install
RUN cd tests/snippets && bundle install

# Node: viewer
RUN cd vcad/viewer && npm ci

# --- Run tests (override with --entrypoint scripts/lint.sh for the lint stage) ---
ENTRYPOINT ["scripts/launch-test.sh"]
