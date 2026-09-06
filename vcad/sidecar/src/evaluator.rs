use crate::adt_cache::AdtCache;
use crate::dae_export::{brep_to_dae, mesh_to_dae};
use crate::imports::{ResolvedImport, build_import_preamble};
use loon_lang::interp::{Env, Value, eval_program_with_env_and_base_dir};
use loon_lang::parser::parse;
use serde::Serialize;
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use vcad_eval::{EvalOptions, evaluate_document};
use vcad_ir::Document;
use vcad_kernel_tessellate::TessellationParams;
use vcad_loon::{VCAD_LIB_SOURCE, value_to_document_in};

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
    pub mesh_path: String,
    pub manifest_path: String,
    pub volume: f64,
    pub surface_area: f64,
    pub bbox: BBox,
    pub is_empty: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub display: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub loaded_module_paths: Option<Vec<String>>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ArtifactManifest {
    pub status: String,
    pub node_id: Option<String>,
    pub revision: Option<u64>,
    pub request_id: Option<String>,
    pub source_file: Option<String>,
    pub source_hash: String,
    pub mesh_path: String,
    pub volume: f64,
    pub surface_area: f64,
    pub bbox: BBox,
    pub queued_at: Option<String>,
    pub started_at: Option<String>,
    pub finished_at: String,
}

