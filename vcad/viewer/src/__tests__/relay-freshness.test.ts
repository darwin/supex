import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { MockWebSocket } from "./mock-websocket";
import { DriverRelayClient } from "../DriverRelayClient";
import { useViewerStore } from "../store";

describe("relay freshness (revision guard)", () => {
  beforeEach(() => {
    MockWebSocket.install();
    useViewerStore.setState({
      meshes: new Map(),
      selectedId: null,
      camera: { position: [50, 50, 50], target: [0, 0, 0], fov: 50 },
    });
    vi.useFakeTimers();
  });

  afterEach(() => {
    MockWebSocket.uninstall();
    vi.useRealTimers();
  });

  function connectClient(): { client: DriverRelayClient; ws: MockWebSocket } {
    const client = new DriverRelayClient();
    client.connect();
    const ws = MockWebSocket.latest!;
    ws.simulateOpen();
    return { client, ws };
  }

  it("applies higher revision mesh update", () => {
    const { client, ws } = connectClient();

    ws.simulateMessage({
      type: "mesh.update",
      node_id: "n1",
      revision: 1,
      positions: [0, 0, 0],
      indices: [0],
      normals: [0, 0, 1],
      material: { color: [1, 0, 0], metallic: 0, roughness: 0.5 },
    });

    ws.simulateMessage({
      type: "mesh.update",
      node_id: "n1",
      revision: 2,
      positions: [1, 1, 1],
      indices: [0],
      normals: [0, 1, 0],
      material: { color: [0, 1, 0], metallic: 0.5, roughness: 0.5 },
    });

    const mesh = useViewerStore.getState().meshes.get("n1")!;
    expect(mesh.revision).toBe(2);
    expect(mesh.material.color).toEqual([0, 1, 0]);
    expect(mesh.positions[0]).toBe(1);

    client.dispose();
  });

  it("ignores out-of-order mesh.update with lower revision", () => {
    const { client, ws } = connectClient();

    // Apply revision 3 first
    ws.simulateMessage({
      type: "mesh.update",
      node_id: "n1",
      revision: 3,
      positions: [3, 3, 3],
      indices: [0],
      normals: [0, 0, 1],
      material: { color: [0, 0, 1], metallic: 0, roughness: 0.5 },
    });

    // Now stale revision 1 arrives (out of order)
    ws.simulateMessage({
      type: "mesh.update",
      node_id: "n1",
      revision: 1,
      positions: [1, 1, 1],
      indices: [0],
      normals: [0, 0, 1],
      material: { color: [1, 0, 0], metallic: 0, roughness: 0.5 },
    });

    // Store should still have revision 3 data
    const mesh = useViewerStore.getState().meshes.get("n1")!;
    expect(mesh.revision).toBe(3);
    expect(mesh.material.color).toEqual([0, 0, 1]);
    expect(mesh.positions[0]).toBe(3);

    client.dispose();
  });

  it("applies equal revision (idempotent update)", () => {
    const { client, ws } = connectClient();

    ws.simulateMessage({
      type: "mesh.update",
      node_id: "n1",
      revision: 2,
      positions: [2, 2, 2],
      indices: [0],
      normals: [0, 0, 1],
    });

    // Same revision with different material (idempotent, still applied)
    ws.simulateMessage({
      type: "mesh.update",
      node_id: "n1",
      revision: 2,
      positions: [2, 2, 2],
      indices: [0],
      normals: [0, 0, 1],
      material: { color: [1, 1, 0], metallic: 1, roughness: 0 },
    });

    const mesh = useViewerStore.getState().meshes.get("n1")!;
    expect(mesh.revision).toBe(2);
    expect(mesh.material.color).toEqual([1, 1, 0]);

    client.dispose();
  });

  it("tracks revisions per node independently", () => {
    const { client, ws } = connectClient();

    ws.simulateMessage({
      type: "mesh.update",
      node_id: "a",
      revision: 5,
      positions: [0, 0, 0],
      indices: [0],
      normals: [0, 0, 1],
    });

    ws.simulateMessage({
      type: "mesh.update",
      node_id: "b",
      revision: 2,
      positions: [1, 1, 1],
      indices: [0],
      normals: [0, 0, 1],
    });

    // Stale update for 'a' ignored, valid update for 'b' applied
    ws.simulateMessage({
      type: "mesh.update",
      node_id: "a",
      revision: 3,
      positions: [9, 9, 9],
      indices: [0],
      normals: [0, 0, 1],
    });

    ws.simulateMessage({
      type: "mesh.update",
      node_id: "b",
      revision: 4,
      positions: [4, 4, 4],
      indices: [0],
      normals: [0, 0, 1],
    });

    expect(useViewerStore.getState().meshes.get("a")!.revision).toBe(5);
    expect(useViewerStore.getState().meshes.get("a")!.positions[0]).toBe(0);
    expect(useViewerStore.getState().meshes.get("b")!.revision).toBe(4);
    expect(useViewerStore.getState().meshes.get("b")!.positions[0]).toBe(4);

    client.dispose();
  });

  it("mesh.remove clears revision tracking for that node", () => {
    const { client, ws } = connectClient();

    ws.simulateMessage({
      type: "mesh.update",
      node_id: "n1",
      revision: 5,
      positions: [0, 0, 0],
      indices: [0],
      normals: [0, 0, 1],
    });

    ws.simulateMessage({ type: "mesh.remove", node_id: "n1" });

    // After remove, revision tracking is cleared, so revision 1 is accepted
    ws.simulateMessage({
      type: "mesh.update",
      node_id: "n1",
      revision: 1,
      positions: [1, 1, 1],
      indices: [0],
      normals: [0, 0, 1],
    });

    const mesh = useViewerStore.getState().meshes.get("n1")!;
    expect(mesh.revision).toBe(1);

    client.dispose();
  });

  it("scene.reset clears all revision tracking", () => {
    const { client, ws } = connectClient();

    ws.simulateMessage({
      type: "mesh.update",
      node_id: "n1",
      revision: 10,
      positions: [0, 0, 0],
      indices: [0],
      normals: [0, 0, 1],
    });

    ws.simulateMessage({ type: "scene.reset" });

    // After reset, revision 1 is accepted for any node
    ws.simulateMessage({
      type: "mesh.update",
      node_id: "n1",
      revision: 1,
      positions: [1, 1, 1],
      indices: [0],
      normals: [0, 0, 1],
    });

    expect(useViewerStore.getState().meshes.get("n1")!.revision).toBe(1);

    client.dispose();
  });
});
