import { describe, it, expect } from "vitest";
import { parseOBJ } from "../mesh-parsing";

describe("parseOBJ", () => {
  it("parses a simple triangle", () => {
    const obj = "v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n";
    const mesh = parseOBJ(obj);
    expect(mesh.positions).toEqual(
      new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]),
    );
    expect(mesh.indices).toEqual(new Uint32Array([0, 1, 2]));
    expect(mesh.normals.length).toBe(0); // no normals in source
  });

  it("parses with normals (v//n format)", () => {
    const obj = [
      "v 0 0 0",
      "v 1 0 0",
      "v 0 1 0",
      "vn 0 0 1",
      "vn 0 0 1",
      "vn 0 0 1",
      "f 1//1 2//2 3//3",
    ].join("\n");
    const mesh = parseOBJ(obj);
    expect(mesh.positions.length).toBe(9);
    expect(mesh.indices).toEqual(new Uint32Array([0, 1, 2]));
    expect(mesh.normals).toEqual(
      new Float32Array([0, 0, 1, 0, 0, 1, 0, 0, 1]),
    );
  });

  it("parses with texcoords and normals (v/t/n format)", () => {
    const obj = [
      "v 0 0 0",
      "v 1 0 0",
      "v 0 1 0",
      "vn 0 0 1",
      "f 1/1/1 2/1/1 3/1/1",
    ].join("\n");
    const mesh = parseOBJ(obj);
    expect(mesh.positions.length).toBe(9);
    expect(mesh.indices.length).toBe(3);
    expect(mesh.normals.length).toBe(9);
  });

  it("triangulates a quad", () => {
    const obj = [
      "v 0 0 0",
      "v 1 0 0",
      "v 1 1 0",
      "v 0 1 0",
      "f 1 2 3 4",
    ].join("\n");
    const mesh = parseOBJ(obj);
    // Quad -> 2 triangles = 6 indices
    expect(mesh.indices.length).toBe(6);
    // 4 unique vertices
    expect(mesh.positions.length).toBe(12);
  });

  it("handles empty/comment-only input", () => {
    const mesh = parseOBJ("# comment\n\n");
    expect(mesh.positions.length).toBe(0);
    expect(mesh.indices.length).toBe(0);
    expect(mesh.normals.length).toBe(0);
  });

  it("ignores non-geometry lines (mtllib, usemtl, o, g, s)", () => {
    const obj = [
      "mtllib material.mtl",
      "o MyObject",
      "g Group1",
      "s 1",
      "usemtl DefaultMaterial",
      "v 0 0 0",
      "v 1 0 0",
      "v 0 1 0",
      "f 1 2 3",
    ].join("\n");
    const mesh = parseOBJ(obj);
    expect(mesh.positions.length).toBe(9);
    expect(mesh.indices.length).toBe(3);
  });

  it("handles multiple faces sharing vertices", () => {
    const obj = [
      "v 0 0 0",
      "v 1 0 0",
      "v 1 1 0",
      "v 0 1 0",
      "f 1 2 3",
      "f 1 3 4",
    ].join("\n");
    const mesh = parseOBJ(obj);
    expect(mesh.indices.length).toBe(6);
    // Shared vertices should be reused
    expect(mesh.positions.length / 3).toBeLessThanOrEqual(4);
  });

  it("throws on out-of-range vertex index", () => {
    const obj = "v 0 0 0\nf 1 2 3\n";
    expect(() => parseOBJ(obj)).toThrow("out of range");
  });
});
