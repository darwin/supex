use std::fmt::Write;
use vcad_eval::EvaluatedMesh;
use vcad_kernel_geom::{GeometryStore, SurfaceKind};
use vcad_kernel_math::{Point2, Vec3};
use vcad_kernel_primitives::BRepSolid;
use vcad_kernel_tessellate::{TessellationParams, tessellate_face};
use vcad_kernel_topo::{Orientation, Topology};

/// Convert a BRep solid to COLLADA (.dae) XML text.
///
/// Planar faces without holes are emitted as native n-gon polygons with f64
/// precision. Curved faces and planar faces with holes are tessellated into
/// triangles via `tessellate_face` (f32 precision, converted to f64 for output).
pub fn brep_to_dae(brep: &BRepSolid, params: &TessellationParams) -> String {
    let solid = &brep.topology.solids[brep.solid_id];
    let shell = &brep.topology.shells[solid.outer_shell];

    let mut all_positions: Vec<f64> = Vec::new();
    let mut all_vcount: Vec<usize> = Vec::new();
    let mut all_indices: Vec<usize> = Vec::new();

    for &face_id in &shell.faces {
        let face = &brep.topology.faces[face_id];
        let surface = &brep.geometry.surfaces[face.surface_index];
        let is_plane = surface.surface_type() == SurfaceKind::Plane;
        let has_holes = !face.inner_loops.is_empty();

        // Planar faces without holes that have a proper polygon boundary
        // (>= 3 loop vertices) can be emitted as native COLLADA polygons.
        // Faces with circular boundaries (e.g. cylinder caps with 1 vertex)
        // fall through to tessellation.
        let loop_verts = brep.topology.loop_vertices(face.outer_loop).len();

        if is_plane && !has_holes && loop_verts >= 3 {
            emit_planar_polygon(
                &brep.topology,
                &brep.geometry,
                face_id,
                &mut all_positions,
                &mut all_vcount,
                &mut all_indices,
            );
        } else {
            emit_tessellated_triangles(
                &brep.topology,
                &brep.geometry,
                face_id,
                params,
                &mut all_positions,
                &mut all_vcount,
                &mut all_indices,
            );
        }
    }

    build_collada_xml(&all_positions, &all_vcount, &all_indices)
}

/// Emit a planar face (no holes) as a single n-gon polygon with f64 vertices.
fn emit_planar_polygon(
    topo: &Topology,
    geom: &GeometryStore,
    face_id: vcad_kernel_topo::FaceId,
    positions: &mut Vec<f64>,
    vcount: &mut Vec<usize>,
    indices: &mut Vec<usize>,
) {
    let face = &topo.faces[face_id];
    let surface = &geom.surfaces[face.surface_index];
    let reversed = face.orientation == Orientation::Reversed;

    let outer_verts: Vec<_> = topo
        .loop_half_edges(face.outer_loop)
        .map(|he| topo.vertices[topo.half_edges[he].origin].point)
        .collect();

    if outer_verts.len() < 3 {
        return;
    }

    // Winding detection — same logic as tessellate_planar_face_with_geom
    let surface_normal = surface.normal(Point2::new(0.0, 0.0));
    let expected_normal = if reversed {
        -surface_normal
    } else {
        surface_normal
    };

    let mut geom_normal = Vec3::zeros();
    for i in 0..outer_verts.len() {
        let curr = outer_verts[i];
        let next = outer_verts[(i + 1) % outer_verts.len()];
        geom_normal.x += (curr.y - next.y) * (curr.z + next.z);
        geom_normal.y += (curr.z - next.z) * (curr.x + next.x);
        geom_normal.z += (curr.x - next.x) * (curr.y + next.y);
    }

    let dot = geom_normal.dot(expected_normal);
    let winding_matches = dot > 0.0;
    let need_flip = !winding_matches;

    let base_idx = positions.len() / 3;
    let n = outer_verts.len();

    // Append vertex positions (f64)
    for v in &outer_verts {
        positions.push(v.x);
        positions.push(v.y);
        positions.push(v.z);
    }

    // Append polygon
    vcount.push(n);
    if need_flip {
        for i in (0..n).rev() {
            indices.push(base_idx + i);
        }
    } else {
        for i in 0..n {
            indices.push(base_idx + i);
        }
    }
}

