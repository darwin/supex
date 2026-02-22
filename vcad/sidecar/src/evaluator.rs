use crate::adt_cache::AdtCache;
use crate::dae_export::{brep_to_dae, mesh_to_dae};
use crate::imports::{build_import_preamble, ResolvedImport};
use loon_lang::interp::{
    eval_program_with_env_and_base_dir, eval_program_with_module_tracking, Env, Value,
};
use loon_lang::parser::parse;
use serde::Serialize;
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use vcad_eval::{evaluate_document, EvalOptions};
use vcad_ir::Document;
use vcad_kernel_tessellate::TessellationParams;
use vcad_loon::{
    eval_vcad, eval_vcad_file, eval_vcad_to_value, value_to_document, VCAD_LIB_SOURCE,
};

struct TempRetention {
    ttl_sec: u64,
    max_files: usize,
    seq: u64,
}

pub struct Evaluator {
    temp_dir: PathBuf,
    adt_cache: AdtCache,
    retention: TempRetention,
}

#[derive(Debug, Clone, Serialize)]
pub struct EvalResult {
    pub obj_path: String,
    pub manifest_path: String,
    pub volume: f64,
    pub surface_area: f64,
    pub bbox: BBox,
    pub is_empty: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct ArtifactManifest {
    pub status: String,
    pub node_id: Option<String>,
    pub revision: Option<u64>,
    pub request_id: Option<String>,
    pub source_file: Option<String>,
    pub source_hash: String,
    pub obj_path: String,
    pub volume: f64,
    pub surface_area: f64,
    pub bbox: BBox,
    pub queued_at: Option<String>,
    pub started_at: Option<String>,
    pub finished_at: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct BBox {
    pub min: [f64; 3],
    pub max: [f64; 3],
}

impl Evaluator {
    pub fn new(temp_dir: PathBuf, ttl_sec: u64, max_files: usize, adt_cache_max: usize) -> Self {
        std::fs::create_dir_all(&temp_dir).ok();
        let max_files = max_files.max(1);
        let seq = Self::load_retention_seq(&temp_dir);
        let mut this = Self {
            temp_dir,
            adt_cache: AdtCache::new(adt_cache_max),
            retention: TempRetention {
                ttl_sec,
                max_files,
                seq,
            },
        };
        this.recover_incomplete_artifact_pairs().ok();
        this.cleanup_temp_dir();
        this
    }

    fn cleanup_temp_dir(&self) {
        let Ok(entries) = std::fs::read_dir(&self.temp_dir) else {
            return;
        };

        let now = std::time::SystemTime::now();
        let ttl = std::time::Duration::from_secs(self.retention.ttl_sec);

        // Collect all artifact pairs (obj + manifest)
        let mut obj_files: Vec<(PathBuf, std::time::SystemTime)> = Vec::new();
        let mut expired: Vec<PathBuf> = Vec::new();

        for entry in entries.flatten() {
            let path = entry.path();
            let ext = path.extension().and_then(|s| s.to_str());

            // Only manage mesh artifacts; manifests follow their mesh file
            if ext != Some("obj") && ext != Some("dae") {
                continue;
            }

            let mtime = entry
                .metadata()
                .ok()
                .and_then(|m| m.modified().ok())
                .unwrap_or(now);

            if now.duration_since(mtime).unwrap_or_default() > ttl {
                expired.push(path);
            } else {
                obj_files.push((path, mtime));
            }
        }

        // Remove expired files
        for path in &expired {
            std::fs::remove_file(path).ok();
            let manifest = path.with_extension("manifest.json");
            std::fs::remove_file(manifest).ok();
        }

        // Sort remaining by mtime (oldest first) and trim to max_files
        obj_files.sort_by_key(|(_, t)| *t);
        while obj_files.len() > self.retention.max_files {
            if let Some((path, _)) = obj_files.first() {
                std::fs::remove_file(path).ok();
                let manifest = path.with_extension("manifest.json");
                std::fs::remove_file(manifest).ok();
                obj_files.remove(0);
            } else {
                break;
            }
        }
    }

    fn load_retention_seq(temp_dir: &Path) -> u64 {
        let mut max_seq = 0_u64;
        let Ok(entries) = std::fs::read_dir(temp_dir) else {
            return 0;
        };

        for entry in entries.flatten() {
            let path = entry.path();
            let ext = path.extension().and_then(|s| s.to_str());
            if ext != Some("obj") && ext != Some("dae") {
                continue;
            }
            let Some(stem) = path.file_stem().and_then(|s| s.to_str()) else {
                continue;
            };
            let Some((_, seq_str)) = stem.rsplit_once('-') else {
                continue;
            };
            if seq_str.len() != 20 || !seq_str.bytes().all(|b| b.is_ascii_digit()) {
                continue;
            }
            if let Ok(seq) = seq_str.parse::<u64>() {
                max_seq = max_seq.max(seq);
            }
        }

        max_seq
    }

    fn next_artifact_path(&mut self, name: &str, ext: &str) -> Result<PathBuf, String> {
        let safe_name = Self::sanitize_obj_name(name);

        loop {
            let next_seq = self
                .retention
                .seq
                .checked_add(1)
                .ok_or_else(|| "TEMP_SEQ_EXHAUSTED".to_string())?;
            self.retention.seq = next_seq;
            let candidate = self
                .temp_dir
                .join(format!("{}-{:020}.{}", safe_name, self.retention.seq, ext));
            if !candidate.exists() {
                return Ok(candidate);
            }
        }
    }

    fn sanitize_obj_name(name: &str) -> String {
        name.chars()
            .map(|c| {
                if c.is_ascii_alphanumeric() || c == '-' || c == '_' {
                    c
                } else {
                    '_'
                }
            })
            .collect()
    }

    /// Evaluate inline Loon code (no module resolution).
    ///
    /// Caches the result ADT value for future solid imports.
    pub fn eval_code(&mut self, code: &str) -> Result<EvalResult, EvalError> {
        let doc = eval_vcad(code, None).map_err(EvalError::Loon)?;
        self.evaluate_and_export(&doc, "eval")
    }

    /// Evaluate inline Loon code and cache its ADT under `node_id`.
    #[allow(dead_code)]
    pub fn eval_code_with_cache(
        &mut self,
        code: &str,
        node_id: &str,
    ) -> Result<EvalResult, EvalError> {
        let adt_value = eval_vcad_to_value(code, None).map_err(EvalError::Loon)?;
        self.adt_cache.set(node_id, adt_value.clone());
        let doc = value_to_document(&adt_value).map_err(EvalError::Loon)?;
        self.evaluate_and_export(&doc, "eval")
    }

    /// Evaluate .skp.oo file (with module resolution via base_dir).
    ///
    /// Caches the result ADT value for future solid imports.
    pub fn eval_file(&mut self, path: &str) -> Result<EvalResult, EvalError> {
        let file_path = Path::new(path);
        let doc = eval_vcad_file(file_path).map_err(EvalError::Loon)?;
        let stem = file_path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("file");
        self.evaluate_and_export(&doc, stem)
    }

    /// Evaluate .skp.oo file and cache its ADT under `node_id`.
    #[allow(dead_code)]
    pub fn eval_file_with_cache(
        &mut self,
        path: &str,
        node_id: &str,
    ) -> Result<EvalResult, EvalError> {
        let file_path = Path::new(path);
        let base_dir = file_path.parent();
        let source = std::fs::read_to_string(file_path)
            .map_err(|e| EvalError::Loon(format!("cannot read {}: {e}", file_path.display())))?;
        let adt_value = eval_vcad_to_value(source.trim(), base_dir).map_err(EvalError::Loon)?;
        self.adt_cache.set(node_id, adt_value.clone());
        let doc = value_to_document(&adt_value).map_err(EvalError::Loon)?;
        let stem = file_path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("file");
        self.evaluate_and_export(&doc, stem)
    }

    /// Evaluate .skp.oo file with module tracking.
    ///
    /// Uses `eval_program_with_module_tracking` to capture all `.oo` module
    /// paths loaded via `[use ...]` during evaluation. Returns both the
    /// evaluation result and the list of loaded module paths.
    pub fn eval_file_tracked(
        &mut self,
        path: &str,
    ) -> Result<(EvalResult, Vec<std::path::PathBuf>), EvalError> {
        let file_path = Path::new(path);
        let base_dir = file_path.parent();
        let source = std::fs::read_to_string(file_path)
            .map_err(|e| EvalError::Loon(format!("cannot read {}: {e}", file_path.display())))?;
        let full_source = format!("{}\n\n{}", VCAD_LIB_SOURCE, source.trim());
        let exprs = parse(&full_source)
            .map_err(|e| EvalError::Loon(format!("Parse error: {}", e.message)))?;

        let (adt_value, loaded_paths) = eval_program_with_module_tracking(&exprs, base_dir)
            .map_err(|e| EvalError::Loon(format!("{e}")))?;

        let doc = value_to_document(&adt_value).map_err(EvalError::Loon)?;
        let stem = file_path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("file");
        let result = self.evaluate_and_export(&doc, stem)?;
        Ok((result, loaded_paths))
    }

    /// Evaluate a Document and return only geometry metadata (no mesh export).
    ///
    /// Used by `eval_with_imports(inspect_only=true)` to skip tessellation,
    /// DAE export, and disk I/O when only volume/bbox/surface_area are needed.
    fn evaluate_metadata_only(&self, doc: &Document) -> Result<EvalResult, EvalError> {
        let options = EvalOptions {
            skip_clash_detection: true,
            clock: None,
        };
        let scene = evaluate_document(doc, &options).map_err(EvalError::Kernel)?;
        let part = select_single_part(&scene)?;
        let solid = part
            .solid
            .as_ref()
            .ok_or_else(|| EvalError::Internal("No BRep solid produced".to_string()))?;

        let (bb_min, bb_max) = solid.bounding_box();

        Ok(EvalResult {
            obj_path: String::new(),
            manifest_path: String::new(),
            volume: solid.volume(),
            surface_area: solid.surface_area(),
            bbox: BBox {
                min: bb_min,
                max: bb_max,
            },
            is_empty: solid.is_empty(),
        })
    }

    /// Evaluate transformed source with both data and solid imports.
    ///
    /// Data imports (dimensions, bbox, transform) are injected as source-level
    /// let-bindings. Solid imports are injected directly into the Loon environment
    /// as cached ADT values retrieved from the ADT cache.
    ///
    /// The combined ADT tree flows through `value_to_document()` -> `evaluate_document()`
    /// so the kernel optimizes the full CSG tree in one pass.
    ///
    /// When `inspect_only` is true, skips tessellation, DAE export, and disk I/O,
    /// returning only geometry metadata (volume, surface_area, bbox).
    pub fn eval_with_imports(
        &mut self,
        transformed_source: &str,
        base_dir: Option<&Path>,
        imports: &HashMap<String, ResolvedImport>,
        node_id: Option<&str>,
        inspect_only: bool,
    ) -> Result<EvalResult, EvalError> {
        // 1. Build Loon preamble for data imports only (solid skipped)
        let preamble = build_import_preamble(imports);
        let augmented_source = format!("{}{}\n{}", VCAD_LIB_SOURCE, preamble, transformed_source);

        // 2. Parse the augmented source
        let exprs = parse(&augmented_source)
            .map_err(|e| EvalError::Loon(format!("Parse error: {}", e.message)))?;

        // 3. Set up Loon environment with solid ADT bindings
        let mut env = Env::new();
        for import in imports.values() {
            if import.extract == "solid" {
                if let Some(ref mesh_data) = import.native_mesh {
                    // Native SketchUp solid: build ImportedMesh ADT from mesh data
                    let positions = Value::Vec(
                        mesh_data.positions.iter().map(|&v| Value::Float(v)).collect(),
                    );
                    let indices = Value::Vec(
                        mesh_data.indices.iter().map(|&v| Value::Int(v as i64)).collect(),
                    );
                    let normals = Value::Vec(
                        mesh_data.normals.iter().map(|&v| Value::Float(v)).collect(),
                    );
                    let mesh_value = Value::Adt(
                        "ImportedMesh".to_string(),
                        vec![positions, indices, normals],
                    );
                    env.set(import.injected_symbol.clone(), mesh_value);
                } else if let Some(ref vcad_nid) = import.vcad_node_id {
                    if let Some(cached_adt) = self.adt_cache.get(vcad_nid) {
                        env.set(import.injected_symbol.clone(), cached_adt.clone());
                    } else {
                        return Err(EvalError::Loon(format!(
                            "ADT_CACHE_MISS: no cached ADT for node '{}' — \
                             the source node must be evaluated before it can be imported",
                            vcad_nid
                        )));
                    }
                } else {
                    return Err(EvalError::Loon(
                        "SOLID_IMPORT_UNAVAILABLE: :solid import requires a \
                         vcad-backed entity with a vcad_node_id or native mesh data"
                            .to_string(),
                    ));
                }
            }
        }

        // 4. Evaluate Loon with pre-populated environment
        let result_value = eval_program_with_env_and_base_dir(&exprs, &mut env, base_dir)
            .map_err(|e| EvalError::Loon(format!("{e}")))?;

        // 5. Cache the result ADT for future imports
        if let Some(nid) = node_id {
            self.adt_cache.set(nid, result_value.clone());
        }

        // 6. Convert to Document and evaluate
        let doc = value_to_document(&result_value).map_err(EvalError::Loon)?;
        if inspect_only {
            self.evaluate_metadata_only(&doc)
        } else {
            self.evaluate_and_export(&doc, "import-eval")
        }
    }

    /// Evaluate transformed source with imports in REPL mode (display string, no mesh).
    ///
    /// Same import resolution as `eval_with_imports` (data preamble + solid ADT
    /// injection), but returns the display string instead of converting to
    /// Document + mesh.
    pub fn eval_repl_with_imports(
        &mut self,
        transformed_source: &str,
        base_dir: Option<&Path>,
        imports: &HashMap<String, ResolvedImport>,
    ) -> Result<String, EvalError> {
        // 1. Build Loon preamble for data imports only (solid skipped)
        let preamble = build_import_preamble(imports);
        let augmented_source = format!("{}{}\n{}", VCAD_LIB_SOURCE, preamble, transformed_source);

        // 2. Parse the augmented source
        let exprs = parse(&augmented_source)
            .map_err(|e| EvalError::Loon(format!("Parse error: {}", e.message)))?;

        // 3. Set up Loon environment with solid ADT bindings
        let mut env = Env::new();
        for import in imports.values() {
            if import.extract == "solid" {
                if let Some(ref mesh_data) = import.native_mesh {
                    let positions = Value::Vec(
                        mesh_data.positions.iter().map(|&v| Value::Float(v)).collect(),
                    );
                    let indices = Value::Vec(
                        mesh_data.indices.iter().map(|&v| Value::Int(v as i64)).collect(),
                    );
                    let normals = Value::Vec(
                        mesh_data.normals.iter().map(|&v| Value::Float(v)).collect(),
                    );
                    let mesh_value = Value::Adt(
                        "ImportedMesh".to_string(),
                        vec![positions, indices, normals],
                    );
                    env.set(import.injected_symbol.clone(), mesh_value);
                } else if let Some(ref vcad_nid) = import.vcad_node_id {
                    if let Some(cached_adt) = self.adt_cache.get(vcad_nid) {
                        env.set(import.injected_symbol.clone(), cached_adt.clone());
                    } else {
                        return Err(EvalError::Loon(format!(
                            "ADT_CACHE_MISS: no cached ADT for node '{}' — \
                             the source node must be evaluated before it can be imported",
                            vcad_nid
                        )));
                    }
                } else {
                    return Err(EvalError::Loon(
                        "SOLID_IMPORT_UNAVAILABLE: :solid import requires a \
                         vcad-backed entity with a vcad_node_id or native mesh data"
                            .to_string(),
                    ));
                }
            }
        }

        // 4. Evaluate Loon with pre-populated environment
        let result_value = eval_program_with_env_and_base_dir(&exprs, &mut env, base_dir)
            .map_err(|e| EvalError::Loon(format!("{e}")))?;

        // 5. Return display string (no mesh conversion)
        Ok(format!("{}", result_value))
    }

    /// Provide read access to the ADT cache (for server-level queries).
    #[allow(dead_code)]
    pub fn adt_cache(&mut self) -> &mut AdtCache {
        &mut self.adt_cache
    }

    fn evaluate_and_export(&mut self, doc: &Document, name: &str) -> Result<EvalResult, EvalError> {
        // Pre-clean before export
        self.cleanup_temp_dir();

        let options = EvalOptions {
            skip_clash_detection: true,
            clock: None,
        };
        let scene = evaluate_document(doc, &options).map_err(EvalError::Kernel)?;
        let part = select_single_part(&scene)?;

        // Extract geometry metadata from Solid
        let (volume, surface_area, bbox, is_empty) = if let Some(ref solid) = part.solid {
            let (bb_min, bb_max) = solid.bounding_box();
            (
                solid.volume(),
                solid.surface_area(),
                BBox {
                    min: bb_min,
                    max: bb_max,
                },
                solid.is_empty(),
            )
        } else {
            // Fallback: compute bbox from mesh positions
            let bb = compute_mesh_bbox(&part.mesh);
            (0.0, 0.0, bb, false)
        };

        let (obj_content, ext) = if let Some(brep) = part.solid.as_ref().and_then(|s| s.brep()) {
            let params = TessellationParams::from_segments(32);
            let dae = brep_to_dae(brep, &params);
            (dae.into_bytes(), "dae")
        } else {
            (mesh_to_dae(&part.mesh).into_bytes(), "dae")
        };
        let obj_path = self.next_artifact_path(name, ext)?;
        let manifest_path = Self::manifest_path_for_obj(&obj_path, &self.temp_dir)?;
        let manifest = ArtifactManifest {
            status: "applied".to_string(),
            node_id: None,
            revision: None,
            request_id: None,
            source_file: None,
            source_hash: Self::hash_document(doc),
            obj_path: obj_path.to_string_lossy().into_owned(),
            volume,
            surface_area,
            bbox: BBox {
                min: bbox.min,
                max: bbox.max,
            },
            queued_at: None,
            started_at: None,
            finished_at: Self::now_rfc3339(),
        };

        Self::write_artifact_pair_atomic(
            &self.temp_dir,
            &obj_path,
            &obj_content,
            &manifest_path,
            &manifest,
        )
        .map_err(EvalError::Internal)?;

        self.cleanup_temp_dir();

        Ok(EvalResult {
            obj_path: obj_path.to_string_lossy().into_owned(),
            manifest_path: manifest_path.to_string_lossy().into_owned(),
            volume,
            surface_area,
            bbox,
            is_empty,
        })
    }

    fn write_artifact_pair_atomic(
        allowed_root: &Path,
        obj_path: &Path,
        obj_content: &[u8],
        manifest_path: &Path,
        manifest: &ArtifactManifest,
    ) -> Result<(), String> {
        let canonical_root = allowed_root
            .canonicalize()
            .map_err(|e| format!("PATH_NOT_ALLOWED: root canonicalize failed: {}", e))?;
        for p in [obj_path, manifest_path] {
            let parent = p
                .parent()
                .ok_or_else(|| "PATH_NOT_ALLOWED: missing parent".to_string())?;
            let canonical_parent = parent
                .canonicalize()
                .map_err(|e| format!("PATH_NOT_ALLOWED: parent canonicalize failed: {}", e))?;
            if !canonical_parent.starts_with(&canonical_root) {
                return Err("PATH_NOT_ALLOWED: artifact path outside allowed root".to_string());
            }
        }

        let ext = obj_path
            .extension()
            .and_then(|s| s.to_str())
            .unwrap_or("dae");
        let obj_tmp = obj_path.with_extension(format!("{ext}.tmp"));
        let manifest_tmp = manifest_path.with_extension("json.tmp");
        let pair_marker = obj_path.with_extension("pair.pending");

        let marker = serde_json::json!({
            "obj_path": obj_path.to_string_lossy(),
            "manifest_path": manifest_path.to_string_lossy(),
            "created_at": Self::now_rfc3339(),
        });
        let marker_body = serde_json::to_vec_pretty(&marker)
            .map_err(|e| format!("Pair marker serialize error: {}", e))?;
        std::fs::write(&pair_marker, marker_body)
            .map_err(|e| format!("Pair marker write error: {}", e))?;

        std::fs::write(&obj_tmp, obj_content)
            .map_err(|e| format!("OBJ temp write error: {}", e))?;

        let body = serde_json::to_vec_pretty(manifest)
            .map_err(|e| format!("Manifest serialize error: {}", e))?;
        std::fs::write(&manifest_tmp, body)
            .map_err(|e| format!("Manifest temp write error: {}", e))?;

        std::fs::rename(&obj_tmp, obj_path)
            .map_err(|e| format!("OBJ publish rename error: {}", e))?;
        std::fs::rename(&manifest_tmp, manifest_path)
            .map_err(|e| format!("Manifest publish rename error: {}", e))?;
        std::fs::remove_file(&pair_marker).ok();

        Ok(())
    }

    fn recover_incomplete_artifact_pairs(&mut self) -> Result<(), String> {
        let Ok(entries) = std::fs::read_dir(&self.temp_dir) else {
            return Ok(());
        };

        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().and_then(|s| s.to_str()) == Some("pending") {
                // Read marker to find associated files
                if let Ok(content) = std::fs::read_to_string(&path) {
                    if let Ok(marker) = serde_json::from_str::<serde_json::Value>(&content) {
                        // Clean up tmp files referenced in the marker
                        if let Some(obj_path) = marker.get("obj_path").and_then(|v| v.as_str()) {
                            let obj = PathBuf::from(obj_path);
                            let tmp_ext = obj.extension().and_then(|s| s.to_str()).unwrap_or("dae");
                            std::fs::remove_file(obj.with_extension(format!("{tmp_ext}.tmp"))).ok();
                            // Remove half-published files too
                            std::fs::remove_file(&obj).ok();
                        }
                        if let Some(manifest_path) =
                            marker.get("manifest_path").and_then(|v| v.as_str())
                        {
                            let manifest = PathBuf::from(manifest_path);
                            std::fs::remove_file(manifest.with_extension("json.tmp")).ok();
                            std::fs::remove_file(&manifest).ok();
                        }
                    }
                }
                // Remove the marker itself
                std::fs::remove_file(&path).ok();
            }
        }

        Ok(())
    }

    fn manifest_path_for_obj(obj_path: &Path, allowed_root: &Path) -> Result<PathBuf, String> {
        let canonical_root = allowed_root
            .canonicalize()
            .map_err(|e| format!("PATH_NOT_ALLOWED: root canonicalize failed: {}", e))?;
        let parent = obj_path
            .parent()
            .ok_or_else(|| "PATH_NOT_ALLOWED: obj parent missing".to_string())?;
        let canonical_parent = parent
            .canonicalize()
            .map_err(|e| format!("PATH_NOT_ALLOWED: parent canonicalize failed: {}", e))?;
        if !canonical_parent.starts_with(&canonical_root) {
            return Err("PATH_NOT_ALLOWED: manifest path outside allowed root".to_string());
        }
        let stem = obj_path
            .file_stem()
            .ok_or_else(|| "PATH_NOT_ALLOWED: obj filename missing".to_string())?;
        Ok(canonical_parent.join(format!("{}.manifest.json", stem.to_string_lossy())))
    }

    fn hash_document(doc: &Document) -> String {
        format!(
            "blake3:{}",
            blake3::hash(format!("{:?}", doc).as_bytes()).to_hex()
        )
    }

    fn now_rfc3339() -> String {
        chrono::Utc::now().to_rfc3339()
    }
}

/// Compute bounding box from mesh positions (fallback when Solid not available).
fn compute_mesh_bbox(mesh: &vcad_eval::EvaluatedMesh) -> BBox {
    let mut min = [f64::MAX; 3];
    let mut max = [f64::MIN; 3];
    let positions = &mesh.positions;
    for i in (0..positions.len()).step_by(3) {
        for j in 0..3 {
            let v = positions[i + j] as f64;
            min[j] = min[j].min(v);
            max[j] = max[j].max(v);
        }
    }
    if positions.is_empty() {
        min = [0.0; 3];
        max = [0.0; 3];
    }
    BBox { min, max }
}

/// Enforce single-part contract.
fn select_single_part(
    scene: &vcad_eval::EvaluatedScene,
) -> Result<&vcad_eval::EvaluatedPart, EvalError> {
    match scene.parts.len() {
        0 => Err(EvalError::NoGeometry),
        1 => Ok(&scene.parts[0]),
        n => Err(EvalError::MultiPart(n)),
    }
}

/// Structured error type for evaluator operations.
#[derive(Debug)]
pub enum EvalError {
    /// Loon parse/interpret error
    Loon(String),
    /// vcad-eval kernel error
    Kernel(vcad_eval::EvalError),
    /// Scene produced zero parts
    NoGeometry,
    /// Scene produced more than one part
    MultiPart(usize),
    /// Internal error (IO, path, etc.)
    Internal(String),
}

impl EvalError {
    /// Machine-readable error code.
    pub fn error_code(&self) -> &'static str {
        match self {
            EvalError::Loon(_) => "LOON_ERROR",
            EvalError::Kernel(_) => "KERNEL_ERROR",
            EvalError::NoGeometry => "NO_GEOMETRY",
            EvalError::MultiPart(_) => "MULTI_PART_UNSUPPORTED",
            EvalError::Internal(s) if s == "TEMP_SEQ_EXHAUSTED" => "TEMP_SEQ_EXHAUSTED",
            EvalError::Internal(s) if s.starts_with("PATH_NOT_ALLOWED") => "PATH_NOT_ALLOWED",
            EvalError::Internal(_) => "INTERNAL_ERROR",
        }
    }

