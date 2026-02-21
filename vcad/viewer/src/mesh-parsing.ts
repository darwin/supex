export interface ParsedMesh {
  positions: Float32Array;
  indices: Uint32Array;
  normals: Float32Array;
}

interface FaceVertex {
  vi: number;
  ni: number | null;
}

/**
 * Parse a Wavefront OBJ string into typed arrays.
 *
 * Supports:
 * - `v x y z` vertex positions
 * - `vn nx ny nz` vertex normals
 * - `f v1 v2 v3 ...` faces (triangulated via fan)
 * - `f v1//n1 v2//n2 v3//n3` faces with normals
 * - `f v1/t1/n1 v2/t2/n2 v3/t3/n3` faces with texcoords and normals
 */
export function parseOBJ(source: string): ParsedMesh {
  const rawPositions: number[][] = [];
  const rawNormals: number[][] = [];

  const outPositions: number[] = [];
  const outNormals: number[] = [];
  const outIndices: number[] = [];

  const vertexMap = new Map<string, number>();

  const lines = source.split("\n");
  for (const raw of lines) {
    const line = raw.trim();
    if (line.length === 0 || line[0] === "#") continue;

    if (line.startsWith("v ")) {
      const parts = line.slice(2).trim().split(/\s+/).map(Number);
      rawPositions.push([parts[0] ?? 0, parts[1] ?? 0, parts[2] ?? 0]);
    } else if (line.startsWith("vn ")) {
      const parts = line.slice(3).trim().split(/\s+/).map(Number);
      rawNormals.push([parts[0] ?? 0, parts[1] ?? 0, parts[2] ?? 0]);
    } else if (line.startsWith("f ")) {
      const tokens = line.slice(2).trim().split(/\s+/);
      const faceVerts: FaceVertex[] = tokens.map(parseFaceToken);
      // Fan triangulation
      for (let i = 1; i < faceVerts.length - 1; i++) {
        const tri = [faceVerts[0], faceVerts[i], faceVerts[i + 1]];
        for (const fv of tri) {
          const key = `${fv.vi}/${fv.ni ?? ""}`;
          let idx = vertexMap.get(key);
          if (idx === undefined) {
            idx = outPositions.length / 3;
            const p = rawPositions[fv.vi];
            if (!p) throw new Error(`Vertex index ${fv.vi + 1} out of range`);
            outPositions.push(p[0], p[1], p[2]);
            if (fv.ni !== null) {
              const n = rawNormals[fv.ni];
              if (n) outNormals.push(n[0], n[1], n[2]);
            }
            vertexMap.set(key, idx);
          }
          outIndices.push(idx);
        }
      }
    }
  }

  // Drop normals if count doesn't match positions
  const normals =
    outNormals.length === outPositions.length
      ? new Float32Array(outNormals)
      : new Float32Array(0);

  return {
    positions: new Float32Array(outPositions),
    indices: new Uint32Array(outIndices),
    normals,
  };
}

function parseFaceToken(token: string): FaceVertex {
  const parts = token.split("/");
  const vi = parseInt(parts[0], 10) - 1;
  const ni =
    parts.length >= 3 && parts[2] !== ""
      ? parseInt(parts[2], 10) - 1
      : null;
  return { vi, ni };
}
