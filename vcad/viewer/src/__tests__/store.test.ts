import { describe, it, expect, beforeEach } from "vitest";
import { useViewerStore } from "../store";
import type { MeshEntry } from "../store";

function makeMesh(id: string): MeshEntry {
  return {
    id,
    positions: new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0]),
    indices: new Uint32Array([0, 1, 2]),
    normals: new Float32Array([0, 0, 1, 0, 0, 1, 0, 0, 1]),
    material: { color: [0.5, 0.5, 0.5], metallic: 0, roughness: 0.7 },
  };
}

describe("useViewerStore", () => {
  beforeEach(() => {
    // Reset store state
    useViewerStore.setState({
      meshes: new Map(),
      selectedId: null,
      camera: { position: [50, 50, 50], target: [0, 0, 0], fov: 50 },
    });
  });

  it("starts with empty meshes", () => {
    const state = useViewerStore.getState();
    expect(state.meshes.size).toBe(0);
    expect(state.selectedId).toBeNull();
  });

  it("addMesh adds a mesh entry", () => {
    useViewerStore.getState().addMesh(makeMesh("a"));
    const state = useViewerStore.getState();
    expect(state.meshes.size).toBe(1);
    expect(state.meshes.get("a")).toBeDefined();
    expect(state.meshes.get("a")!.id).toBe("a");
  });

  it("addMesh replaces mesh with same id", () => {
    useViewerStore.getState().addMesh(makeMesh("a"));
    const updated = {
      ...makeMesh("a"),
      material: { color: [1, 0, 0] as [number, number, number], metallic: 0.5, roughness: 0.3 },
    };
    useViewerStore.getState().addMesh(updated);
    const state = useViewerStore.getState();
    expect(state.meshes.size).toBe(1);
    expect(state.meshes.get("a")!.material.metallic).toBe(0.5);
  });

  it("removeMesh removes a mesh", () => {
    useViewerStore.getState().addMesh(makeMesh("a"));
    useViewerStore.getState().addMesh(makeMesh("b"));
    useViewerStore.getState().removeMesh("a");
    const state = useViewerStore.getState();
    expect(state.meshes.size).toBe(1);
    expect(state.meshes.has("a")).toBe(false);
    expect(state.meshes.has("b")).toBe(true);
  });

  it("removeMesh clears selection if removed mesh was selected", () => {
    useViewerStore.getState().addMesh(makeMesh("a"));
    useViewerStore.getState().select("a");
    expect(useViewerStore.getState().selectedId).toBe("a");
    useViewerStore.getState().removeMesh("a");
    expect(useViewerStore.getState().selectedId).toBeNull();
  });

  it("removeMesh preserves selection if different mesh removed", () => {
    useViewerStore.getState().addMesh(makeMesh("a"));
    useViewerStore.getState().addMesh(makeMesh("b"));
    useViewerStore.getState().select("a");
    useViewerStore.getState().removeMesh("b");
    expect(useViewerStore.getState().selectedId).toBe("a");
  });

  it("updateMesh updates partial fields", () => {
    useViewerStore.getState().addMesh(makeMesh("a"));
    useViewerStore.getState().updateMesh("a", {
      material: { color: [1, 0, 0], metallic: 1, roughness: 0.1 },
    });
    const mesh = useViewerStore.getState().meshes.get("a")!;
    expect(mesh.material.color).toEqual([1, 0, 0]);
    expect(mesh.material.metallic).toBe(1);
  });

  it("updateMesh is no-op for unknown id", () => {
    useViewerStore.getState().updateMesh("nonexistent", {
      material: { color: [1, 0, 0], metallic: 0, roughness: 0 },
    });
    expect(useViewerStore.getState().meshes.size).toBe(0);
  });

  it("clearMeshes removes all meshes and clears selection", () => {
    useViewerStore.getState().addMesh(makeMesh("a"));
    useViewerStore.getState().addMesh(makeMesh("b"));
    useViewerStore.getState().select("a");
    useViewerStore.getState().clearMeshes();
    const state = useViewerStore.getState();
    expect(state.meshes.size).toBe(0);
    expect(state.selectedId).toBeNull();
  });

  it("select sets selectedId", () => {
    useViewerStore.getState().select("x");
    expect(useViewerStore.getState().selectedId).toBe("x");
    useViewerStore.getState().select(null);
    expect(useViewerStore.getState().selectedId).toBeNull();
  });

  it("setCamera merges partial camera state", () => {
    useViewerStore.getState().setCamera({ fov: 35 });
    const cam = useViewerStore.getState().camera;
    expect(cam.fov).toBe(35);
    expect(cam.position).toEqual([50, 50, 50]); // unchanged
  });

  it("setCamera updates position", () => {
    useViewerStore.getState().setCamera({ position: [10, 20, 30] });
    expect(useViewerStore.getState().camera.position).toEqual([10, 20, 30]);
  });
});
