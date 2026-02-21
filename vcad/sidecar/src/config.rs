use std::path::PathBuf;

pub struct Config {
    pub host: String,
    pub port: u16,
    pub temp_dir: PathBuf,
    pub temp_ttl_sec: u64,
    pub temp_max_files: usize,
    pub max_queue: usize,
    pub eval_timeout_ms: u64,
    pub adt_cache_max: usize,
    pub allow_remote: bool,
    pub auth_token: Option<String>,
}

impl Config {
    pub fn from_env() -> Self {
        Self {
            host: std::env::var("VCAD_HOST").unwrap_or_else(|_| "127.0.0.1".into()),
            port: std::env::var("VCAD_PORT")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(9877),
            temp_dir: std::env::var("VCAD_TEMP_DIR")
                .map(PathBuf::from)
                .unwrap_or_else(|_| std::env::temp_dir().join("vcad-sidecar")),
            temp_ttl_sec: std::env::var("VCAD_TEMP_TTL_SEC")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(3600),
            temp_max_files: std::env::var("VCAD_TEMP_MAX_FILES")
                .ok()
                .and_then(|s| s.parse().ok())
                .filter(|v: &usize| *v > 0)
                .unwrap_or(500),
            max_queue: std::env::var("VCAD_MAX_QUEUE")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(64),
            eval_timeout_ms: std::env::var("VCAD_EVAL_TIMEOUT_MS")
                .ok()
                .and_then(|s| s.parse().ok())
                .unwrap_or(120_000),
            adt_cache_max: std::env::var("VCAD_ADT_CACHE_MAX")
                .ok()
                .and_then(|s| s.parse().ok())
                .filter(|v: &usize| *v > 0)
                .unwrap_or(256),
            allow_remote: std::env::var("VCAD_ALLOW_REMOTE")
                .ok()
                .map(|s| s == "1")
                .unwrap_or(false),
            auth_token: std::env::var("VCAD_AUTH_TOKEN").ok(),
        }
    }

    /// Returns true if the configured host is a loopback address.
    pub fn is_loopback(&self) -> bool {
        matches!(self.host.as_str(), "127.0.0.1" | "localhost" | "::1")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_defaults() {
        // Clear env vars that might interfere
        std::env::remove_var("VCAD_HOST");
        std::env::remove_var("VCAD_PORT");
        std::env::remove_var("VCAD_TEMP_DIR");
        std::env::remove_var("VCAD_MAX_QUEUE");
        std::env::remove_var("VCAD_EVAL_TIMEOUT_MS");
        std::env::remove_var("VCAD_ADT_CACHE_MAX");
        std::env::remove_var("VCAD_ALLOW_REMOTE");
        std::env::remove_var("VCAD_AUTH_TOKEN");
        std::env::remove_var("VCAD_TEMP_TTL_SEC");
        std::env::remove_var("VCAD_TEMP_MAX_FILES");

        let config = Config::from_env();
        assert_eq!(config.host, "127.0.0.1");
        assert_eq!(config.port, 9877);
        assert_eq!(config.max_queue, 64);
        assert_eq!(config.eval_timeout_ms, 120_000);
        assert_eq!(config.adt_cache_max, 256);
        assert!(!config.allow_remote);
        assert!(config.auth_token.is_none());
        assert!(config.is_loopback());
    }

    #[test]
    fn test_is_loopback() {
        let mut config = Config::from_env();
        config.host = "127.0.0.1".into();
        assert!(config.is_loopback());
        config.host = "localhost".into();
        assert!(config.is_loopback());
        config.host = "::1".into();
        assert!(config.is_loopback());
        config.host = "0.0.0.0".into();
        assert!(!config.is_loopback());
    }
}
