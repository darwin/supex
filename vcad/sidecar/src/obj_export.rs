use crate::evaluator::BBox;
use std::fmt::Write;
use vcad_eval::EvaluatedMesh;

/// Convert EvaluatedMesh to Wavefront OBJ text format.
/// EvaluatedMesh has: positions: Vec<f32>, indices: Vec<u32>, normals: Option<Vec<f32>>
/// Units: mm (vcad default).
/// OBJ carries geometry only (no materials).
pub fn mesh_to_obj(mesh: &EvaluatedMesh) -> String {
    let mut obj = String::new();

    // Vertices: v x y z
    for i in (0..mesh.positions.len()).step_by(3) {
        writeln!(
            obj,
            "v {} {} {}",
            mesh.positions[i],
            mesh.positions[i + 1],
            mesh.positions[i + 2]
        )
        .unwrap();
    }

    // Normals: vn nx ny nz (if available)
    let has_normals = mesh.normals.as_ref().is_some_and(|n| !n.is_empty());
    if let Some(ref normals) = mesh.normals {
        for i in (0..normals.len()).step_by(3) {
            writeln!(
                obj,
                "vn {} {} {}",
                normals[i],
                normals[i + 1],
                normals[i + 2]
            )
            .unwrap();
        }
    }

    // Faces: f v1//n1 v2//n2 v3//n3 (with normals) or f v1 v2 v3 (without)
    for i in (0..mesh.indices.len()).step_by(3) {
        let v1 = mesh.indices[i] + 1;
        let v2 = mesh.indices[i + 1] + 1;
        let v3 = mesh.indices[i + 2] + 1;
        if has_normals {
            writeln!(obj, "f {v1}//{v1} {v2}//{v2} {v3}//{v3}").unwrap();
        } else {
            writeln!(obj, "f {v1} {v2} {v3}").unwrap();
        }
    }

    obj
}

/// Compute bounding box from mesh positions (fallback when Solid not available).
/// EvaluatedMesh.positions is Vec<f32>, convert to f64 for BBox.
pub fn compute_mesh_bbox(mesh: &EvaluatedMesh) -> BBox {
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

#[cfg(test)]
mod tests {
    use super::*;

    fn make_triangle_mesh() -> EvaluatedMesh {
        EvaluatedMesh {
            positions: vec![0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
            indices: vec![0, 1, 2],
            normals: Some(vec![0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0]),
        }
    }

    #[test]
    fn test_mesh_to_obj_with_normals() {
        let mesh = make_triangle_mesh();
        let obj = mesh_to_obj(&mesh);
        assert!(obj.contains("v 0 0 0"));
        assert!(obj.contains("v 1 0 0"));
        assert!(obj.contains("v 0 1 0"));
        assert!(obj.contains("vn 0 0 1"));
        assert!(obj.contains("f 1//1 2//2 3//3"));
    }

    #[test]
    fn test_mesh_to_obj_without_normals() {
        let mesh = EvaluatedMesh {
            positions: vec![0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
            indices: vec![0, 1, 2],
            normals: None,
        };
        let obj = mesh_to_obj(&mesh);
        assert!(obj.contains("f 1 2 3"));
        assert!(!obj.contains("vn"));
        assert!(!obj.contains("//"));
    }

    #[test]
    fn test_compute_mesh_bbox() {
        let mesh = make_triangle_mesh();
        let bbox = compute_mesh_bbox(&mesh);
        assert_eq!(bbox.min, [0.0, 0.0, 0.0]);
        assert_eq!(bbox.max, [1.0, 1.0, 0.0]);
    }

    #[test]
    fn test_compute_mesh_bbox_empty() {
        let mesh = EvaluatedMesh {
            positions: vec![],
            indices: vec![],
            normals: None,
        };
        let bbox = compute_mesh_bbox(&mesh);
        assert_eq!(bbox.min, [0.0; 3]);
        assert_eq!(bbox.max, [0.0; 3]);
    }
}
