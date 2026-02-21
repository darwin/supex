import { describe, it, expect, beforeEach } from "vitest";
import ReactThreeTestRenderer from "@react-three/test-renderer";
import { SceneMesh } from "../SceneMesh";
import { useViewerStore } from "../store";
import type { MeshEntry } from "../store";

function makeMesh(id: string): MeshEntry {
  return {
    id,
    positions: new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]),
    indices: new Uint32Array([0, 1, 2]),
    normals: new Float32Array([0, 0, 1, 0, 0, 1, 0, 0, 1]),
    material: { color: [0.55, 0.55, 0.55], metallic: 0, roughness: 0.7 },
  };
}

/**
 * Scene-level tests that verify the correct number of meshes are rendered
 * based on store state. We render SceneMesh components directly (rather than
 * the full Viewport which requires Canvas context) to test scene composition.
 */
describe("Viewport scene composition", () => {
  beforeEach(() => {
    useViewerStore.setState({
      meshes: new Map(),
      selectedId: null,
      camera: { position: [50, 50, 50], target: [0, 0, 0], fov: 50 },
    });
  });

  it("renders correct number of meshes from store", async () => {
    const entries = [makeMesh("a"), makeMesh("b"), makeMesh("c")];

    const renderer = await ReactThreeTestRenderer.create(
      <>
        {entries.map((entry) => (
          <SceneMesh key={entry.id} entry={entry} />
        ))}
      </>,
    );

    const meshNodes = renderer.scene.findAllByType("Mesh");
    expect(meshNodes.length).toBe(3);

    await renderer.unmount();
  });

  it("renders empty scene when no meshes", async () => {
    const renderer = await ReactThreeTestRenderer.create(<></>);

    const meshNodes = renderer.scene.findAllByType("Mesh");
    expect(meshNodes.length).toBe(0);

    await renderer.unmount();
  });

  it("updates scene when meshes are added via store", async () => {
    function SceneFromStore() {
      const meshes = useViewerStore((s) => s.meshes);
      return (
        <>
          {Array.from(meshes.values()).map((entry) => (
            <SceneMesh key={entry.id} entry={entry} />
          ))}
        </>
      );
    }

    const renderer = await ReactThreeTestRenderer.create(<SceneFromStore />);

    // Initially empty
    let meshNodes = renderer.scene.findAllByType("Mesh");
    expect(meshNodes.length).toBe(0);

    // Add meshes via store
    await ReactThreeTestRenderer.act(async () => {
      useViewerStore.getState().addMesh(makeMesh("x"));
      useViewerStore.getState().addMesh(makeMesh("y"));
    });

    meshNodes = renderer.scene.findAllByType("Mesh");
    expect(meshNodes.length).toBe(2);

    // Remove one
    await ReactThreeTestRenderer.act(async () => {
      useViewerStore.getState().removeMesh("x");
    });

    meshNodes = renderer.scene.findAllByType("Mesh");
    expect(meshNodes.length).toBe(1);

    await renderer.unmount();
  });
});