/// Emit a face (curved or with holes) as tessellated triangles.
fn emit_tessellated_triangles(
    topo: &Topology,
    geom: &GeometryStore,
    face_id: vcad_kernel_topo::FaceId,
    params: &TessellationParams,
    positions: &mut Vec<f64>,
    vcount: &mut Vec<usize>,
    indices: &mut Vec<usize>,
) {
    let mesh = tessellate_face(topo, geom, face_id, params);
    if mesh.indices.is_empty() {
        return;
    }

    let base_idx = positions.len() / 3;

    // Convert f32 vertices to f64 for consistent XML output
    for chunk in mesh.vertices.as_chunks::<3>().0 {
        positions.push(chunk[0] as f64);
        positions.push(chunk[1] as f64);
        positions.push(chunk[2] as f64);
    }

    // Each triangle is a polygon with vcount=3
    for tri in mesh.indices.as_chunks::<3>().0 {
        vcount.push(3);
        indices.push(base_idx + tri[0] as usize);
        indices.push(base_idx + tri[1] as usize);
        indices.push(base_idx + tri[2] as usize);
    }
}

/// Convert an EvaluatedMesh (triangulated, f32) to COLLADA (.dae) XML text.
///
/// Each triangle is emitted as a polylist entry with vcount=3. Vertex positions
/// are promoted from f32 to f64 for consistent XML output.
///
/// Returns an error if mesh arrays have invalid sizes or out-of-range indices.
pub fn mesh_to_dae(mesh: &EvaluatedMesh) -> Result<String, String> {
    if !mesh.positions.len().is_multiple_of(3) {
        return Err(format!(
            "positions array length {} is not a multiple of 3",
            mesh.positions.len()
        ));
    }
    if !mesh.indices.len().is_multiple_of(3) {
        return Err(format!(
            "index array length {} is not a multiple of 3",
            mesh.indices.len()
        ));
    }
    let vertex_count = mesh.positions.len() / 3;
    for (i, &idx) in mesh.indices.iter().enumerate() {
        if (idx as usize) >= vertex_count {
            return Err(format!(
                "index {} at position {} is out of range (vertex count: {})",
                idx, i, vertex_count
            ));
        }
    }

    let mut positions: Vec<f64> = Vec::with_capacity(mesh.positions.len());
    let mut vcount: Vec<usize> = Vec::new();
    let mut indices: Vec<usize> = Vec::new();

    for &p in &mesh.positions {
        positions.push(p as f64);
    }

    for tri in mesh.indices.as_chunks::<3>().0 {
        vcount.push(3);
        indices.push(tri[0] as usize);
        indices.push(tri[1] as usize);
        indices.push(tri[2] as usize);
    }

    Ok(build_collada_xml(&positions, &vcount, &indices))
}

