mod adt_cache;
mod config;
mod dae_export;
mod evaluator;
mod imports;
mod module_tracker;
mod server;
mod watcher;

/// Pipe-separated log formatter: `timestamp|LEVEL|target|message`
struct PipeFormat;

impl<S, N> tracing_subscriber::fmt::FormatEvent<S, N> for PipeFormat
where
    S: tracing::Subscriber + for<'a> tracing_subscriber::registry::LookupSpan<'a>,
    N: for<'a> tracing_subscriber::fmt::FormatFields<'a> + 'static,
{
    fn format_event(
        &self,
        ctx: &tracing_subscriber::fmt::FmtContext<'_, S, N>,
        mut writer: tracing_subscriber::fmt::format::Writer<'_>,
        event: &tracing::Event<'_>,
    ) -> std::fmt::Result {
        let now = chrono::Local::now();
        write!(
            writer,
            "{}|{}|{}|",
            now.format("%Y-%m-%dT%H:%M:%S%.3f"),
            event.metadata().level(),
            event.metadata().target(),
        )?;
        ctx.field_format().format_fields(writer.by_ref(), event)?;
        writeln!(writer)
    }
}

fn main() {
    tracing_subscriber::fmt()
        .event_format(PipeFormat)
        .with_writer(std::io::stderr)
        .init();
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
