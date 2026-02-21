use serde::Serialize;
use std::io::BufRead;

/// Triangle mesh data sent to the frontend via IPC.
#[derive(Debug, Clone, Serialize)]
pub struct MeshData {
    pub id: String,
    pub positions: Vec<f32>,
    pub indices: Vec<u32>,
    pub normals: Vec<f32>,
    pub material: MeshMaterial,
}

/// PBR material properties.
#[derive(Debug, Clone, Serialize)]
pub struct MeshMaterial {
    pub color: [f32; 3],
    pub metallic: f32,
    pub roughness: f32,
}

/// Parse a Wavefront OBJ file into flat arrays.
///
/// Supports:
/// - `v x y z` — vertex positions
/// - `vn nx ny nz` — vertex normals
/// - `f v1 v2 v3` — face with position indices only
/// - `f v1//n1 v2//n2 v3//n3` — face with position and normal indices
/// - `f v1/t1/n1 v2/t2/n2 v3/t3/n3` — face with position, texcoord, and normal indices
type ObjResult = (Vec<f32>, Vec<u32>, Vec<f32>);

pub fn parse_obj(content: &str) -> Result<ObjResult, String> {
    let mut positions: Vec<[f32; 3]> = Vec::new();
    let mut normals: Vec<[f32; 3]> = Vec::new();

    let mut out_positions: Vec<f32> = Vec::new();
    let mut out_normals: Vec<f32> = Vec::new();
    let mut out_indices: Vec<u32> = Vec::new();

    let mut vertex_map: std::collections::HashMap<(usize, Option<usize>), u32> =
        std::collections::HashMap::new();

    for line in content.as_bytes().lines() {
        let line = line.map_err(|e| format!("Read error: {e}"))?;
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }

        if let Some(rest) = line.strip_prefix("v ") {
            let coords = parse_floats(rest, 3)?;
            positions.push([coords[0], coords[1], coords[2]]);
        } else if let Some(rest) = line.strip_prefix("vn ") {
            let coords = parse_floats(rest, 3)?;
            normals.push([coords[0], coords[1], coords[2]]);
        } else if let Some(rest) = line.strip_prefix("f ") {
            let face_verts = parse_face(rest)?;
            if face_verts.len() < 3 {
                return Err("Face with fewer than 3 vertices".to_string());
            }
            // Triangulate (fan from first vertex)
            let first = face_verts[0];
            for i in 1..face_verts.len() - 1 {
                let tri = [first, face_verts[i], face_verts[i + 1]];
                for (vi, ni) in tri {
                    let key = (vi, ni);
                    let idx = if let Some(&existing) = vertex_map.get(&key) {
                        existing
                    } else {
                        let idx = (out_positions.len() / 3) as u32;
                        if vi >= positions.len() {
                            return Err(format!(
                                "Vertex index {} out of range (have {})",
                                vi + 1,
                                positions.len()
                            ));
                        }
                        let p = positions[vi];
                        out_positions.extend_from_slice(&p);
                        if let Some(ni) = ni {
                            if ni < normals.len() {
                                let n = normals[ni];
                                out_normals.extend_from_slice(&n);
                            }
                        }
                        vertex_map.insert(key, idx);
                        idx
                    };
                    out_indices.push(idx);
                }
            }
        }
    }

    // Drop normals if count doesn't match positions
    if !out_normals.is_empty() && out_normals.len() != out_positions.len() {
        out_normals.clear();
    }

    Ok((out_positions, out_indices, out_normals))
}

fn parse_face(s: &str) -> Result<Vec<(usize, Option<usize>)>, String> {
    s.split_whitespace()
        .map(|token| {
            let parts: Vec<&str> = token.split('/').collect();
            let vi: usize = parts[0]
                .parse::<usize>()
                .map_err(|e| format!("Bad vertex index '{token}': {e}"))?
                .checked_sub(1)
                .ok_or_else(|| "Vertex index 0 invalid (OBJ is 1-based)".to_string())?;
            let ni = if parts.len() >= 3 && !parts[2].is_empty() {
                Some(
                    parts[2]
                        .parse::<usize>()
                        .map_err(|e| format!("Bad normal index '{token}': {e}"))?
                        .checked_sub(1)
                        .ok_or_else(|| "Normal index 0 invalid (OBJ is 1-based)".to_string())?,
                )
            } else {
                None
            };
            Ok((vi, ni))
        })
        .collect()
}

