use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};

/// Tracks which `.loon` library files each vcad node depends on (via `[use ...]`).
///
/// After each evaluation, the sidecar records the loaded module paths for the
/// node. When a shared library file changes, `get_affected_nodes()` returns all
/// vcad nodes that need re-evaluation.
pub struct ModuleTracker {
    /// Maps: node_id -> Set<file_path> (all .loon files loaded via [use ...])
    node_modules: HashMap<String, HashSet<PathBuf>>,
    /// Inverse: file_path -> Set<node_id> (which nodes depend on this file)
    file_dependents: HashMap<PathBuf, HashSet<String>>,
}

impl ModuleTracker {
    pub fn new() -> Self {
        Self {
            node_modules: HashMap::new(),
            file_dependents: HashMap::new(),
        }
    }

    /// Record module dependencies after evaluation.
    ///
    /// Clears previous state for `node_id` and rebuilds from the fresh
    /// `loaded_paths` returned by the Loon interpreter's module tracking.
    pub fn record_evaluation(&mut self, node_id: &str, loaded_paths: Vec<PathBuf>) {
        // Clear previous state for this node
        self.clear_node(node_id);

        // Build forward and inverse maps
        let paths: HashSet<PathBuf> = loaded_paths.into_iter().collect();
        for path in &paths {
            self.file_dependents
                .entry(path.clone())
                .or_default()
                .insert(node_id.to_string());
        }
        self.node_modules.insert(node_id.to_string(), paths);
    }

    /// Get all node_ids that depend on `changed_file`.
    pub fn get_affected_nodes(&self, changed_file: &Path) -> Vec<String> {
        self.file_dependents
            .get(changed_file)
            .map(|set| set.iter().cloned().collect())
            .unwrap_or_default()
    }

    /// Clear tracked state for a node (called before re-eval to rebuild).
    pub fn clear_node(&mut self, node_id: &str) {
        if let Some(old_paths) = self.node_modules.remove(node_id) {
            for path in old_paths {
                if let Some(deps) = self.file_dependents.get_mut(&path) {
                    deps.remove(node_id);
                    if deps.is_empty() {
                        self.file_dependents.remove(&path);
                    }
                }
            }
        }
    }

    /// Get all module paths tracked for a node.
    #[allow(dead_code)]
    pub fn get_node_modules(&self, node_id: &str) -> Vec<PathBuf> {
        self.node_modules
            .get(node_id)
            .map(|set| set.iter().cloned().collect())
            .unwrap_or_default()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_record_and_query() {
        let mut tracker = ModuleTracker::new();

        tracker.record_evaluation("node-a", vec![PathBuf::from("/project/src/dims.loon")]);
        tracker.record_evaluation(
            "node-b",
            vec![
                PathBuf::from("/project/src/dims.loon"),
                PathBuf::from("/project/src/helpers.loon"),
            ],
        );

        let affected = tracker.get_affected_nodes(Path::new("/project/src/dims.loon"));
        assert_eq!(affected.len(), 2);
        assert!(affected.contains(&"node-a".to_string()));
        assert!(affected.contains(&"node-b".to_string()));

        let affected = tracker.get_affected_nodes(Path::new("/project/src/helpers.loon"));
        assert_eq!(affected, vec!["node-b".to_string()]);
    }

    #[test]
    fn test_no_dependents() {
        let tracker = ModuleTracker::new();
        let affected = tracker.get_affected_nodes(Path::new("/nonexistent.loon"));
        assert!(affected.is_empty());
    }

    #[test]
    fn test_clear_node() {
        let mut tracker = ModuleTracker::new();

        tracker.record_evaluation("node-a", vec![PathBuf::from("/project/src/dims.loon")]);
        tracker.record_evaluation("node-b", vec![PathBuf::from("/project/src/dims.loon")]);

        tracker.clear_node("node-a");

        let affected = tracker.get_affected_nodes(Path::new("/project/src/dims.loon"));
        assert_eq!(affected, vec!["node-b".to_string()]);

        // node-a should have no modules
        assert!(tracker.get_node_modules("node-a").is_empty());
    }

    #[test]
    fn test_record_overwrites_previous() {
        let mut tracker = ModuleTracker::new();

        tracker.record_evaluation(
            "node-a",
            vec![
                PathBuf::from("/project/src/old.loon"),
                PathBuf::from("/project/src/dims.loon"),
            ],
        );

        // Re-record with different paths
        tracker.record_evaluation("node-a", vec![PathBuf::from("/project/src/dims.loon")]);

        // old.loon should no longer have dependents
        let affected = tracker.get_affected_nodes(Path::new("/project/src/old.loon"));
        assert!(affected.is_empty());

        // dims.loon still has node-a
        let affected = tracker.get_affected_nodes(Path::new("/project/src/dims.loon"));
        assert_eq!(affected, vec!["node-a".to_string()]);
    }

    #[test]
    fn test_get_node_modules() {
        let mut tracker = ModuleTracker::new();

        let paths = vec![
            PathBuf::from("/project/src/a.loon"),
            PathBuf::from("/project/src/b.loon"),
        ];
        tracker.record_evaluation("node-a", paths.clone());

        let mut modules = tracker.get_node_modules("node-a");
        modules.sort();
        assert_eq!(modules.len(), 2);
    }

    #[test]
    fn test_empty_loaded_paths() {
        let mut tracker = ModuleTracker::new();
        tracker.record_evaluation("node-a", vec![]);

        // Node exists but has no modules
        assert!(tracker.get_node_modules("node-a").is_empty());
    }

    #[test]
    fn test_clear_nonexistent_node() {
        let mut tracker = ModuleTracker::new();
        // Should not panic
        tracker.clear_node("nonexistent");
    }
}
