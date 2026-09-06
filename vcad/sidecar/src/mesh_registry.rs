//! Native SketchUp meshes referenced from loon programs by a sentinel path.
//!
//! A `:solid` import of a native SketchUp entity enters the program as
//! `[MeshImport "<sentinel>" 1.0 1.0 1.0]`, an upstream VCAD constructor, so
//! the loon value stays small and cached ADT trees remain self-contained. The
//! sentinel is an absolute path under the sidecar temp directory that is never
//! written; after `value_to_document_in` the registry rewrites every
//! `MeshImport` node carrying such a path into `ImportedMesh` with the exact
//! vertex data (f64 millimetres, SketchUp normals), the same rewrite vcad's own
//! browser flow performs before evaluation.

use crate::imports::NativeMeshData;
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use vcad_ir::{CsgOp, Document};

/// Directory (under the sidecar temp dir) that sentinel paths live in.
const SENTINEL_DIR: &str = "native-mesh";
const SENTINEL_EXT: &str = "mesh";

pub struct MeshRegistry {
    dir: PathBuf,
    entries: HashMap<String, Entry>,
    max_entries: usize,
    access_seq: u64,
}

struct Entry {
    mesh: NativeMeshData,
    last_access: u64,
}

impl MeshRegistry {
    /// A registry whose sentinels live under `temp_dir` and that keeps at most
    /// `max_entries` meshes (LRU).
    pub fn new(temp_dir: &Path, max_entries: usize) -> Self {
        let root = std::path::absolute(temp_dir).unwrap_or_else(|_| temp_dir.to_path_buf());
        Self {
            dir: root.join(SENTINEL_DIR),
            entries: HashMap::new(),
            max_entries: max_entries.max(1),
            access_seq: 0,
        }
    }

    /// Register `mesh` and return the sentinel path that refers to it.
    ///
    /// Content-addressed: the same mesh always maps to the same sentinel.
    pub fn register(&mut self, mesh: &NativeMeshData) -> String {
        let key = Self::hash(mesh);
        self.access_seq += 1;
        let seq = self.access_seq;
        self.entries
            .entry(key.clone())
            .and_modify(|e| e.last_access = seq)
            .or_insert_with(|| Entry {
                mesh: mesh.clone(),
                last_access: seq,
            });
        self.evict_if_needed();
        self.sentinel_for(&key)
    }

    /// Rewrite every `MeshImport` node whose path is one of this registry's
    /// sentinels into an `ImportedMesh` node with the registered vertex data.
    ///
    /// Returns the number of rewritten nodes. A sentinel with no registered
    /// mesh (evicted, or from a sidecar restart) is an error: vcad-eval would
    /// otherwise treat it as a missing STL and silently produce no geometry.
    pub fn resolve(&mut self, doc: &mut Document) -> Result<usize, String> {
        let mut rewritten = 0;
        for node in doc.nodes.values_mut() {
            let CsgOp::MeshImport { path, .. } = &node.op else {
                continue;
            };
            let Some(key) = self.key_for(path) else {
                continue;
            };
            self.access_seq += 1;
            let seq = self.access_seq;
            let entry = self.entries.get_mut(&key).ok_or_else(|| {
                format!(
                    "NATIVE_MESH_MISS: no registered mesh for '{path}' — \
                     re-run the import from SketchUp (the sidecar may have restarted \
                     or evicted it)"
                )
            })?;
            entry.last_access = seq;
            node.op = CsgOp::ImportedMesh {
                positions: entry.mesh.positions.clone(),
                indices: entry.mesh.indices.clone(),
                normals: Some(entry.mesh.normals.clone()),
                source: Some(path.clone()),
            };
            rewritten += 1;
        }
        Ok(rewritten)
    }

    #[cfg(test)]
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    fn sentinel_for(&self, key: &str) -> String {
        self.dir
            .join(format!("{key}.{SENTINEL_EXT}"))
            .to_string_lossy()
            .into_owned()
    }

    /// The registry key encoded in `path`, if it is one of our sentinels.
    fn key_for(&self, path: &str) -> Option<String> {
        let p = Path::new(path);
        if p.parent() != Some(self.dir.as_path()) {
            return None;
        }
        if p.extension().and_then(|e| e.to_str()) != Some(SENTINEL_EXT) {
            return None;
        }
        p.file_stem().and_then(|s| s.to_str()).map(str::to_owned)
    }

    fn hash(mesh: &NativeMeshData) -> String {
        let mut hasher = blake3::Hasher::new();
        for v in &mesh.positions {
            hasher.update(&v.to_le_bytes());
        }
        hasher.update(b"|");
        for i in &mesh.indices {
            hasher.update(&i.to_le_bytes());
        }
        hasher.update(b"|");
        for n in &mesh.normals {
            hasher.update(&n.to_le_bytes());
        }
        hasher.finalize().to_hex().to_string()
    }

