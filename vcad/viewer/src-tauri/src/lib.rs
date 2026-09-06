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

/// Parsed mesh: (positions, indices, normals) as flat arrays.
type ObjResult = (Vec<f32>, Vec<u32>, Vec<f32>);

/// Parse a Wavefront OBJ file into flat arrays.
///
/// Supports:
/// - `v x y z` — vertex positions
/// - `vn nx ny nz` — vertex normals
/// - `f v1 v2 v3` — face with position indices only
/// - `f v1//n1 v2//n2 v3//n3` — face with position and normal indices
/// - `f v1/t1/n1 v2/t2/n2 v3/t3/n3` — face with position, texcoord, and normal indices
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
                        if let Some(ni) = ni
                            && ni < normals.len()
                        {
                            let n = normals[ni];
                            out_normals.extend_from_slice(&n);
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

/// Parse a COLLADA DAE file (as produced by the VCAD sidecar) into flat arrays.
///
/// The sidecar emits a predictable DAE structure with fixed IDs:
/// - `mesh0-positions-array` float_array with vertex positions
/// - `<polylist>` with `<vcount>` and `<p>` elements
///
/// Polygons are triangulated using fan method (same as OBJ parser).
/// No XML library needed — simple string search on the predictable format.
pub fn parse_dae(content: &str) -> Result<ObjResult, String> {
    // Extract positions from float_array
    let positions = extract_dae_float_array(content, "mesh0-positions-array")?;

    // Extract vcount and p from polylist
    let vcount = extract_dae_int_array(content, "vcount")?;
    let p_indices = extract_dae_int_array(content, "p")?;

    // Handle empty mesh
    if positions.is_empty() || vcount.is_empty() {
        return Ok((Vec::new(), Vec::new(), Vec::new()));
    }

    let num_vertices = positions.len() / 3;

    // Validate: sum of vcount == len of p
    let expected_indices: usize = vcount.iter().sum();
    if expected_indices != p_indices.len() {
        return Err(format!(
            "DAE polylist mismatch: sum(vcount)={} but p has {} indices",
            expected_indices,
            p_indices.len()
        ));
    }

    // Triangulate polygons and build output arrays
    let mut out_positions: Vec<f32> = Vec::new();
    let mut out_indices: Vec<u32> = Vec::new();
    let mut vertex_map: std::collections::HashMap<usize, u32> = std::collections::HashMap::new();

    let mut p_offset = 0usize;
    for &vc in &vcount {
        if vc < 3 {
            return Err(format!("DAE polygon with fewer than 3 vertices: {vc}"));
        }

        // Collect vertex indices for this polygon
        let face_indices: Vec<usize> = p_indices[p_offset..p_offset + vc].to_vec();
        p_offset += vc;

        // Fan triangulation from first vertex
        let first = face_indices[0];
        for i in 1..face_indices.len() - 1 {
            let tri = [first, face_indices[i], face_indices[i + 1]];
            for vi in tri {
                let idx = if let Some(&existing) = vertex_map.get(&vi) {
                    existing
                } else {
                    if vi >= num_vertices {
                        return Err(format!(
                            "DAE vertex index {} out of range (have {})",
                            vi, num_vertices
                        ));
                    }
                    let idx = (out_positions.len() / 3) as u32;
                    out_positions.push(positions[vi * 3]);
                    out_positions.push(positions[vi * 3 + 1]);
                    out_positions.push(positions[vi * 3 + 2]);
                    vertex_map.insert(vi, idx);
                    idx
                };
                out_indices.push(idx);
            }
        }
    }

    // DAE from sidecar has no per-vertex normals — return empty
    Ok((out_positions, out_indices, Vec::new()))
}

/// Extract float values from a `<float_array id="ID" count="N">...</float_array>` element.
fn extract_dae_float_array(content: &str, id: &str) -> Result<Vec<f32>, String> {
    let tag_start = format!("<float_array id=\"{id}\"");
    let start = match content.find(&tag_start) {
        Some(pos) => pos,
        None => return Err(format!("DAE: <float_array id=\"{id}\"> not found")),
    };

    // Find the closing > of the opening tag
    let data_start = match content[start..].find('>') {
        Some(pos) => start + pos + 1,
        None => return Err("DAE: malformed float_array opening tag".to_string()),
    };

    // Find closing </float_array>
    let data_end = match content[data_start..].find("</float_array>") {
        Some(pos) => data_start + pos,
        None => return Err("DAE: missing </float_array>".to_string()),
    };

    let text = content[data_start..data_end].trim();
    if text.is_empty() {
        return Ok(Vec::new());
    }

    text.split_whitespace()
        .map(|t| {
            t.parse::<f32>()
                .map_err(|e| format!("DAE: bad float '{t}': {e}"))
        })
        .collect()
}

/// Extract integer values from a `<TAG>...</TAG>` element inside `<polylist>`.
fn extract_dae_int_array(content: &str, tag: &str) -> Result<Vec<usize>, String> {
    // Find within polylist context
    let polylist_start = match content.find("<polylist") {
        Some(pos) => pos,
        None => return Err("DAE: <polylist> not found".to_string()),
    };
    let polylist_content = &content[polylist_start..];

    let open_tag = format!("<{tag}>");
    let close_tag = format!("</{tag}>");

    let start = match polylist_content.find(&open_tag) {
        Some(pos) => pos + open_tag.len(),
        None => return Err(format!("DAE: <{tag}> not found in polylist")),
    };

    let end = match polylist_content[start..].find(&close_tag) {
        Some(pos) => start + pos,
        None => return Err(format!("DAE: </{tag}> not found")),
    };

    let text = polylist_content[start..end].trim();
    if text.is_empty() {
        return Ok(Vec::new());
    }

    text.split_whitespace()
        .map(|t| {
            t.parse::<usize>()
                .map_err(|e| format!("DAE: bad integer '{t}': {e}"))
        })
        .collect()
}

#[tauri::command]
fn load_mesh(path: String) -> Result<MeshData, String> {
    let content =
        std::fs::read_to_string(&path).map_err(|e| format!("Failed to read '{}': {}", path, e))?;

    let is_dae = path.ends_with(".dae");
    let (positions, indices, normals) = if is_dae {
        parse_dae(&content)?
    } else {
        parse_obj(&content)?
    };

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
    use crate::{MeshData, MeshMaterial, parse_dae, parse_obj};

    #[test]
    fn test_parse_obj_simple_triangle() {
        let obj = "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n";
        let (positions, indices, normals) = parse_obj(obj).unwrap();
        assert_eq!(positions, vec![0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0]);
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
        assert_eq!(normals, vec![0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0]);
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

    // --- DAE parser tests ---

    const DAE_TRIANGLE: &str = r##"<?xml version="1.0" encoding="utf-8"?>
<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1">
  <asset><unit name="millimeter" meter="0.001"/><up_axis>Z_UP</up_axis></asset>
  <library_geometries>
    <geometry id="mesh0" name="mesh">
      <mesh>
        <source id="mesh0-positions">
          <float_array id="mesh0-positions-array" count="9">0 0 0 1 0 0 0 1 0</float_array>
          <technique_common>
            <accessor source="#mesh0-positions-array" count="3" stride="3">
              <param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/>
            </accessor>
          </technique_common>
        </source>
        <vertices id="mesh0-vertices">
          <input semantic="POSITION" source="#mesh0-positions"/>
        </vertices>
        <polylist count="1">
          <input semantic="VERTEX" source="#mesh0-vertices" offset="0"/>
          <vcount>3</vcount>
          <p>0 1 2</p>
        </polylist>
      </mesh>
    </geometry>
  </library_geometries>
  <library_visual_scenes>
    <visual_scene id="Scene" name="Scene">
      <node id="Node" type="NODE"><instance_geometry url="#mesh0"/></node>
    </visual_scene>
  </library_visual_scenes>
  <scene><instance_visual_scene url="#Scene"/></scene>
</COLLADA>"##;

    #[test]
    fn test_parse_dae_triangle() {
        let (positions, indices, normals) = parse_dae(DAE_TRIANGLE).unwrap();
        assert_eq!(positions, vec![0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0]);
        assert_eq!(indices, vec![0, 1, 2]);
        assert!(normals.is_empty());
    }

    #[test]
    fn test_parse_dae_quad_triangulation() {
        let dae = r##"<?xml version="1.0" encoding="utf-8"?>
<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1">
  <asset><unit name="millimeter" meter="0.001"/><up_axis>Z_UP</up_axis></asset>
  <library_geometries>
    <geometry id="mesh0" name="mesh">
      <mesh>
        <source id="mesh0-positions">
          <float_array id="mesh0-positions-array" count="12">0 0 0 1 0 0 1 1 0 0 1 0</float_array>
          <technique_common>
            <accessor source="#mesh0-positions-array" count="4" stride="3">
              <param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/>
            </accessor>
          </technique_common>
        </source>
        <vertices id="mesh0-vertices">
          <input semantic="POSITION" source="#mesh0-positions"/>
        </vertices>
        <polylist count="1">
          <input semantic="VERTEX" source="#mesh0-vertices" offset="0"/>
          <vcount>4</vcount>
          <p>0 1 2 3</p>
        </polylist>
      </mesh>
    </geometry>
  </library_geometries>
  <library_visual_scenes>
    <visual_scene id="Scene" name="Scene">
      <node id="Node" type="NODE"><instance_geometry url="#mesh0"/></node>
    </visual_scene>
  </library_visual_scenes>
  <scene><instance_visual_scene url="#Scene"/></scene>
</COLLADA>"##;
        let (positions, indices, _) = parse_dae(dae).unwrap();
        // Quad → 2 triangles = 6 indices
        assert_eq!(indices.len(), 6);
        assert_eq!(positions.len(), 12); // 4 vertices × 3
    }

    #[test]
    fn test_parse_dae_empty() {
        let dae = r##"<?xml version="1.0" encoding="utf-8"?>
<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1">
  <asset><unit name="millimeter" meter="0.001"/><up_axis>Z_UP</up_axis></asset>
  <library_geometries>
    <geometry id="mesh0" name="mesh">
      <mesh>
        <source id="mesh0-positions">
          <float_array id="mesh0-positions-array" count="0"></float_array>
          <technique_common>
            <accessor source="#mesh0-positions-array" count="0" stride="3">
              <param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/>
            </accessor>
          </technique_common>
        </source>
        <vertices id="mesh0-vertices">
          <input semantic="POSITION" source="#mesh0-positions"/>
        </vertices>
        <polylist count="0">
          <input semantic="VERTEX" source="#mesh0-vertices" offset="0"/>
          <vcount></vcount>
          <p></p>
        </polylist>
      </mesh>
    </geometry>
  </library_geometries>
  <library_visual_scenes>
    <visual_scene id="Scene" name="Scene">
      <node id="Node" type="NODE"><instance_geometry url="#mesh0"/></node>
    </visual_scene>
  </library_visual_scenes>
  <scene><instance_visual_scene url="#Scene"/></scene>
</COLLADA>"##;
        let (positions, indices, normals) = parse_dae(dae).unwrap();
        assert!(positions.is_empty());
        assert!(indices.is_empty());
        assert!(normals.is_empty());
    }
}