#[derive(Debug, Clone, Default, Serialize)]
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

        // Collect all mesh artifact pairs (mesh + manifest)
        let mut mesh_files: Vec<(PathBuf, std::time::SystemTime)> = Vec::new();
        let mut expired: Vec<PathBuf> = Vec::new();

        for entry in entries.flatten() {
            let path = entry.path();
            let ext = path.extension().and_then(|s| s.to_str());

            // Only manage mesh artifacts; manifests follow their mesh file
            if ext != Some("dae") {
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
                mesh_files.push((path, mtime));
            }
        }

        // Remove expired files
        for path in &expired {
            std::fs::remove_file(path).ok();
            let manifest = path.with_extension("manifest.json");
            std::fs::remove_file(manifest).ok();
        }

        // Sort remaining by mtime (oldest first) and trim to max_files
        mesh_files.sort_by_key(|(_, t)| *t);
        while mesh_files.len() > self.retention.max_files {
            if let Some((path, _)) = mesh_files.first() {
                std::fs::remove_file(path).ok();
                let manifest = path.with_extension("manifest.json");
                std::fs::remove_file(manifest).ok();
                mesh_files.remove(0);
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
            if ext != Some("dae") {
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
        let safe_name = Self::sanitize_artifact_name(name);

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

    fn sanitize_artifact_name(name: &str) -> String {
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

    /// Evaluate a Document and return only geometry metadata (no mesh export).
    ///
    /// Used by `eval_with_imports(inspect=true)` to skip tessellation,
    /// DAE export, and disk I/O when only volume/bbox/surface_area are needed.
    fn evaluate_metadata_only(&self, doc: &Document) -> Result<EvalResult, EvalError> {
        let options = EvalOptions {
            skip_clash_detection: true,
            clock: None,
            ..Default::default()
        };
        let scene = evaluate_document(doc, &options).map_err(EvalError::Kernel)?;
        let part = select_single_part(&scene)?;
        let solid = part
            .solid
            .as_ref()
            .ok_or_else(|| EvalError::Internal("No BRep solid produced".to_string()))?;

        let (bb_min, bb_max) = solid.bounding_box();

        Ok(EvalResult {
            mesh_path: String::new(),
            manifest_path: String::new(),
            volume: solid.volume(),
            surface_area: solid.surface_area(),
            bbox: BBox {
                min: bb_min,
                max: bb_max,
            },
            is_empty: solid.is_empty(),
            display: None,
            loaded_module_paths: None,
        })
    }

    /// Unified evaluation entry point with bool flags controlling pipeline steps.
    ///
    /// Pipeline after Loon eval:
    /// - `display`: format result value as display string
    /// - `cache_adt`: cache result ADT in adt_cache (requires node_id)
    /// - `track_modules`: track [use ...] module paths
    /// - `inspect`: compute volume/bbox/surface_area (BRep, no mesh export)
    /// - `export_mesh`: tessellate + DAE export to disk
    ///
    /// BRep conversion is skipped when `!inspect && !export_mesh` (REPL/display path).
    #[allow(clippy::too_many_arguments)]
    pub fn eval_with_imports(
        &mut self,
        transformed_source: &str,
        base_dir: Option<&Path>,
        imports: &HashMap<String, ResolvedImport>,
        node_id: Option<&str>,
        display: bool,
        cache_adt: bool,
        track_modules: bool,
        inspect: bool,
        export_mesh: bool,
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
                        mesh_data
                            .positions
                            .iter()
                            .map(|&v| Value::Float(v))
                            .collect(),
                    );
                    let indices = Value::Vec(
                        mesh_data
                            .indices
                            .iter()
                            .map(|&v| Value::Int(v as i64))
                            .collect(),
                    );
                    let normals =
                        Value::Vec(mesh_data.normals.iter().map(|&v| Value::Float(v)).collect());
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

        // 4. Evaluate Loon
        let (result_value, loaded_paths) =
            eval_program_with_env_and_base_dir(&exprs, &mut env, base_dir, track_modules)
                .map_err(|e| EvalError::Loon(format!("{e}")))?;

        // A. Format display string
        let display_str = if display {
            Some(format!("{}", result_value))
        } else {
            None
        };

        // B. Cache ADT
        if cache_adt && let Some(nid) = node_id {
            self.adt_cache.set(nid, result_value.clone());
        }

        // C. Module tracking paths
        let module_paths = if track_modules {
            Some(
                loaded_paths
                    .iter()
                    .map(|p| p.to_string_lossy().into_owned())
                    .collect(),
            )
        } else {
            None
        };

        // D-F. BRep conversion path. `base_dir` also anchors relative
        // `import-mesh` / `import-step` paths to the source file's directory.
        if export_mesh {
            let doc = value_to_document_in(&result_value, base_dir).map_err(EvalError::Loon)?;
            let mut result = self.evaluate_and_export(&doc, "import-eval")?;
            result.display = display_str;
            result.loaded_module_paths = module_paths;
            Ok(result)
        } else if inspect {
            let doc = value_to_document_in(&result_value, base_dir).map_err(EvalError::Loon)?;
            let mut result = self.evaluate_metadata_only(&doc)?;
            result.display = display_str;
            result.loaded_module_paths = module_paths;
            Ok(result)
        } else {
            // Display-only / REPL path — no BRep conversion
            Ok(EvalResult {
                mesh_path: String::new(),
                manifest_path: String::new(),
                volume: 0.0,
                surface_area: 0.0,
                bbox: BBox::default(),
                is_empty: true,
                display: display_str,
                loaded_module_paths: module_paths,
            })
        }
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
            ..Default::default()
        };
        let scene = evaluate_document(doc, &options).map_err(EvalError::Kernel)?;
        let part = select_single_part(&scene)?;

        // Validate mesh arrays early if we'll need them (no BRep available)
        let has_brep = part.solid.as_ref().and_then(|s| s.brep()).is_some();
        if !has_brep {
            // vcad-eval swallows a missing or unreadable `import-mesh` file and
            // hands back an empty mesh; fail loudly instead of exporting nothing.
            if part.mesh.indices.is_empty() {
                return Err(EvalError::RootFailed(
                    "mesh-backed root produced no triangles (missing or unreadable import file?)"
                        .to_string(),
                ));
            }
            validate_mesh_arrays(&part.mesh.positions, &part.mesh.indices)?;
        }

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

        let (mesh_content, ext) = if let Some(brep) = part.solid.as_ref().and_then(|s| s.brep()) {
            let params = TessellationParams::from_segments(32);
            let dae = brep_to_dae(brep, &params);
            (dae.into_bytes(), "dae")
        } else {
            (
                mesh_to_dae(&part.mesh)
                    .map_err(EvalError::MeshMalformed)?
                    .into_bytes(),
                "dae",
            )
        };
        let mesh_path = self.next_artifact_path(name, ext)?;
        let manifest_path = Self::manifest_path_for_mesh(&mesh_path, &self.temp_dir)?;
        let manifest = ArtifactManifest {
            status: "applied".to_string(),
            node_id: None,
            revision: None,
            request_id: None,
            source_file: None,
            source_hash: Self::hash_document(doc),
            mesh_path: mesh_path.to_string_lossy().into_owned(),
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
            &mesh_path,
            &mesh_content,
            &manifest_path,
            &manifest,
        )
        .map_err(EvalError::Internal)?;

        self.cleanup_temp_dir();

        Ok(EvalResult {
            mesh_path: mesh_path.to_string_lossy().into_owned(),
            manifest_path: manifest_path.to_string_lossy().into_owned(),
            volume,
            surface_area,
            bbox,
            is_empty,
            display: None,
            loaded_module_paths: None,
        })
    }

    fn write_artifact_pair_atomic(
        allowed_root: &Path,
        mesh_path: &Path,
        mesh_content: &[u8],
        manifest_path: &Path,
        manifest: &ArtifactManifest,
    ) -> Result<(), String> {
        let canonical_root = allowed_root
            .canonicalize()
            .map_err(|e| format!("PATH_NOT_ALLOWED: root canonicalize failed: {}", e))?;
        for p in [mesh_path, manifest_path] {
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

        let ext = mesh_path
            .extension()
            .and_then(|s| s.to_str())
            .unwrap_or("dae");
        let mesh_tmp = mesh_path.with_extension(format!("{ext}.tmp"));
        let manifest_tmp = manifest_path.with_extension("json.tmp");
        let pair_marker = mesh_path.with_extension("pair.pending");

        let marker = serde_json::json!({
            "mesh_path": mesh_path.to_string_lossy(),
            "manifest_path": manifest_path.to_string_lossy(),
            "created_at": Self::now_rfc3339(),
        });
        let marker_body = serde_json::to_vec_pretty(&marker)
            .map_err(|e| format!("Pair marker serialize error: {}", e))?;
        std::fs::write(&pair_marker, marker_body)
            .map_err(|e| format!("Pair marker write error: {}", e))?;

        std::fs::write(&mesh_tmp, mesh_content)
            .map_err(|e| format!("Mesh temp write error: {}", e))?;

        let body = serde_json::to_vec_pretty(manifest)
            .map_err(|e| format!("Manifest serialize error: {}", e))?;
        std::fs::write(&manifest_tmp, body)
            .map_err(|e| format!("Manifest temp write error: {}", e))?;

        std::fs::rename(&mesh_tmp, mesh_path)
            .map_err(|e| format!("Mesh publish rename error: {}", e))?;
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
                if let Ok(content) = std::fs::read_to_string(&path)
                    && let Ok(marker) = serde_json::from_str::<serde_json::Value>(&content)
                {
                    // Clean up tmp files referenced in the marker
                    if let Some(mesh_path) = marker.get("mesh_path").and_then(|v| v.as_str()) {
                        let mesh = PathBuf::from(mesh_path);
                        if is_inside_root(&mesh, &self.temp_dir) {
                            let tmp_ext =
                                mesh.extension().and_then(|s| s.to_str()).unwrap_or("dae");
                            std::fs::remove_file(mesh.with_extension(format!("{tmp_ext}.tmp")))
                                .ok();
                            // Remove half-published files too
                            std::fs::remove_file(&mesh).ok();
                        } else {
                            tracing::warn!(
                                "Recovery: skipping mesh path outside temp root: {}",
                                mesh.display()
                            );
                        }
                    }
                    if let Some(manifest_path) =
                        marker.get("manifest_path").and_then(|v| v.as_str())
                    {
                        let manifest = PathBuf::from(manifest_path);
                        if is_inside_root(&manifest, &self.temp_dir) {
                            std::fs::remove_file(manifest.with_extension("json.tmp")).ok();
                            std::fs::remove_file(&manifest).ok();
                        } else {
                            tracing::warn!(
                                "Recovery: skipping manifest path outside temp root: {}",
                                manifest.display()
                            );
                        }
                    }
                }
                // Always remove the marker itself (found inside temp_dir by read_dir)
                std::fs::remove_file(&path).ok();
            }
        }

        Ok(())
    }

    fn manifest_path_for_mesh(mesh_path: &Path, allowed_root: &Path) -> Result<PathBuf, String> {
        let canonical_root = allowed_root
            .canonicalize()
            .map_err(|e| format!("PATH_NOT_ALLOWED: root canonicalize failed: {}", e))?;
        let parent = mesh_path
            .parent()
            .ok_or_else(|| "PATH_NOT_ALLOWED: mesh parent missing".to_string())?;
        let canonical_parent = parent
            .canonicalize()
            .map_err(|e| format!("PATH_NOT_ALLOWED: parent canonicalize failed: {}", e))?;
        if !canonical_parent.starts_with(&canonical_root) {
            return Err("PATH_NOT_ALLOWED: manifest path outside allowed root".to_string());
        }
        let stem = mesh_path
            .file_stem()
            .ok_or_else(|| "PATH_NOT_ALLOWED: mesh filename missing".to_string())?;
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

/// Check if `candidate` path is inside `root` using canonical paths.
///
/// Handles both existing files (full canonicalize) and non-existing files
/// (canonicalize parent + filename comparison).
fn is_inside_root(candidate: &Path, root: &Path) -> bool {
    let Ok(canonical_root) = root.canonicalize() else {
        return false;
    };
    // If the file exists, canonicalize directly
    if let Ok(canonical) = candidate.canonicalize() {
        return canonical.starts_with(&canonical_root);
    }
    // For non-existing files, canonicalize the parent directory
    if let Some(parent) = candidate.parent()
        && let Ok(canonical_parent) = parent.canonicalize()
    {
        return canonical_parent.starts_with(&canonical_root);
    }
    false
}

/// Validate mesh array sizes for stride-3 positions and stride-3 indices (triangles).
fn validate_mesh_arrays(positions: &[f32], indices: &[u32]) -> Result<(), EvalError> {
    if !positions.len().is_multiple_of(3) {
        return Err(EvalError::MeshMalformed(format!(
            "positions array length {} is not a multiple of 3",
            positions.len()
        )));
    }
    if !indices.len().is_multiple_of(3) {
        return Err(EvalError::MeshMalformed(format!(
            "index array length {} is not a multiple of 3",
            indices.len()
        )));
    }
    let vertex_count = positions.len() / 3;
    for (i, &idx) in indices.iter().enumerate() {
        if (idx as usize) >= vertex_count {
            return Err(EvalError::MeshMalformed(format!(
                "index {} at position {} is out of range (vertex count: {})",
                idx, i, vertex_count
            )));
        }
    }
    Ok(())
}

/// Compute bounding box from mesh positions (fallback when Solid not available).
///
/// Caller must validate mesh arrays first (positions.len() % 3 == 0).
fn compute_mesh_bbox(mesh: &vcad_eval::EvaluatedMesh) -> BBox {
    let mut min = [f64::MAX; 3];
    let mut max = [f64::MIN; 3];
    let positions = &mesh.positions;
    for chunk in positions.as_chunks::<3>().0 {
        for j in 0..3 {
            let v = chunk[j] as f64;
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
///
/// `evaluate_document` never fails on a broken root: it records the problem in
/// `scene.failures` and emits an empty part instead. Surface that here so the
/// caller sees the kernel message rather than a generic "no solid" error.
fn select_single_part(
    scene: &vcad_eval::EvaluatedScene,
) -> Result<&vcad_eval::EvaluatedPart, EvalError> {
    if let Some(failure) = scene.failures.first() {
        return Err(EvalError::RootFailed(format!(
            "{}: {}",
            failure.scope, failure.error
        )));
    }
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
    /// Malformed mesh geometry (bad array sizes or out-of-range indices)
    MeshMalformed(String),
    /// A scene root failed inside vcad-eval (recorded in `scene.failures`)
    RootFailed(String),
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
            EvalError::MeshMalformed(_) => "MESH_MALFORMED",
            EvalError::RootFailed(_) => "ROOT_EVAL_FAILED",
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
            EvalError::MeshMalformed(msg) => format!("Malformed mesh geometry: {}", msg),
            EvalError::RootFailed(msg) => format!("Root evaluation failed: {}", msg),
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
    fn test_sanitize_artifact_name() {
        assert_eq!(Evaluator::sanitize_artifact_name("hello"), "hello");
        assert_eq!(Evaluator::sanitize_artifact_name("my file"), "my_file");
        assert_eq!(Evaluator::sanitize_artifact_name("a/b/../c"), "a_b____c");
        assert_eq!(
            Evaluator::sanitize_artifact_name("test-file_1"),
            "test-file_1"
        );
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
            EvalError::RootFailed("root[0]: boom".into()).error_code(),
            "ROOT_EVAL_FAILED"
        );
        assert_eq!(
            EvalError::Internal("PATH_NOT_ALLOWED: bad path".into()).error_code(),
            "PATH_NOT_ALLOWED"
        );
    }

    #[test]
    fn test_manifest_path_for_mesh() {
        let temp = tempfile::tempdir().unwrap();
        let mesh_path = temp.path().join("test-00000000000000000001.dae");
        let result = Evaluator::manifest_path_for_mesh(&mesh_path, temp.path());
        assert!(result.is_ok());
        let manifest_path = result.unwrap();
        assert!(
            manifest_path
                .to_string_lossy()
                .contains("test-00000000000000000001.manifest.json")
        );
    }

    #[test]
    fn test_load_retention_seq_empty() {
        let temp = tempfile::tempdir().unwrap();
        assert_eq!(Evaluator::load_retention_seq(temp.path()), 0);
    }

    #[test]
    fn test_load_retention_seq_with_files() {
        let temp = tempfile::tempdir().unwrap();
        std::fs::write(temp.path().join("eval-00000000000000000005.dae"), "dummy").unwrap();
        std::fs::write(temp.path().join("eval-00000000000000000010.dae"), "dummy").unwrap();
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
        // Create 5 mesh files
        for i in 1..=5 {
            std::fs::write(temp.path().join(format!("eval-{:020}.dae", i)), "dummy dae").unwrap();
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

        // Count remaining mesh files
        let mesh_count = std::fs::read_dir(temp.path())
            .unwrap()
            .flatten()
            .filter(|e| e.path().extension().and_then(|s| s.to_str()) == Some("dae"))
            .count();
        assert!(
            mesh_count <= 3,
            "Expected <= 3 mesh files, got {}",
            mesh_count
        );
    }

    #[test]
    fn test_recovery_cleans_pending_markers() {
        let temp = tempfile::tempdir().unwrap();

        // Create a pending marker with associated tmp files
        let mesh_path = temp.path().join("eval-00000000000000000001.dae");
        let manifest_path = temp.path().join("eval-00000000000000000001.manifest.json");

        let marker = serde_json::json!({
            "mesh_path": mesh_path.to_string_lossy(),
            "manifest_path": manifest_path.to_string_lossy(),
            "created_at": "2025-01-01T00:00:00Z",
        });
        std::fs::write(
            temp.path().join("eval-00000000000000000001.pair.pending"),
            serde_json::to_vec_pretty(&marker).unwrap(),
        )
        .unwrap();
        std::fs::write(mesh_path.with_extension("dae.tmp"), "tmp mesh").unwrap();
        std::fs::write(manifest_path.with_extension("json.tmp"), "tmp manifest").unwrap();
        // Also create a half-published mesh
        std::fs::write(&mesh_path, "half published mesh").unwrap();

        let _evaluator = Evaluator::new(temp.path().to_path_buf(), 3600, 500, 256);

        // Pending marker should be gone
        assert!(
            !temp
                .path()
                .join("eval-00000000000000000001.pair.pending")
                .exists()
        );
        // Tmp files should be gone
        assert!(!mesh_path.with_extension("dae.tmp").exists());
        assert!(!manifest_path.with_extension("json.tmp").exists());
        // Half-published mesh should be gone
        assert!(!mesh_path.exists());
    }

    #[test]
    fn test_raw_import_fails_without_preprocessing() {
        // Imports are only supported in .cmp.oo files where they are
        // preprocessed by extract_and_rewrite_imports before evaluation.
        // In plain .oo modules (loaded via [use ...]), raw [import ...]
        // reaches the Loon interpreter directly and must fail.
        let temp = tempfile::tempdir().unwrap();
        let mut evaluator = Evaluator::new(temp.path().to_path_buf(), 3600, 500, 256);

        let source = r#"[let cutout [import :host "entity:12345" :solid]]
[cube 10.0 10.0 10.0]"#;

        let imports = std::collections::HashMap::new();
        let result = evaluator.eval_with_imports(
            source, None, &imports, None, false, false, false, false, true,
        );
        assert!(
            result.is_err(),
            "raw [import ...] must fail during evaluation"
        );
    }

    /// Minimal ASCII STL: a single 10 mm x 5 mm right triangle in the XY plane.
    /// vcad reads STL in metres (URDF convention) and scales to millimetres.
    const TRIANGLE_STL: &str = "solid tri\n facet normal 0 0 1\n  outer loop\n   vertex 0 0 0\n   vertex 0.01 0 0\n   vertex 0 0.005 0\n  endloop\n endfacet\nendsolid tri\n";

    #[test]
    fn test_relative_import_mesh_resolves_against_base_dir() {
        let temp = tempfile::tempdir().unwrap();
        let project = temp.path().join("project");
        std::fs::create_dir_all(project.join("vendor")).unwrap();
        std::fs::write(project.join("vendor").join("tri.stl"), TRIANGLE_STL).unwrap();

        let mut evaluator = Evaluator::new(temp.path().join("artifacts"), 3600, 500, 256);
        let imports = HashMap::new();
        let source = "[import-mesh \"vendor/tri.stl\"]";

        // With base_dir the relative path resolves against the project directory,
        // the STL loads and the mesh is exported (mesh imports carry no BRep, so
        // the export path with its mesh fallback is the one that applies).
        let result = evaluator
            .eval_with_imports(
                source,
                Some(&project),
                &imports,
                None,
                false,
                false,
                false,
                false,
                true,
            )
            .expect("import-mesh with base_dir should evaluate");
        assert!(!result.is_empty, "mesh import must produce geometry");
        assert!(
            (result.bbox.max[0] - 10.0).abs() < 1e-6 && (result.bbox.max[1] - 5.0).abs() < 1e-6,
            "bbox should span the imported triangle in mm, got {:?}",
            result.bbox
        );
        assert!(
            Path::new(&result.mesh_path).exists(),
            "DAE artifact must be written"
        );

        // Without base_dir the same source resolves against the process cwd,
        // where the file does not exist, so evaluation must not succeed.
        let result = evaluator.eval_with_imports(
            source, None, &imports, None, false, false, false, false, true,
        );
        assert!(
            result.is_err(),
            "without base_dir the relative mesh path must not resolve"
        );
    }

    #[test]
    fn test_is_inside_root() {
        let temp = tempfile::tempdir().unwrap();

        // Existing file inside temp dir
        let inside = temp.path().join("inside.txt");
        std::fs::write(&inside, "test").unwrap();
        assert!(is_inside_root(&inside, temp.path()));

        // Non-existing file in temp dir
        assert!(is_inside_root(
            &temp.path().join("nonexist.txt"),
            temp.path()
        ));

        // Outside path
        let other = tempfile::tempdir().unwrap();
        let outside = other.path().join("outside.txt");
        std::fs::write(&outside, "test").unwrap();
        assert!(!is_inside_root(&outside, temp.path()));

        // Path traversal attempt
        let traversal = temp.path().join("sub").join("..").join("..").join("etc");
        assert!(!is_inside_root(&traversal, temp.path()));
    }

    #[test]
    fn test_recovery_skips_paths_outside_temp() {
        let temp = tempfile::tempdir().unwrap();
        let outside = tempfile::tempdir().unwrap();

        // Create a file outside temp that should NOT be deleted
        let target = outside.path().join("precious.txt");
        std::fs::write(&target, "precious").unwrap();

        // Create a malicious marker pointing outside temp
        let marker = serde_json::json!({
            "mesh_path": target.to_string_lossy(),
            "manifest_path": target.to_string_lossy(),
            "created_at": "2025-01-01T00:00:00Z",
        });
        std::fs::write(
            temp.path().join("evil.pair.pending"),
            serde_json::to_vec_pretty(&marker).unwrap(),
        )
        .unwrap();

        let _evaluator = Evaluator::new(temp.path().to_path_buf(), 3600, 500, 256);

        // Marker should be gone
        assert!(!temp.path().join("evil.pair.pending").exists());
        // Target outside temp should still exist
        assert!(target.exists(), "File outside temp root was deleted!");
    }

    #[test]
    fn test_validate_mesh_arrays_valid() {
        // Valid mesh
        assert!(validate_mesh_arrays(&[0.0, 1.0, 2.0, 3.0, 4.0, 5.0], &[0, 1, 0]).is_ok());

        // Empty mesh
        assert!(validate_mesh_arrays(&[], &[]).is_ok());
    }

    #[test]
    fn test_validate_mesh_arrays_bad_positions() {
        let err = validate_mesh_arrays(&[0.0, 1.0], &[]).unwrap_err();
        assert_eq!(err.error_code(), "MESH_MALFORMED");
    }

    #[test]
    fn test_validate_mesh_arrays_bad_indices() {
        let err = validate_mesh_arrays(&[0.0, 1.0, 2.0], &[0, 0]).unwrap_err();
        assert_eq!(err.error_code(), "MESH_MALFORMED");
    }

    #[test]
    fn test_validate_mesh_arrays_index_out_of_range() {
        let err = validate_mesh_arrays(&[0.0, 1.0, 2.0], &[0, 0, 5]).unwrap_err();
        assert_eq!(err.error_code(), "MESH_MALFORMED");
    }

    #[test]
    fn test_mesh_malformed_error_code() {
        let err = EvalError::MeshMalformed("test".into());
        assert_eq!(err.error_code(), "MESH_MALFORMED");
        assert!(err.message().contains("Malformed mesh geometry"));
    }

    #[test]
    fn test_no_overwrite_existing_mesh_after_restart() {
        let temp = tempfile::tempdir().unwrap();

        // Pre-seed a mesh file with seq 5
        std::fs::write(
            temp.path().join("eval-00000000000000000005.dae"),
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
        assert!(temp.path().join("eval-00000000000000000005.dae").exists());
    }
}
