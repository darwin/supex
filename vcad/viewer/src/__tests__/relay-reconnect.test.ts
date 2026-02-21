import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { MockWebSocket } from "./mock-websocket";
import { DriverRelayClient } from "../DriverRelayClient";
import { useViewerStore } from "../store";

describe("relay reconnect", () => {
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

  it("attempts reconnect after disconnect", () => {
    const client = new DriverRelayClient();
    client.connect();
    const ws1 = MockWebSocket.latest!;
    ws1.simulateOpen();

    expect(MockWebSocket._instances.length).toBe(1);

    // Disconnect
    ws1.simulateClose();

    // Advance past reconnect delay (2000ms)
    vi.advanceTimersByTime(2500);

    // Should have created a new WebSocket
    expect(MockWebSocket._instances.length).toBe(2);

    client.dispose();
  });

  it("sends viewer.ready on reconnect", () => {
    const client = new DriverRelayClient();
    client.connect();
    const ws1 = MockWebSocket.latest!;
    ws1.simulateOpen();

    // Disconnect and reconnect
    ws1.simulateClose();
    vi.advanceTimersByTime(2500);

    const ws2 = MockWebSocket.latest!;
    expect(ws2).not.toBe(ws1);
    ws2.simulateOpen();

    const ready = ws2.sentMessages[0] as Record<string, unknown>;
    expect(ready.type).toBe("viewer.ready");
    expect(ready.protocol_version).toBe("1.0");

    client.dispose();
  });

  it("scene.snapshot on reconnect rebuilds store from latest state", () => {
    const client = new DriverRelayClient();
    client.connect();
    const ws1 = MockWebSocket.latest!;
    ws1.simulateOpen();

    // Initial updates
    ws1.simulateMessage({
      type: "mesh.update",
      node_id: "n1",
      revision: 3,
      positions: [1, 2, 3],
      indices: [0],
      normals: [0, 0, 1],
      material: { color: [1, 0, 0], metallic: 0, roughness: 0.5 },
    });
    ws1.simulateMessage({
      type: "mesh.update",
      node_id: "n2",
      revision: 7,
      positions: [4, 5, 6],
      indices: [0],
      normals: [0, 1, 0],
    });

    expect(useViewerStore.getState().meshes.size).toBe(2);

    // Disconnect and reconnect
    ws1.simulateClose();
    vi.advanceTimersByTime(2500);

    const ws2 = MockWebSocket.latest!;
    ws2.simulateOpen();

    // Driver sends scene.snapshot with latest per-node state
    ws2.simulateMessage({
      type: "scene.snapshot",
      nodes: [
        {
          node_id: "n1",
          revision: 3,
          positions: [1, 2, 3],
          indices: [0],
          normals: [0, 0, 1],
          material: { color: [1, 0, 0], metallic: 0, roughness: 0.5 },
        },
        {
          node_id: "n2",
          revision: 7,
          positions: [4, 5, 6],
          indices: [0],
          normals: [0, 1, 0],
        },
      ],
    });

    const state = useViewerStore.getState();
    expect(state.meshes.size).toBe(2);
    expect(state.meshes.get("n1")!.revision).toBe(3);
    expect(state.meshes.get("n2")!.revision).toBe(7);

    client.dispose();
  });

  it("scene.snapshot contains no historical duplicates", () => {
    const client = new DriverRelayClient();
    client.connect();
    const ws1 = MockWebSocket.latest!;
    ws1.simulateOpen();

    // Multiple updates to same node
    ws1.simulateMessage({
      type: "mesh.update",
      node_id: "n1",
      revision: 1,
      positions: [0, 0, 0],
      indices: [0],
      normals: [0, 0, 1],
    });
    ws1.simulateMessage({
      type: "mesh.update",
      node_id: "n1",
      revision: 2,
      positions: [1, 1, 1],
      indices: [0],
      normals: [0, 0, 1],
    });
    ws1.simulateMessage({
      type: "mesh.update",
      node_id: "n1",
      revision: 3,
      positions: [2, 2, 2],
      indices: [0],
      normals: [0, 0, 1],
    });

    // Disconnect and reconnect
    ws1.simulateClose();
    vi.advanceTimersByTime(2500);
    const ws2 = MockWebSocket.latest!;
    ws2.simulateOpen();

    // Snapshot should only have the latest revision, not historical duplicates
    ws2.simulateMessage({
      type: "scene.snapshot",
      nodes: [
        {
          node_id: "n1",
          revision: 3,
          positions: [2, 2, 2],
          indices: [0],
          normals: [0, 0, 1],
        },
      ],
    });

    const state = useViewerStore.getState();
    expect(state.meshes.size).toBe(1);
    expect(state.meshes.get("n1")!.revision).toBe(3);
    expect(state.meshes.get("n1")!.positions[0]).toBe(2);

    client.dispose();
  });

  it("revision tracking resets after snapshot", () => {
    const client = new DriverRelayClient();
    client.connect();
    const ws1 = MockWebSocket.latest!;
    ws1.simulateOpen();

    ws1.simulateMessage({
      type: "mesh.update",
      node_id: "n1",
      revision: 10,
      positions: [0, 0, 0],
      indices: [0],
      normals: [0, 0, 1],
    });

    // Disconnect + reconnect
    ws1.simulateClose();
    vi.advanceTimersByTime(2500);
    const ws2 = MockWebSocket.latest!;
    ws2.simulateOpen();

    // Snapshot with revision 5 (lower than previously tracked 10)
    // This is valid because snapshot resets tracking
    ws2.simulateMessage({
      type: "scene.snapshot",
      nodes: [
        {
          node_id: "n1",
          revision: 5,
          positions: [5, 5, 5],
          indices: [0],
          normals: [0, 0, 1],
        },
      ],
    });

    const mesh = useViewerStore.getState().meshes.get("n1")!;
    expect(mesh.revision).toBe(5);

    // Now a revision 6 update should be accepted
    ws2.simulateMessage({
      type: "mesh.update",
      node_id: "n1",
      revision: 6,
      positions: [6, 6, 6],
      indices: [0],
      normals: [0, 0, 1],
    });

    expect(useViewerStore.getState().meshes.get("n1")!.revision).toBe(6);

    // But revision 4 (lower than snapshot's 5) should be rejected
    ws2.simulateMessage({
      type: "mesh.update",
      node_id: "n1",
      revision: 4,
      positions: [4, 4, 4],
      indices: [0],
      normals: [0, 0, 1],
    });

    expect(useViewerStore.getState().meshes.get("n1")!.revision).toBe(6);

    client.dispose();
  });

  it("stops reconnect attempts after dispose", () => {
    const client = new DriverRelayClient();
    client.connect();
    const ws = MockWebSocket.latest!;
    ws.simulateOpen();

    // Disconnect
    ws.simulateClose();
    client.dispose();

    // Even after waiting, no reconnect
    vi.advanceTimersByTime(5000);
    expect(MockWebSocket._instances.length).toBe(1);
  });
});