/// Build the complete COLLADA XML document.
fn build_collada_xml(positions: &[f64], vcount: &[usize], indices: &[usize]) -> String {
    let num_verts = positions.len() / 3;
    let num_faces = vcount.len();
    let num_floats = positions.len();

    // Pre-allocate: rough estimate
    let mut xml = String::with_capacity(num_floats * 24 + indices.len() * 8 + 1024);

    xml.push_str(
        r##"<?xml version="1.0" encoding="utf-8"?>
<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1">
  <asset>
    <unit name="millimeter" meter="0.001"/>
    <up_axis>Z_UP</up_axis>
  </asset>
  <library_geometries>
    <geometry id="mesh0" name="mesh">
      <mesh>
        <source id="mesh0-positions">
"##,
    );

    // float_array
    write!(
        xml,
        "          <float_array id=\"mesh0-positions-array\" count=\"{}\">",
        num_floats
    )
    .unwrap();
    for (i, &v) in positions.iter().enumerate() {
        if i > 0 {
            xml.push(' ');
        }
        // Use Display formatting which preserves f64 precision
        write!(xml, "{}", v).unwrap();
    }
    xml.push_str("</float_array>\n");

    // accessor
    write!(
        xml,
        r##"          <technique_common>
            <accessor source="#mesh0-positions-array" count="{}" stride="3">
              <param name="X" type="float"/>
              <param name="Y" type="float"/>
              <param name="Z" type="float"/>
            </accessor>
          </technique_common>
"##,
        num_verts
    )
    .unwrap();

    xml.push_str(
        r##"        </source>
        <vertices id="mesh0-vertices">
          <input semantic="POSITION" source="#mesh0-positions"/>
        </vertices>
"##,
    );

    // polylist
    writeln!(xml, "        <polylist count=\"{}\">", num_faces).unwrap();
    xml.push_str(
        "          <input semantic=\"VERTEX\" source=\"#mesh0-vertices\" offset=\"0\"/>\n",
    );

    // vcount
    xml.push_str("          <vcount>");
    for (i, &vc) in vcount.iter().enumerate() {
        if i > 0 {
            xml.push(' ');
        }
        write!(xml, "{}", vc).unwrap();
    }
    xml.push_str("</vcount>\n");

    // p (indices)
    xml.push_str("          <p>");
    for (i, &idx) in indices.iter().enumerate() {
        if i > 0 {
            xml.push(' ');
        }
        write!(xml, "{}", idx).unwrap();
    }
    xml.push_str("</p>\n");

    xml.push_str(
        r##"        </polylist>
      </mesh>
    </geometry>
  </library_geometries>
  <library_visual_scenes>
    <visual_scene id="Scene" name="Scene">
      <node id="Node" type="NODE">
        <instance_geometry url="#mesh0"/>
      </node>
    </visual_scene>
  </library_visual_scenes>
  <scene>
    <instance_visual_scene url="#Scene"/>
  </scene>
</COLLADA>
"##,
    );

    xml
}

#[cfg(test)]
mod tests {
    use super::*;
    use vcad_kernel_primitives::{make_cube, make_cylinder, make_torus, make_wedge};

    /// Vertex counts of every polygon in the `<polylist>`.
    fn polygon_vcounts(dae: &str) -> Vec<usize> {
        let start = dae.find("<vcount>").unwrap() + "<vcount>".len();
        let end = dae.find("</vcount>").unwrap();
        dae[start..end]
            .split_whitespace()
            .map(|s| s.parse().unwrap())
            .collect()
    }

    #[test]
    fn test_cube_all_polygons() {
        let brep = make_cube(10.0, 20.0, 30.0);
        let params = TessellationParams::from_segments(32);
        let dae = brep_to_dae(&brep, &params);

        // Basic XML structure
        assert!(dae.starts_with("<?xml"));
        assert!(dae.contains("<COLLADA"));
        assert!(dae.contains("</COLLADA>"));
        assert!(dae.contains("<polylist"));

        // A cube has 6 faces, all planar — should be 6 polygons
        assert!(dae.contains("count=\"6\""));

        // All faces are quads (4 vertices each)
        let vcount_start = dae.find("<vcount>").unwrap() + "<vcount>".len();
        let vcount_end = dae.find("</vcount>").unwrap();
        let vcount_str = &dae[vcount_start..vcount_end];
        let vcounts: Vec<&str> = vcount_str.split_whitespace().collect();
        assert_eq!(vcounts.len(), 6, "Cube should have 6 polygons");
        for vc in &vcounts {
            assert_eq!(*vc, "4", "Each cube face should be a quad");
        }

        // Verify f64 precision: cube vertices should be exact (10.0, 20.0, 30.0)
        assert!(dae.contains("10"));
        assert!(dae.contains("20"));
        assert!(dae.contains("30"));
    }