    /// Structured error details, if available for this error variant.
    pub fn details(&self) -> Option<serde_json::Value> {
        match self {
            EvalError::MultiPart(n) => Some(serde_json::json!({
                "part_count": *n,
            })),
            _ => None,
        }
    }

    /// Human-readable error message.
    pub fn message(&self) -> String {
        match self {
            EvalError::Loon(msg) => format!("Loon evaluation error: {}", msg),
            EvalError::Kernel(e) => format!("Kernel evaluation error: {}", e),
            EvalError::NoGeometry => "Scene produced zero parts".to_string(),
            EvalError::MultiPart(n) => format!("Scene produced {} parts (expected 1)", n),
            EvalError::Internal(msg) => msg.clone(),
        }
    }
}

impl std::fmt::Display for EvalError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.message())
    }
}

impl std::error::Error for EvalError {}

impl From<String> for EvalError {
    fn from(s: String) -> Self {
        EvalError::Internal(s)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sanitize_obj_name() {
        assert_eq!(Evaluator::sanitize_obj_name("hello"), "hello");
        assert_eq!(Evaluator::sanitize_obj_name("my file"), "my_file");
        assert_eq!(Evaluator::sanitize_obj_name("a/b/../c"), "a_b____c");
        assert_eq!(Evaluator::sanitize_obj_name("test-file_1"), "test-file_1");
    }

    #[test]
    fn test_hash_document() {
        let doc = Document::new();
        let hash = Evaluator::hash_document(&doc);
        assert!(hash.starts_with("blake3:"));
        assert!(hash.len() > 10);
    }

    #[test]
    fn test_eval_error_codes() {
        assert_eq!(EvalError::NoGeometry.error_code(), "NO_GEOMETRY");
        assert_eq!(
            EvalError::MultiPart(3).error_code(),
            "MULTI_PART_UNSUPPORTED"
        );
        assert_eq!(
            EvalError::Loon("parse error".into()).error_code(),
            "LOON_ERROR"
        );
        assert_eq!(
            EvalError::Internal("TEMP_SEQ_EXHAUSTED".into()).error_code(),
            "TEMP_SEQ_EXHAUSTED"
        );
        assert_eq!(
            EvalError::Internal("PATH_NOT_ALLOWED: bad path".into()).error_code(),
            "PATH_NOT_ALLOWED"
        );
    }

    #[test]
    fn test_manifest_path_for_obj() {
        let temp = tempfile::tempdir().unwrap();
        let obj_path = temp.path().join("test-00000000000000000001.obj");
        let result = Evaluator::manifest_path_for_obj(&obj_path, temp.path());
        assert!(result.is_ok());
        let manifest_path = result.unwrap();
        assert!(manifest_path
            .to_string_lossy()
            .contains("test-00000000000000000001.manifest.json"));
    }

    #[test]
    fn test_load_retention_seq_empty() {
        let temp = tempfile::tempdir().unwrap();
        assert_eq!(Evaluator::load_retention_seq(temp.path()), 0);
    }

    #[test]
    fn test_load_retention_seq_with_files() {
        let temp = tempfile::tempdir().unwrap();
        std::fs::write(temp.path().join("eval-00000000000000000005.obj"), "dummy").unwrap();
        std::fs::write(temp.path().join("eval-00000000000000000010.obj"), "dummy").unwrap();
        assert_eq!(Evaluator::load_retention_seq(temp.path()), 10);
    }

    #[test]
    fn test_seq_exhausted() {
        let temp = tempfile::tempdir().unwrap();
        let mut evaluator = Evaluator::new(temp.path().to_path_buf(), 3600, 500, 256);
        evaluator.retention.seq = u64::MAX;
        let result = evaluator.next_artifact_path("test", "dae");
        assert!(result.is_err());
        assert!(result.unwrap_err().contains("TEMP_SEQ_EXHAUSTED"));
    }

    #[test]
    fn test_cleanup_respects_max_files() {
        let temp = tempfile::tempdir().unwrap();
        // Create 5 OBJ files
        for i in 1..=5 {
            std::fs::write(temp.path().join(format!("eval-{:020}.obj", i)), "dummy obj").unwrap();
            std::fs::write(
                temp.path().join(format!("eval-{:020}.manifest.json", i)),
                "{}",
            )
            .unwrap();
            // Stagger modification times a bit
            std::thread::sleep(std::time::Duration::from_millis(10));
        }

        let evaluator = Evaluator::new(temp.path().to_path_buf(), 3600, 3, 256);
        evaluator.cleanup_temp_dir();

        // Count remaining OBJ files
        let obj_count = std::fs::read_dir(temp.path())
            .unwrap()
            .flatten()
            .filter(|e| e.path().extension().and_then(|s| s.to_str()) == Some("obj"))
            .count();
        assert!(obj_count <= 3, "Expected <= 3 OBJ files, got {}", obj_count);
    }

    #[test]
    fn test_recovery_cleans_pending_markers() {
        let temp = tempfile::tempdir().unwrap();

        // Create a pending marker with associated tmp files
        let obj_path = temp.path().join("eval-00000000000000000001.obj");
        let manifest_path = temp.path().join("eval-00000000000000000001.manifest.json");

        let marker = serde_json::json!({
            "obj_path": obj_path.to_string_lossy(),
            "manifest_path": manifest_path.to_string_lossy(),
            "created_at": "2025-01-01T00:00:00Z",
        });
        std::fs::write(
            temp.path().join("eval-00000000000000000001.pair.pending"),
            serde_json::to_vec_pretty(&marker).unwrap(),
        )
        .unwrap();
        std::fs::write(obj_path.with_extension("obj.tmp"), "tmp obj").unwrap();
        std::fs::write(manifest_path.with_extension("json.tmp"), "tmp manifest").unwrap();
        // Also create a half-published obj
        std::fs::write(&obj_path, "half published obj").unwrap();

        let _evaluator = Evaluator::new(temp.path().to_path_buf(), 3600, 500, 256);

        // Pending marker should be gone
        assert!(!temp
            .path()
            .join("eval-00000000000000000001.pair.pending")
            .exists());
        // Tmp files should be gone
        assert!(!obj_path.with_extension("obj.tmp").exists());
        assert!(!manifest_path.with_extension("json.tmp").exists());
        // Half-published obj should be gone
        assert!(!obj_path.exists());
    }

    #[test]
    fn test_raw_import_fails_without_preprocessing() {
        // Imports are only supported in .skp.oo files where they are
        // preprocessed by extract_and_rewrite_imports before evaluation.
        // In plain .oo modules (loaded via [use ...]), raw [import ...]
        // reaches the Loon interpreter directly and must fail.
        let temp = tempfile::tempdir().unwrap();
        let mut evaluator = Evaluator::new(temp.path().to_path_buf(), 3600, 500, 256);

        let source = r#"[let cutout [import :solid "entity:12345"]]
[cube 10.0 10.0 10.0]"#;

        let result = evaluator.eval_code(source);
        assert!(result.is_err(), "raw [import ...] must fail during evaluation");
    }

    #[test]
    fn test_no_overwrite_existing_obj_after_restart() {
        let temp = tempfile::tempdir().unwrap();

        // Pre-seed an OBJ file with seq 5
        std::fs::write(
            temp.path().join("eval-00000000000000000005.obj"),
            "existing",
        )
        .unwrap();

        let mut evaluator = Evaluator::new(temp.path().to_path_buf(), 3600, 500, 256);
        // After restart, seq should be >= 5, so next_artifact_path should produce seq > 5
        let path = evaluator.next_artifact_path("eval", "dae").unwrap();
        assert!(
            path.to_string_lossy().contains("00000000000000000006"),
            "Expected seq 6, got: {}",
            path.display()
        );
        // Existing file should still be there
        assert!(temp.path().join("eval-00000000000000000005.obj").exists());
    }
}