fn parse_floats(s: &str, count: usize) -> Result<Vec<f32>, String> {
    let vals: Vec<f32> = s
        .split_whitespace()
        .filter_map(|t| t.parse::<f32>().ok())
        .collect();
    if vals.len() < count {
        return Err(format!("Expected {count} floats, got {}", vals.len()));
    }
    Ok(vals)
}

#[tauri::command]
fn load_mesh(path: String) -> Result<MeshData, String> {
    let content = std::fs::read_to_string(&path)
        .map_err(|e| format!("Failed to read '{}': {}", path, e))?;

    let (positions, indices, normals) = parse_obj(&content)?;

    let file_name = std::path::Path::new(&path)
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("mesh")
        .to_string();

    Ok(MeshData {
        id: file_name,
        positions,
        indices,
        normals,
        material: MeshMaterial {
            color: [0.55, 0.55, 0.55],
            metallic: 0.0,
            roughness: 0.7,
        },
    })
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![load_mesh])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[cfg(test)]
mod tests {
    use crate::{parse_obj, MeshData, MeshMaterial};

    #[test]
    fn test_parse_obj_simple_triangle() {
        let obj = "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n";
        let (positions, indices, normals) = parse_obj(obj).unwrap();
        assert_eq!(
            positions,
            vec![0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        );
        assert_eq!(indices, vec![0, 1, 2]);
        assert!(normals.is_empty());
    }

    #[test]
    fn test_parse_obj_with_normals() {
        let obj = "\
            v 0 0 0\nv 1 0 0\nv 0 1 0\n\
            vn 0 0 1\nvn 0 0 1\nvn 0 0 1\n\
            f 1//1 2//2 3//3\n";
        let (positions, indices, normals) = parse_obj(obj).unwrap();
        assert_eq!(positions.len(), 9);
        assert_eq!(indices, vec![0, 1, 2]);
        assert_eq!(
            normals,
            vec![0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0]
        );
    }

    #[test]
    fn test_parse_obj_quad_triangulation() {
        let obj = "v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nf 1 2 3 4\n";
        let (_, indices, _) = parse_obj(obj).unwrap();
        assert_eq!(indices.len(), 6);
    }

    #[test]
    fn test_parse_obj_with_texcoords() {
        let obj = "v 0 0 0\nv 1 0 0\nv 0 1 0\nvn 0 0 1\nf 1/1/1 2/1/1 3/1/1\n";
        let (positions, indices, normals) = parse_obj(obj).unwrap();
        assert_eq!(positions.len(), 9);
        assert_eq!(indices, vec![0, 1, 2]);
        assert_eq!(normals.len(), 9);
    }

    #[test]
    fn test_parse_obj_empty() {
        let obj = "# comment\n\n";
        let (positions, indices, normals) = parse_obj(obj).unwrap();
        assert!(positions.is_empty());
        assert!(indices.is_empty());
        assert!(normals.is_empty());
    }

    #[test]
    fn test_load_mesh_constructs_mesh_data() {
        // Test that parse_obj + MeshData construction works correctly
        let obj = "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n";
        let (positions, indices, normals) = parse_obj(obj).unwrap();
        let mesh = MeshData {
            id: "test".to_string(),
            positions,
            indices,
            normals,
            material: MeshMaterial {
                color: [0.55, 0.55, 0.55],
                metallic: 0.0,
                roughness: 0.7,
            },
        };
        assert_eq!(mesh.id, "test");
        assert_eq!(mesh.positions.len(), 9);
        assert_eq!(mesh.indices.len(), 3);
    }
}
