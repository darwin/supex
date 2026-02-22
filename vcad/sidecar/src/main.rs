mod adt_cache;
mod config;
mod dae_export;
mod evaluator;
mod imports;
mod server;
mod watcher;

fn main() {
    tracing_subscriber::fmt::init();
    let config = config::Config::from_env();
    eprintln!(
        "vcad sidecar v{} (Rust + loon-lang)",
        env!("CARGO_PKG_VERSION")
    );
    if let Err(e) = server::run(&config) {
        eprintln!("Fatal error: {}", e);
        std::process::exit(1);
    }
}