    fn evict_if_needed(&mut self) {
        while self.entries.len() > self.max_entries {
            let lru = self
                .entries
                .iter()
                .min_by_key(|(_, e)| e.last_access)
                .map(|(k, _)| k.clone());
            match lru {
                Some(k) => {
                    self.entries.remove(&k);
                }
                None => break,
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use vcad_ir::{Node, SceneEntry};

    fn tetrahedron() -> NativeMeshData {
        NativeMeshData {
            positions: vec![
                0.0, 0.0, 0.0, 10.0, 0.0, 0.0, 5.0, 10.0, 0.0, 5.0, 5.0, 10.0,
            ],
            indices: vec![0, 2, 1, 0, 1, 3, 1, 2, 3, 2, 0, 3],
            normals: vec![0.0; 12],
        }
    }

    fn doc_with_mesh_import(path: &str) -> Document {
        let mut doc = Document::new();
        doc.nodes.insert(
            0,
            Node {
                id: 0,
                name: None,
                op: CsgOp::MeshImport {
                    path: path.to_string(),
                    scale: None,
                },
            },
        );
        doc.roots.push(SceneEntry {
            root: 0,
            material: "default".to_string(),
            visible: None,
        });
        doc
    }

    #[test]
    fn sentinel_is_absolute_and_content_addressed() {
        let temp = tempfile::tempdir().unwrap();
        let mut registry = MeshRegistry::new(temp.path(), 8);
        let a = registry.register(&tetrahedron());
        let b = registry.register(&tetrahedron());
        assert_eq!(a, b);
        assert!(Path::new(&a).is_absolute());
        assert!(a.starts_with(temp.path().join(SENTINEL_DIR).to_str().unwrap()));
        assert!(!Path::new(&a).exists(), "sentinels are never written");
        assert_eq!(registry.len(), 1);
    }

    #[test]
    fn resolve_rewrites_sentinel_into_imported_mesh() {
        let temp = tempfile::tempdir().unwrap();
        let mut registry = MeshRegistry::new(temp.path(), 8);
        let sentinel = registry.register(&tetrahedron());
        let mut doc = doc_with_mesh_import(&sentinel);

        assert_eq!(registry.resolve(&mut doc).unwrap(), 1);
        match &doc.nodes[&0].op {
            CsgOp::ImportedMesh {
                positions,
                indices,
                normals,
                source,
            } => {
                assert_eq!(positions.len(), 12);
                assert_eq!(indices.len(), 12);
                assert_eq!(normals.as_ref().map(Vec::len), Some(12));
                assert_eq!(source.as_deref(), Some(sentinel.as_str()));
            }
            other => panic!("expected ImportedMesh, got {other:?}"),
        }
    }

    #[test]
    fn resolve_leaves_real_mesh_imports_alone() {
        let temp = tempfile::tempdir().unwrap();
        let mut registry = MeshRegistry::new(temp.path(), 8);
        let real = temp.path().join("vendor").join("bracket.stl");
        let mut doc = doc_with_mesh_import(real.to_str().unwrap());
        assert_eq!(registry.resolve(&mut doc).unwrap(), 0);
        assert!(matches!(doc.nodes[&0].op, CsgOp::MeshImport { .. }));
    }

    #[test]
    fn resolve_fails_loudly_for_unregistered_sentinel() {
        let temp = tempfile::tempdir().unwrap();
        let mut registry = MeshRegistry::new(temp.path(), 8);
        let sentinel = registry.register(&tetrahedron());
        // A fresh registry over the same temp dir knows the sentinel shape but
        // has no data for it — the sidecar-restart case.
        let mut fresh = MeshRegistry::new(temp.path(), 8);
        let mut doc = doc_with_mesh_import(&sentinel);
        let err = fresh.resolve(&mut doc).unwrap_err();
        assert!(err.starts_with("NATIVE_MESH_MISS"), "{err}");
    }

    #[test]
    fn lru_eviction_keeps_recently_used() {
        let temp = tempfile::tempdir().unwrap();
        let mut registry = MeshRegistry::new(temp.path(), 2);
        let mut second = tetrahedron();
        second.positions[0] = 1.0;
        let mut third = tetrahedron();
        third.positions[0] = 2.0;

        let a = registry.register(&tetrahedron());
        registry.register(&second);
        registry.register(&tetrahedron()); // touch a
        registry.register(&third); // evicts second
        assert_eq!(registry.len(), 2);

        let mut doc = doc_with_mesh_import(&a);
        assert_eq!(registry.resolve(&mut doc).unwrap(), 1);
        let evicted = MeshRegistry::new(temp.path(), 2).sentinel_for(&MeshRegistry::hash(&second));
        let mut doc = doc_with_mesh_import(&evicted);
        assert!(registry.resolve(&mut doc).is_err());
    }
}
