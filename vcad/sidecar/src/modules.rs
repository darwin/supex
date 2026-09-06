//! Module resolution for `[use ...]`: dependency tracking and the VCAD lib path.
//!
//! The sidecar evaluates programs through loon's `eval_program_with_modules`,
//! which consults a host [`ModuleProvider`] before the filesystem for every
//! `[use ...]` (including nested ones inside modules). [`RecordingProvider`]
//! uses that hook for two things:
//!
//! 1. **Dependency tracking** — every module resolved next to its importer is
//!    recorded (and then declined, so loon loads it from disk itself and nested
//!    `[use ...]` inside it keep resolving relative to the module).
//! 2. **Lib path** — a module missing next to the importer is looked up in the
//!    `VCAD_LOON_PATH` directories (the same search vcad's own tools perform),
//!    recorded, and served from there.

use loon_lang::module::{ModuleCache, ModuleProvider};
use std::cell::RefCell;
use std::path::{Path, PathBuf};

/// A [`ModuleProvider`] that records every module a program loads and falls
/// back to the VCAD lib path for modules not found beside their importer.
pub struct RecordingProvider {
    lib_dirs: Vec<PathBuf>,
    seen: RefCell<Vec<PathBuf>>,
}

impl RecordingProvider {
    /// A provider searching `lib_dirs` (in order) after the importer's directory.
    pub fn new(lib_dirs: Vec<PathBuf>) -> Self {
        Self {
            lib_dirs,
            seen: RefCell::new(Vec::new()),
        }
    }

    /// Paths of all modules resolved so far, in load order, without duplicates.
    pub fn loaded_paths(&self) -> Vec<PathBuf> {
        self.seen.borrow().clone()
    }

    fn record(&self, path: PathBuf) {
        let path = path.canonicalize().unwrap_or(path);
        let mut seen = self.seen.borrow_mut();
        if !seen.contains(&path) {
            seen.push(path);
        }
    }

    /// `<dir>/<a>/<b>.oo` (or `.loon`) for a dotted module name, if present.
    ///
    /// Mirrors `vcad_loon::LibPathProvider`: a module name is a name, not a
    /// path, so anything that would climb out of `dir` is refused.
    fn lib_candidate(dir: &Path, module_path: &str) -> Option<PathBuf> {
        let mut p = dir.to_path_buf();
        for part in module_path.split('.') {
            if part.is_empty() || part == ".." || part.contains(['/', '\\']) {
                return None;
            }
            p.push(part);
        }
        for ext in ["oo", "loon"] {
            let f = p.with_extension(ext);
            if f.is_file() {
                return Some(f);
            }
        }
        None
    }
}

impl ModuleProvider for RecordingProvider {
    fn fetch(&self, module_path: &str, from_dir: Option<&str>) -> Result<Option<String>, String> {
        // Beside the importer: record and decline, so loon's own filesystem
        // lookup loads it with the correct nested-resolution directory.
        if let Some(dir) = from_dir {
            let local = ModuleCache::resolve_path(module_path, Path::new(dir));
            if local.is_file() {
                self.record(local);
                return Ok(None);
            }
        }
        for dir in &self.lib_dirs {
            if let Some(file) = Self::lib_candidate(dir, module_path) {
                let source = std::fs::read_to_string(&file).map_err(|e| {
                    format!(
                        "cannot read module '{module_path}' at {}: {e}",
                        file.display()
                    )
                })?;
                self.record(file);
                return Ok(Some(source));
            }
        }
        Ok(None)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn local_module_is_recorded_and_declined() {
        let dir = tempfile::tempdir().unwrap();
        let module = dir.path().join("dims.oo");
        std::fs::write(&module, "[let width 10.0]").unwrap();

        let provider = RecordingProvider::new(Vec::new());
        let result = provider
            .fetch("dims", Some(dir.path().to_str().unwrap()))
            .unwrap();
        assert!(result.is_none(), "local modules are loaded by loon itself");
        assert_eq!(
            provider.loaded_paths(),
            vec![module.canonicalize().unwrap()]
        );
    }

    #[test]
    fn lib_module_is_served_and_recorded() {
        let project = tempfile::tempdir().unwrap();
        let lib = tempfile::tempdir().unwrap();
        std::fs::create_dir_all(lib.path().join("hardware")).unwrap();
        let module = lib.path().join("hardware").join("screws.oo");
        std::fs::write(&module, "[let m4 4.0]").unwrap();

        let provider = RecordingProvider::new(vec![lib.path().to_path_buf()]);
        let source = provider
            .fetch("hardware.screws", Some(project.path().to_str().unwrap()))
            .unwrap();
        assert_eq!(source.as_deref(), Some("[let m4 4.0]"));
        assert_eq!(
            provider.loaded_paths(),
            vec![module.canonicalize().unwrap()]
        );
    }

    #[test]
    fn local_module_shadows_lib_module() {
        let project = tempfile::tempdir().unwrap();
        let lib = tempfile::tempdir().unwrap();
        std::fs::write(project.path().join("dims.oo"), "[let width 1.0]").unwrap();
        std::fs::write(lib.path().join("dims.oo"), "[let width 2.0]").unwrap();

        let provider = RecordingProvider::new(vec![lib.path().to_path_buf()]);
        let result = provider
            .fetch("dims", Some(project.path().to_str().unwrap()))
            .unwrap();
        assert!(result.is_none());
        assert_eq!(
            provider.loaded_paths(),
            vec![project.path().join("dims.oo").canonicalize().unwrap()]
        );
    }

    #[test]
    fn unknown_module_declines_without_recording() {
        let project = tempfile::tempdir().unwrap();
        let provider = RecordingProvider::new(vec![project.path().join("nope")]);
        let result = provider
            .fetch("missing", Some(project.path().to_str().unwrap()))
            .unwrap();
        assert!(result.is_none());
        assert!(provider.loaded_paths().is_empty());
    }

    #[test]
    fn lib_lookup_refuses_path_traversal() {
        let lib = tempfile::tempdir().unwrap();
        assert!(RecordingProvider::lib_candidate(lib.path(), "..").is_none());
        assert!(RecordingProvider::lib_candidate(lib.path(), "a/b").is_none());
        assert!(RecordingProvider::lib_candidate(lib.path(), "a..b").is_none());
    }

    #[test]
    fn repeated_loads_are_recorded_once() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(dir.path().join("dims.oo"), "[let width 10.0]").unwrap();
        let provider = RecordingProvider::new(Vec::new());
        let from = dir.path().to_str().unwrap();
        provider.fetch("dims", Some(from)).unwrap();
        provider.fetch("dims", Some(from)).unwrap();
        assert_eq!(provider.loaded_paths().len(), 1);
    }
}
