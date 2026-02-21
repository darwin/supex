mod adt_cache;
mod config;
mod evaluator;
mod obj_export;
mod server;

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
