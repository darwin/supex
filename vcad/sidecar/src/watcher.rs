use notify::{Event, EventKind, RecommendedWatcher, RecursiveMode, Watcher};
use std::path::{Path, PathBuf};
use std::sync::mpsc;
use std::time::Duration;

/// A filesystem change detected by the watcher.
#[derive(Debug, Clone)]
pub struct FileChange {
    pub path: PathBuf,
    pub kind: FileChangeKind,
}

/// Classification of changed file type.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum FileChangeKind {
    /// A .cmp.oo file (VCAD node source).
    VcadLoon,
    /// A library .oo module file (legacy .loon still accepted).
    Loon,
}

pub struct FileWatcher {
    watcher: Option<RecommendedWatcher>,
    rx: mpsc::Receiver<Result<Event, notify::Error>>,
    tx: mpsc::Sender<Result<Event, notify::Error>>,
    watch_dir: Option<PathBuf>,
}

impl FileWatcher {
    pub fn new() -> Self {
        let (tx, rx) = mpsc::channel();
        Self {
            watcher: None,
            rx,
            tx,
            watch_dir: None,
        }
    }

    /// Start watching a project directory for .cmp.oo and .oo module changes.
    pub fn watch(&mut self, dir: &Path) -> Result<(), String> {
        // Stop previous watch if any
        self.stop();

        let tx = self.tx.clone();
        let watcher = RecommendedWatcher::new(
            move |res| {
                let _ = tx.send(res);
            },
            notify::Config::default().with_poll_interval(Duration::from_millis(500)),
        )
        .map_err(|e| format!("Failed to create watcher: {}", e))?;

        self.watcher = Some(watcher);

        self.watcher
            .as_mut()
            .unwrap()
            .watch(dir, RecursiveMode::Recursive)
            .map_err(|e| format!("Failed to watch directory: {}", e))?;

        self.watch_dir = Some(dir.to_path_buf());

        tracing::info!("Started watching directory: {}", dir.display());
        Ok(())
    }

    /// Stop watching. Idempotent.
    pub fn stop(&mut self) {
        if let Some(ref mut w) = self.watcher {
            if let Some(ref dir) = self.watch_dir {
                let _ = w.unwatch(dir);
            }
        }
        self.watcher = None;
        self.watch_dir = None;
        // Drain any pending events
        while self.rx.try_recv().is_ok() {}
    }

    /// Whether the watcher is currently active.
    #[allow(dead_code)]
    pub fn is_watching(&self) -> bool {
        self.watcher.is_some()
    }

    /// The directory currently being watched, if any.
    #[allow(dead_code)]
    pub fn watch_dir(&self) -> Option<&Path> {
        self.watch_dir.as_deref()
    }

    /// Poll for changed files since last poll. Non-blocking.
    /// Deduplicates by path and filters to relevant file types.
    pub fn poll_changes(&self) -> Vec<FileChange> {
        let mut seen = std::collections::HashSet::new();
        let mut changes = Vec::new();

        while let Ok(event_result) = self.rx.try_recv() {
            let event = match event_result {
                Ok(e) => e,
                Err(err) => {
                    tracing::warn!("Watcher error: {}", err);
                    continue;
                }
            };

            // Only care about create/modify/remove events
            match event.kind {
                EventKind::Create(_) | EventKind::Modify(_) | EventKind::Remove(_) => {}
                _ => continue,
            }

            for path in event.paths {
                if seen.contains(&path) {
                    continue;
                }

                if let Some(change) = classify_path(&path) {
                    seen.insert(path);
                    changes.push(change);
                }
            }
        }

        changes
    }
}

