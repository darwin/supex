import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { MockWebSocket } from "./mock-websocket";
import { DriverRelayClient, _setTauriInvokeForTest } from "../DriverRelayClient";
import { useViewerStore } from "../store";
import type { TauriMeshData } from "./tauri-mock";
import { installTauriMock, uninstallTauriMock, meshPayload } from "./tauri-mock";

describe("DriverRelayClient", () => {
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

  it("creates WebSocket with correct URL on connect", () => {
    const client = new DriverRelayClient("ws://127.0.0.1:9999");
    client.connect();

    expect(MockWebSocket.latest).toBeDefined();
    expect(MockWebSocket.latest!.url).toBe("ws://127.0.0.1:9999");

    client.dispose();
  });

  it("sends viewer.ready on open", () => {
    const client = new DriverRelayClient();
    client.connect();

    const ws = MockWebSocket.latest!;
    ws.simulateOpen();

    expect(ws.sentMessages.length).toBeGreaterThanOrEqual(1);
    const ready = ws.sentMessages[0] as Record<string, unknown>;
    expect(ready.type).toBe("viewer.ready");
    expect(ready.protocol_version).toBe("1.0");
    expect(ready.features).toEqual(
      expect.arrayContaining(["mesh", "screenshot", "state", "focus"]),
    );

    client.dispose();
  });

  it("handles mesh.update and adds mesh to store", async () => {
    const client = new DriverRelayClient();
    client.connect();
    const ws = MockWebSocket.latest!;
    ws.simulateOpen();

    ws.simulateMessage(meshPayload("node-1", 1, {
      material: { color: [1, 0, 0], metallic: 0.5, roughness: 0.3 },
    }));

    await vi.advanceTimersByTimeAsync(0);

    const state = useViewerStore.getState();
    expect(state.meshes.size).toBe(1);
    const mesh = state.meshes.get("node-1")!;
    expect(mesh.id).toBe("node-1");
    expect(mesh.revision).toBe(1);
    expect(mesh.material.color).toEqual([1, 0, 0]);
    expect(mesh.material.metallic).toBe(0.5);

    client.dispose();
  });

  it("handles mesh.remove and removes mesh from store", async () => {
    const client = new DriverRelayClient();
    client.connect();
    const ws = MockWebSocket.latest!;
    ws.simulateOpen();

    ws.simulateMessage(meshPayload("node-1", 1));
    await vi.advanceTimersByTimeAsync(0);
    expect(useViewerStore.getState().meshes.size).toBe(1);

    ws.simulateMessage({
      type: "mesh.remove",
      node_id: "node-1",
    });
    expect(useViewerStore.getState().meshes.size).toBe(0);

    client.dispose();
  });

  it("handles scene.snapshot and rebuilds store", async () => {
    const client = new DriverRelayClient();
    client.connect();
    const ws = MockWebSocket.latest!;
    ws.simulateOpen();

    // Pre-existing mesh
    ws.simulateMessage(meshPayload("old", 1));
    await vi.advanceTimersByTimeAsync(0);

    // Snapshot replaces everything
    ws.simulateMessage({
      type: "scene.snapshot",
      nodes: [
        meshPayload("snap-a", 5, {
          material: { color: [0.5, 0.5, 0.5], metallic: 0, roughness: 0.7 },
        }),
        meshPayload("snap-b", 3),
      ],
    });
    await vi.advanceTimersByTimeAsync(0);

    const state = useViewerStore.getState();
    expect(state.meshes.size).toBe(2);
    expect(state.meshes.has("old")).toBe(false);
    expect(state.meshes.has("snap-a")).toBe(true);
    expect(state.meshes.has("snap-b")).toBe(true);
    expect(state.meshes.get("snap-a")!.revision).toBe(5);

    client.dispose();
  });

  it("handles scene.reset and clears store", async () => {
    const client = new DriverRelayClient();
    client.connect();
    const ws = MockWebSocket.latest!;
    ws.simulateOpen();

    ws.simulateMessage(meshPayload("node-1", 1));
    await vi.advanceTimersByTimeAsync(0);
    expect(useViewerStore.getState().meshes.size).toBe(1);

    ws.simulateMessage({ type: "scene.reset" });
    expect(useViewerStore.getState().meshes.size).toBe(0);

    client.dispose();
  });

  it("sends viewer.state periodically", () => {
    const client = new DriverRelayClient();
    client.connect();
    const ws = MockWebSocket.latest!;
    ws.simulateOpen();

    // Clear the viewer.ready message
    ws.sentMessages.length = 0;

    // Advance time to trigger state send (1000ms interval)
    vi.advanceTimersByTime(1100);

    const stateMsg = ws.sentMessages.find(
      (m) => (m as Record<string, unknown>).type === "viewer.state",
    ) as Record<string, unknown> | undefined;
    expect(stateMsg).toBeDefined();
    expect(stateMsg!.camera).toBeDefined();
    expect(stateMsg!.selection).toEqual([]);

    client.dispose();
  });

  it("handles viewer.focus by selecting node", () => {
    const client = new DriverRelayClient();
    client.connect();
    const ws = MockWebSocket.latest!;
    ws.simulateOpen();

    ws.simulateMessage({
      type: "viewer.focus",
      node_id: "focus-target",
    });

    expect(useViewerStore.getState().selectedId).toBe("focus-target");

    client.dispose();
  });

  it("handles screenshot.request by sending response", () => {
    const client = new DriverRelayClient();
    client.connect();
    const ws = MockWebSocket.latest!;
    ws.simulateOpen();
    ws.sentMessages.length = 0;

    ws.simulateMessage({
      type: "screenshot.request",
      request_id: "req-123",
    });

    const resp = ws.sentMessages.find(
      (m) => (m as Record<string, unknown>).type === "screenshot.response",
    ) as Record<string, unknown> | undefined;
    expect(resp).toBeDefined();
    expect(resp!.request_id).toBe("req-123");

    client.dispose();
  });

  it("applies default material when none provided", async () => {
    const client = new DriverRelayClient();
    client.connect();
    const ws = MockWebSocket.latest!;
    ws.simulateOpen();

    ws.simulateMessage(meshPayload("no-mat", 1));
    await vi.advanceTimersByTimeAsync(0);

    const mesh = useViewerStore.getState().meshes.get("no-mat")!;
    expect(mesh.material.color).toEqual([0.55, 0.55, 0.55]);
    expect(mesh.material.metallic).toBe(0.0);
    expect(mesh.material.roughness).toBe(0.7);

    client.dispose();
  });

  it("dispose prevents reconnection", () => {
    const client = new DriverRelayClient();
    client.connect();
    const ws = MockWebSocket.latest!;
    ws.simulateOpen();

    client.dispose();

    // Advance past reconnect delay
    vi.advanceTimersByTime(3000);

    // Should still have only 1 instance (no reconnect)
    expect(MockWebSocket._instances.length).toBe(1);
  });
});