    #[test]
    fn test_cylinder_all_tessellated() {
        // Cylinder B-rep has circular boundaries (1-vertex loops) on caps,
        // so all 3 faces (lateral + 2 caps) go through tessellation.
        let brep = make_cylinder(5.0, 20.0, 16);
        let params = TessellationParams::from_segments(16);
        let dae = brep_to_dae(&brep, &params);

        assert!(dae.starts_with("<?xml"));
        assert!(dae.contains("<polylist"));

        let vcount_start = dae.find("<vcount>").unwrap() + "<vcount>".len();
        let vcount_end = dae.find("</vcount>").unwrap();
        let vcount_str = &dae[vcount_start..vcount_end];
        let vcounts: Vec<usize> = vcount_str
            .split_whitespace()
            .map(|s| s.parse().unwrap())
            .collect();

        // All faces tessellated into triangles
        let triangle_count = vcounts.iter().filter(|&&v| v == 3).count();
        assert!(
            triangle_count > 0,
            "Cylinder should have tessellated triangles"
        );
        assert!(
            vcounts.len() > 3,
            "Cylinder should have multiple faces from tessellation, got {}",
            vcounts.len()
        );
    }

    #[test]
    fn test_wedge_all_polygons() {
        // A wedge is bounded by planar faces only: 2 triangular caps + 3 quads,
        // so every face is emitted as one polygon without tessellation.
        let brep = make_wedge(10.0, 20.0, 5.0);
        let dae = brep_to_dae(&brep, &TessellationParams::from_segments(32));
        let vcounts = polygon_vcounts(&dae);

        assert_eq!(
            vcounts.len(),
            5,
            "wedge should have 5 polygons, got {vcounts:?}"
        );
        assert_eq!(
            vcounts.iter().filter(|&&v| v == 3).count(),
            2,
            "2 triangular caps"
        );
        assert_eq!(
            vcounts.iter().filter(|&&v| v == 4).count(),
            3,
            "3 rectangular sides"
        );
    }

    #[test]
    fn test_torus_tessellated_finite() {
        // The torus is the first primitive with a toroidal surface: its single
        // curved face must tessellate into triangles with finite coordinates.
        let brep = make_torus(10.0, 2.0, 32);
        let dae = brep_to_dae(&brep, &TessellationParams::from_segments(32));
        let vcounts = polygon_vcounts(&dae);

        assert!(!vcounts.is_empty(), "torus should produce triangles");
        assert!(
            vcounts.iter().all(|&v| v == 3),
            "torus faces must be tessellated, got {vcounts:?}"
        );

        let start = dae.find("<float_array").unwrap();
        let end = dae[start..].find("</float_array>").unwrap() + start;
        let floats = &dae[start..end];
        assert!(
            !floats.contains("NaN") && !floats.contains("inf"),
            "torus positions must be finite"
        );
    }

    #[test]
    fn test_dae_xml_validity() {
        let brep = make_cube(1.0, 1.0, 1.0);
        let params = TessellationParams::from_segments(32);
        let dae = brep_to_dae(&brep, &params);

        // Check required COLLADA elements
        assert!(dae.contains("version=\"1.4.1\""));
        assert!(dae.contains("<unit name=\"millimeter\" meter=\"0.001\"/>"));
        assert!(dae.contains("<up_axis>Z_UP</up_axis>"));
        assert!(dae.contains("<library_geometries>"));
        assert!(dae.contains("<library_visual_scenes>"));
        assert!(dae.contains("<scene>"));
        assert!(dae.contains("<instance_visual_scene"));
        assert!(dae.contains("mesh0-positions-array"));
        assert!(dae.contains("mesh0-vertices"));

        // Check that float array count matches actual floats
        let fa_marker = "float_array id=\"mesh0-positions-array\" count=\"";
        let fa_pos = dae.find(fa_marker).unwrap() + fa_marker.len();
        let fa_end = dae[fa_pos..].find('"').unwrap();
        let float_count: usize = dae[fa_pos..fa_pos + fa_end].parse().unwrap();

        let fa_content_start = dae[fa_pos..].find('>').unwrap() + fa_pos + 1;
        let fa_content_end = dae[fa_content_start..].find('<').unwrap() + fa_content_start;
        let fa_content = &dae[fa_content_start..fa_content_end];
        let actual_count = fa_content.split_whitespace().count();
        assert_eq!(
            float_count, actual_count,
            "float_array count ({}) doesn't match actual float count ({})",
            float_count, actual_count
        );
    }

