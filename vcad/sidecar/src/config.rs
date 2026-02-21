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
            temp_dir: Self::resolve_temp_dir(),
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

    /// Resolve temp directory: VCAD_TEMP_DIR > SUPEX_WORKSPACE/.tmp/vcad-sidecar.
    ///
    /// Panics if neither variable is set — silent fallback to system temp caused
    /// PATH_NOT_ALLOWED errors because SketchUp's path policy rejects imports
    /// from outside the workspace.
    fn resolve_temp_dir() -> PathBuf {
        if let Ok(dir) = std::env::var("VCAD_TEMP_DIR") {
            return PathBuf::from(dir);
        }
        if let Ok(ws) = std::env::var("SUPEX_WORKSPACE") {
            return PathBuf::from(ws).join(".tmp").join("vcad-sidecar");
        }
        panic!(
            "VCAD_TEMP_DIR or SUPEX_WORKSPACE must be set. \
             Without a workspace-relative temp directory, SketchUp will reject imported files."
        );
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

        // resolve_temp_dir requires at least SUPEX_WORKSPACE
        let tmp = tempfile::tempdir().unwrap();
        std::env::set_var("SUPEX_WORKSPACE", tmp.path());

        let config = Config::from_env();
        assert_eq!(config.host, "127.0.0.1");
        assert_eq!(config.port, 9877);
        assert_eq!(config.max_queue, 64);
        assert_eq!(config.eval_timeout_ms, 120_000);
        assert_eq!(config.adt_cache_max, 256);
        assert!(!config.allow_remote);
        assert!(config.auth_token.is_none());
        assert!(config.is_loopback());
        assert_eq!(
            config.temp_dir,
            tmp.path().join(".tmp").join("vcad-sidecar")
        );

        std::env::remove_var("SUPEX_WORKSPACE");
    }

    #[test]
    #[should_panic(expected = "VCAD_TEMP_DIR or SUPEX_WORKSPACE must be set")]
    fn test_temp_dir_panics_without_env() {
        std::env::remove_var("VCAD_TEMP_DIR");
        std::env::remove_var("SUPEX_WORKSPACE");
        Config::resolve_temp_dir();
    }

    #[test]
    fn test_vcad_temp_dir_takes_precedence() {
        let tmp = tempfile::tempdir().unwrap();
        let ws = tempfile::tempdir().unwrap();
        std::env::set_var("VCAD_TEMP_DIR", tmp.path());
        std::env::set_var("SUPEX_WORKSPACE", ws.path());

        let dir = Config::resolve_temp_dir();
        assert_eq!(dir, tmp.path());

        std::env::remove_var("VCAD_TEMP_DIR");
        std::env::remove_var("SUPEX_WORKSPACE");
    }

    #[test]
    fn test_is_loopback() {
        // Don't use from_env() — we only need to test the is_loopback method
        let mut config = Config {
            host: "127.0.0.1".into(),
            port: 9877,
            temp_dir: PathBuf::from("/tmp"),
            temp_ttl_sec: 3600,
            temp_max_files: 500,
            max_queue: 64,
            eval_timeout_ms: 120_000,
            adt_cache_max: 256,
            allow_remote: false,
            auth_token: None,
        };
        assert!(config.is_loopback());
        config.host = "localhost".into();
        assert!(config.is_loopback());
        config.host = "::1".into();
        assert!(config.is_loopback());
        config.host = "0.0.0.0".into();
        assert!(!config.is_loopback());
    }
}
