import { describe, it, expect, beforeEach } from "vitest";
import ReactThreeTestRenderer from "@react-three/test-renderer";
import { SceneMesh } from "../SceneMesh";
import { useViewerStore } from "../store";
import type { MeshEntry } from "../store";

function makeMesh(id: string): MeshEntry {
  return {
    id,
    revision: 0,
    positions: new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]),
    indices: new Uint32Array([0, 1, 2]),
    normals: new Float32Array([0, 0, 1, 0, 0, 1, 0, 0, 1]),
    material: { color: [0.5, 0.5, 0.5], metallic: 0.2, roughness: 0.8 },
  };
}

describe("SceneMesh", () => {
  beforeEach(() => {
    useViewerStore.setState({
      meshes: new Map(),
      selectedId: null,
      camera: { position: [50, 50, 50], target: [0, 0, 0], fov: 50 },
    });
  });

  it("renders a mesh with bufferGeometry and material", async () => {
    const entry = makeMesh("test");
    const renderer = await ReactThreeTestRenderer.create(
      <SceneMesh entry={entry} />,
    );

    // Verify mesh node exists via scene graph
    const meshNode = renderer.scene.findByType("Mesh");
    expect(meshNode).toBeDefined();

    // Verify tree contains both geometry and material
    const tree = renderer.toTree();
    expect(tree).toBeDefined();
    const geoNode = findNodeByType(tree!, "bufferGeometry");
    const matNode = findNodeByType(tree!, "meshStandardMaterial");
    expect(geoNode).toBeDefined();
    expect(matNode).toBeDefined();

    await renderer.unmount();
  });

  it("applies material properties from entry", async () => {
    const entry = makeMesh("mat-test");
    entry.material = { color: [1, 0, 0], metallic: 0.8, roughness: 0.2 };

    const renderer = await ReactThreeTestRenderer.create(
      <SceneMesh entry={entry} />,
    );

    const tree = renderer.toTree();
    expect(tree).toBeDefined();

    // Verify the tree contains a meshStandardMaterial
    const materialNode = findNodeByType(tree!, "meshStandardMaterial");
    expect(materialNode).toBeDefined();
    if (materialNode) {
      expect(materialNode.props.metalness).toBe(0.8);
      expect(materialNode.props.roughness).toBe(0.2);
    }

    await renderer.unmount();
  });
});

// Helper to recursively find a node by type in the tree
function findNodeByType(
  nodes: Array<{ type: string; children: Array<unknown> }>,
  type: string,
): { type: string; props: Record<string, unknown>; children: unknown[] } | null {
  for (const node of nodes) {
    if (node.type === type) return node as never;
    if (node.children) {
      const found = findNodeByType(
        node.children as Array<{ type: string; children: Array<unknown> }>,
        type,
      );
      if (found) return found;
    }
  }
  return null;
}