    #[test]
    fn test_mesh_to_dae_single_triangle() {
        let mesh = EvaluatedMesh {
            positions: vec![0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
            indices: vec![0, 1, 2],
            normals: None,
            face_kinds: None,
            face_ids: None,
        };
        let dae = mesh_to_dae(&mesh).unwrap();

        assert!(dae.starts_with("<?xml"));
        assert!(dae.contains("<COLLADA"));
        assert!(dae.contains("</COLLADA>"));
        assert!(dae.contains("<polylist"));

        // 1 triangle = 1 polygon with vcount=3
        let vcount_start = dae.find("<vcount>").unwrap() + "<vcount>".len();
        let vcount_end = dae.find("</vcount>").unwrap();
        let vcount_str = &dae[vcount_start..vcount_end];
        assert_eq!(vcount_str.trim(), "3");

        // 3 vertices × 3 floats = 9 floats in float_array
        assert!(dae.contains("count=\"9\""));
    }

    #[test]
    fn test_mesh_to_dae_empty() {
        let mesh = EvaluatedMesh {
            positions: vec![],
            indices: vec![],
            normals: None,
            face_kinds: None,
            face_ids: None,
        };
        let dae = mesh_to_dae(&mesh).unwrap();

        assert!(dae.starts_with("<?xml"));
        assert!(dae.contains("<COLLADA"));
        // 0 vertices, 0 polygons
        assert!(dae.contains("count=\"0\""));
    }

    #[test]
    fn test_mesh_to_dae_malformed_positions() {
        let mesh = EvaluatedMesh {
            positions: vec![0.0, 1.0], // not a multiple of 3
            indices: vec![],
            normals: None,
            face_kinds: None,
            face_ids: None,
        };
        let err = mesh_to_dae(&mesh).unwrap_err();
        assert!(err.contains("not a multiple of 3"));
    }

    #[test]
    fn test_mesh_to_dae_malformed_indices() {
        let mesh = EvaluatedMesh {
            positions: vec![0.0, 1.0, 2.0],
            indices: vec![0, 0], // not a multiple of 3
            normals: None,
            face_kinds: None,
            face_ids: None,
        };
        let err = mesh_to_dae(&mesh).unwrap_err();
        assert!(err.contains("not a multiple of 3"));
    }

    #[test]
    fn test_mesh_to_dae_index_out_of_range() {
        let mesh = EvaluatedMesh {
            positions: vec![0.0, 1.0, 2.0, 3.0, 4.0, 5.0],
            indices: vec![0, 1, 5], // index 5 out of range (only 2 vertices)
            normals: None,
            face_kinds: None,
            face_ids: None,
        };
        let err = mesh_to_dae(&mesh).unwrap_err();
        assert!(err.contains("out of range"));
    }

    #[test]
    fn test_f64_precision() {
        // Use a cube with dimensions that would lose precision in f32
        let brep = make_cube(100.123456789012, 200.987654321098, 50.111222333444);
        let params = TessellationParams::from_segments(32);
        let dae = brep_to_dae(&brep, &params);

        // f64 Display should output enough digits to distinguish from f32
        // f32 can only represent ~7 significant digits
        // Check that we get more precision than f32 would give
        assert!(
            dae.contains("100.123456789012") || dae.contains("100.12345678901"),
            "DAE should preserve f64 precision for X dimension"
        );
    }
}
