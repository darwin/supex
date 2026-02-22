import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { MockWebSocket } from "./mock-websocket";
import { DriverRelayClient } from "../DriverRelayClient";
import { useViewerStore } from "../store";
import { installTauriMock, uninstallTauriMock, meshPayload } from "./tauri-mock";

describe("relay freshness (revision guard)", () => {
  beforeEach(() => {
    MockWebSocket.install();
    installTauriMock();
    useViewerStore.setState({
      meshes: new Map(),
      selectedId: null,
      camera: { position: [50, 50, 50], target: [0, 0, 0], fov: 50 },
    });
    vi.useFakeTimers();
  });

  afterEach(() => {
    MockWebSocket.uninstall();
    uninstallTauriMock();
    vi.useRealTimers();
  });

  function connectClient(): { client: DriverRelayClient; ws: MockWebSocket } {
    const client = new DriverRelayClient();
    client.connect();
    const ws = MockWebSocket.latest!;
    ws.simulateOpen();
    return { client, ws };
  }

  it("applies higher revision mesh update", async () => {
    const { client, ws } = connectClient();

    ws.simulateMessage(meshPayload("n1", 1, {
      material: { color: [1, 0, 0], metallic: 0, roughness: 0.5 },
    }));
    await vi.advanceTimersByTimeAsync(0);

    ws.simulateMessage(meshPayload("n1", 2, {
      material: { color: [0, 1, 0], metallic: 0.5, roughness: 0.5 },
    }));
    await vi.advanceTimersByTimeAsync(0);

    const mesh = useViewerStore.getState().meshes.get("n1")!;
    expect(mesh.revision).toBe(2);
    expect(mesh.material.color).toEqual([0, 1, 0]);

    client.dispose();
  });

  it("ignores out-of-order mesh.update with lower revision", async () => {
    const { client, ws } = connectClient();

    // Apply revision 3 first
    ws.simulateMessage(meshPayload("n1", 3, {
      material: { color: [0, 0, 1], metallic: 0, roughness: 0.5 },
    }));
    await vi.advanceTimersByTimeAsync(0);

    // Now stale revision 1 arrives (out of order)
    ws.simulateMessage(meshPayload("n1", 1, {
      material: { color: [1, 0, 0], metallic: 0, roughness: 0.5 },
    }));
    await vi.advanceTimersByTimeAsync(0);

    // Store should still have revision 3 data
    const mesh = useViewerStore.getState().meshes.get("n1")!;
    expect(mesh.revision).toBe(3);
    expect(mesh.material.color).toEqual([0, 0, 1]);

    client.dispose();
  });

  it("applies equal revision (idempotent update)", async () => {
    const { client, ws } = connectClient();

    ws.simulateMessage(meshPayload("n1", 2));
    await vi.advanceTimersByTimeAsync(0);

    // Same revision with different material (idempotent, still applied)
    ws.simulateMessage(meshPayload("n1", 2, {
      material: { color: [1, 1, 0], metallic: 1, roughness: 0 },
    }));
    await vi.advanceTimersByTimeAsync(0);

    const mesh = useViewerStore.getState().meshes.get("n1")!;
    expect(mesh.revision).toBe(2);
    expect(mesh.material.color).toEqual([1, 1, 0]);

    client.dispose();
  });

  it("tracks revisions per node independently", async () => {
    const { client, ws } = connectClient();

    ws.simulateMessage(meshPayload("a", 5));
    ws.simulateMessage(meshPayload("b", 2));
    await vi.advanceTimersByTimeAsync(0);

    // Stale update for 'a' ignored, valid update for 'b' applied
    ws.simulateMessage(meshPayload("a", 3));
    ws.simulateMessage(meshPayload("b", 4));
    await vi.advanceTimersByTimeAsync(0);

    expect(useViewerStore.getState().meshes.get("a")!.revision).toBe(5);
    expect(useViewerStore.getState().meshes.get("b")!.revision).toBe(4);

    client.dispose();
  });

  it("mesh.remove clears revision tracking for that node", async () => {
    const { client, ws } = connectClient();

    ws.simulateMessage(meshPayload("n1", 5));
    await vi.advanceTimersByTimeAsync(0);

    ws.simulateMessage({ type: "mesh.remove", node_id: "n1" });

    // After remove, revision tracking is cleared, so revision 1 is accepted
    ws.simulateMessage(meshPayload("n1", 1));
    await vi.advanceTimersByTimeAsync(0);

    const mesh = useViewerStore.getState().meshes.get("n1")!;
    expect(mesh.revision).toBe(1);

    client.dispose();
  });

  it("scene.reset clears all revision tracking", async () => {
    const { client, ws } = connectClient();

    ws.simulateMessage(meshPayload("n1", 10));
    await vi.advanceTimersByTimeAsync(0);

    ws.simulateMessage({ type: "scene.reset" });

    // After reset, revision 1 is accepted for any node
    ws.simulateMessage(meshPayload("n1", 1));
    await vi.advanceTimersByTimeAsync(0);

    expect(useViewerStore.getState().meshes.get("n1")!.revision).toBe(1);

    client.dispose();
  });
});
