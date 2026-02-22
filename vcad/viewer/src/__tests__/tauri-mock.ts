/**
 * Shared Tauri invoke mock for viewer tests.
 *
 * Provides a mock `load_mesh` command that returns deterministic mesh data
 * based on the file path, so tests can send `dae_path` payloads and get
 * predictable results without actual file I/O.
 */

import { _setTauriInvokeForTest } from "../DriverRelayClient";

export interface TauriMeshData {
  id: string;
  positions: number[];
  indices: number[];
  normals: number[];
  material: {
    color: [number, number, number];
    metallic: number;
    roughness: number;
  };
}

/** Default mesh data returned by the mock Tauri invoke. */
const DEFAULT_MESH: TauriMeshData = {
  id: "mock",
  positions: [0, 0, 0, 1, 0, 0, 0, 1, 0],
  indices: [0, 1, 2],
  normals: [0, 0, 1, 0, 0, 1, 0, 0, 1],
  material: { color: [0.55, 0.55, 0.55], metallic: 0, roughness: 0.7 },
};

/** Install a mock Tauri invoke that handles `load_mesh`. */
export function installTauriMock(): void {
  _setTauriInvokeForTest(<T>(cmd: string, _args?: Record<string, unknown>) => {
    if (cmd === "load_mesh") {
      return Promise.resolve(DEFAULT_MESH as unknown as T);
    }
    return Promise.reject(new Error(`Unknown Tauri command: ${cmd}`));
  });
}

/** Remove the mock Tauri invoke. */
export function uninstallTauriMock(): void {
  _setTauriInvokeForTest(null);
}

/**
 * Build a mesh.update payload with dae_path for tests.
 *
 * The actual mesh data comes from the Tauri mock, not the payload.
 */
export function meshPayload(
  nodeId: string,
  revision: number,
  overrides?: { material?: { color?: [number, number, number]; metallic?: number; roughness?: number } },
): Record<string, unknown> {
  return {
    type: "mesh.update",
    node_id: nodeId,
    revision,
    dae_path: `/tmp/mock/${nodeId}.dae`,
    ...(overrides?.material ? { material: overrides.material } : {}),
  };
}
