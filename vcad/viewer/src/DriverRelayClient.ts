/**
 * WebSocket client connecting viewer to the driver relay.
 *
 * Receives mesh push messages (mesh.update, mesh.remove, scene.snapshot,
 * scene.reset) and updates the Zustand store. Sends viewer.ready on
 * connect and periodic viewer.state with camera/selection.
 */

import { useViewerStore } from "./store";
import type { MeshMaterial } from "./store";

const RELAY_PROTOCOL_VERSION = "1.0";
const VIEWER_FEATURES = ["mesh", "screenshot", "state", "focus"];
const RECONNECT_DELAY_MS = 2000;
const STATE_SEND_INTERVAL_MS = 1000;

const DEFAULT_MATERIAL: MeshMaterial = {
  color: [0.55, 0.55, 0.55],
  metallic: 0.0,
  roughness: 0.7,
};

interface RelayMessage {
  type: string;
  [key: string]: unknown;
}

interface MeshUpdatePayload {
  node_id: string;
  revision: number;
  positions: number[];
  indices: number[];
  normals: number[];
  material?: {
    color?: [number, number, number];
    metallic?: number;
    roughness?: number;
  };
  bbox?: unknown;
}

export class DriverRelayClient {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private stateSendTimer: ReturnType<typeof setInterval> | null = null;
  private latestRevisionByNode: Map<string, number> = new Map();
  private _disposed = false;

  constructor(url: string = "ws://127.0.0.1:9878") {
    this.url = url;
  }

  connect(): void {
    if (this._disposed) return;
    this.cleanup();

    this.ws = new WebSocket(this.url);
    this.ws.onopen = () => this.onOpen();
    this.ws.onmessage = (event: MessageEvent) => this.onMessage(event);
    this.ws.onclose = () => this.onClose();
    this.ws.onerror = () => {};
  }

  private onOpen(): void {
    this.send({
      type: "viewer.ready",
      protocol_version: RELAY_PROTOCOL_VERSION,
      features: VIEWER_FEATURES,
    });

    this.stateSendTimer = setInterval(() => {
      this.sendViewerState();
    }, STATE_SEND_INTERVAL_MS);
  }

  private onMessage(event: MessageEvent): void {
    try {
      const msg = JSON.parse(event.data as string) as RelayMessage;
      this.handleMessage(msg);
    } catch {
      // Invalid JSON, ignore
    }
  }

  private handleMessage(msg: RelayMessage): void {
    switch (msg.type) {
      case "mesh.update":
        this.handleMeshUpdate(msg as unknown as MeshUpdatePayload);
        break;
      case "mesh.remove":
        this.handleMeshRemove(msg.node_id as string);
        break;
      case "scene.snapshot":
        this.handleSceneSnapshot(msg.nodes as MeshUpdatePayload[]);
        break;
      case "scene.reset":
        this.handleSceneReset();
        break;
      case "screenshot.request":
        this.handleScreenshotRequest(msg.request_id as string);
        break;
      case "viewer.focus":
        this.handleViewerFocus(msg.node_id as string);
        break;
    }
  }

  private handleMeshUpdate(payload: MeshUpdatePayload): void {
    const { node_id, revision } = payload;

    // Freshness guard: ignore lower revision
    const currentRev = this.latestRevisionByNode.get(node_id) ?? -1;
    if (revision < currentRev) return;
    this.latestRevisionByNode.set(node_id, revision);

    const store = useViewerStore.getState();
    store.addMesh({
      id: node_id,
      revision,
      positions: new Float32Array(payload.positions),
      indices: new Uint32Array(payload.indices),
      normals: new Float32Array(payload.normals),
      material: this.parseMaterial(payload.material),
    });
  }

  private handleMeshRemove(nodeId: string): void {
    this.latestRevisionByNode.delete(nodeId);
    useViewerStore.getState().removeMesh(nodeId);
  }

  private handleSceneSnapshot(nodes: MeshUpdatePayload[]): void {
    if (!Array.isArray(nodes)) return;

    const store = useViewerStore.getState();
    store.clearMeshes();
    this.latestRevisionByNode.clear();

    for (const node of nodes) {
      this.latestRevisionByNode.set(node.node_id, node.revision);
      store.addMesh({
        id: node.node_id,
        revision: node.revision,
        positions: new Float32Array(node.positions),
        indices: new Uint32Array(node.indices),
        normals: new Float32Array(node.normals),
        material: this.parseMaterial(node.material),
      });
    }
  }

  private handleSceneReset(): void {
    this.latestRevisionByNode.clear();
    useViewerStore.getState().clearMeshes();
  }

  private handleScreenshotRequest(requestId: string): void {
    // Screenshot capture will be implemented via Tauri canvas capture.
    // For now, send an empty response.
    this.send({
      type: "screenshot.response",
      request_id: requestId,
      data: "",
      width: 0,
      height: 0,
    });
  }

  private handleViewerFocus(nodeId: string): void {
    useViewerStore.getState().select(nodeId);
  }

  private sendViewerState(): void {
    const state = useViewerStore.getState();
    this.send({
      type: "viewer.state",
      camera: state.camera,
      selection: state.selectedId ? [state.selectedId] : [],
    });
  }

  private send(msg: Record<string, unknown>): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  private onClose(): void {
    this.stopTimers();
    if (!this._disposed) {
      this.reconnectTimer = setTimeout(() => this.connect(), RECONNECT_DELAY_MS);
    }
  }

  private stopTimers(): void {
    if (this.stateSendTimer) {
      clearInterval(this.stateSendTimer);
      this.stateSendTimer = null;
    }
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private cleanup(): void {
    this.stopTimers();
    if (this.ws) {
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onclose = null;
      this.ws.onerror = null;
      if (
        this.ws.readyState === WebSocket.OPEN ||
        this.ws.readyState === WebSocket.CONNECTING
      ) {
        this.ws.close();
      }
      this.ws = null;
    }
  }

  dispose(): void {
    this._disposed = true;
    this.cleanup();
  }

  private parseMaterial(raw?: {
    color?: [number, number, number];
    metallic?: number;
    roughness?: number;
  }): MeshMaterial {
    if (!raw) return { ...DEFAULT_MATERIAL };
    return {
      color: raw.color ?? DEFAULT_MATERIAL.color,
      metallic: raw.metallic ?? DEFAULT_MATERIAL.metallic,
      roughness: raw.roughness ?? DEFAULT_MATERIAL.roughness,
    };
  }

  /** Expose revision map for testing. */
  get revisionMap(): Map<string, number> {
    return new Map(this.latestRevisionByNode);
  }
}