/// Classify a file path into a FileChange if it's a relevant file type.
fn classify_path(path: &Path) -> Option<FileChange> {
    let name = path.file_name()?.to_str()?;

    if name.ends_with(".cmp.oo") {
        Some(FileChange {
            path: path.to_path_buf(),
            kind: FileChangeKind::VcadLoon,
        })
    } else if name.ends_with(".oo") || name.ends_with(".loon") {
        Some(FileChange {
            path: path.to_path_buf(),
            kind: FileChangeKind::Loon,
        })
    } else {
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn test_classify_cmp_oo() {
        let change = classify_path(Path::new("/project/test.cmp.oo"));
        assert!(change.is_some());
        assert_eq!(change.unwrap().kind, FileChangeKind::VcadLoon);
    }

    #[test]
    fn test_classify_module_oo() {
        let change = classify_path(Path::new("/project/src/build.oo"));
        assert!(change.is_some());
        assert_eq!(change.unwrap().kind, FileChangeKind::Loon);
    }

    #[test]
    fn test_classify_module_loon_legacy() {
        let change = classify_path(Path::new("/project/src/build.loon"));
        assert!(change.is_some());
        assert_eq!(change.unwrap().kind, FileChangeKind::Loon);
    }

    #[test]
    fn test_classify_other() {
        assert!(classify_path(Path::new("/project/readme.md")).is_none());
        assert!(classify_path(Path::new("/project/test.rs")).is_none());
    }

    #[test]
    fn test_watcher_lifecycle() {
        let dir = tempfile::tempdir().unwrap();
        let mut watcher = FileWatcher::new();

        assert!(!watcher.is_watching());
        assert!(watcher.watch_dir().is_none());

        watcher.watch(dir.path()).unwrap();
        assert!(watcher.is_watching());
        assert_eq!(watcher.watch_dir(), Some(dir.path()));

        // No changes yet
        let changes = watcher.poll_changes();
        assert!(changes.is_empty());

        watcher.stop();
        assert!(!watcher.is_watching());
        assert!(watcher.watch_dir().is_none());
    }

    #[test]
    fn test_watcher_detects_cmp_oo_change() {
        let dir = tempfile::tempdir().unwrap();
        let mut watcher = FileWatcher::new();
        watcher.watch(dir.path()).unwrap();

        // Create a .cmp.oo file
        let file_path = dir.path().join("test.cmp.oo");
        fs::write(&file_path, "[cube 10.0 10.0 10.0]").unwrap();

        // Give the watcher time to pick up the event
        std::thread::sleep(Duration::from_millis(200));

        let changes = watcher.poll_changes();
        // Should have at least one VcadLoon change
        let vcad_changes: Vec<_> = changes
            .iter()
            .filter(|c| c.kind == FileChangeKind::VcadLoon)
            .collect();
        assert!(
            !vcad_changes.is_empty(),
            "Expected at least one VcadLoon change, got {:?}",
            changes
                .iter()
                .map(|c| c.path.display().to_string())
                .collect::<Vec<_>>()
        );

        watcher.stop();
    }

    #[test]
    fn test_watcher_ignores_non_relevant_files() {
        let dir = tempfile::tempdir().unwrap();
        let mut watcher = FileWatcher::new();
        watcher.watch(dir.path()).unwrap();

        // Create a non-relevant file
        fs::write(dir.path().join("readme.md"), "hello").unwrap();

        std::thread::sleep(Duration::from_millis(200));

        let changes = watcher.poll_changes();
        assert!(
            changes.is_empty(),
            "Expected no relevant changes, got {:?}",
            changes
                .iter()
                .map(|c| c.path.display().to_string())
                .collect::<Vec<_>>()
        );

        watcher.stop();
    }

    #[test]
    fn test_watcher_stop_is_idempotent() {
        let mut watcher = FileWatcher::new();
        watcher.stop(); // Should not panic
        watcher.stop(); // Should not panic
    }

    #[test]
    fn test_watcher_rewatch() {
        let dir1 = tempfile::tempdir().unwrap();
        let dir2 = tempfile::tempdir().unwrap();
        let mut watcher = FileWatcher::new();

        watcher.watch(dir1.path()).unwrap();
        assert_eq!(watcher.watch_dir(), Some(dir1.path()));

        // Re-watch a different directory
        watcher.watch(dir2.path()).unwrap();
        assert_eq!(watcher.watch_dir(), Some(dir2.path()));

        watcher.stop();
    }
}
