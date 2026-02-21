import { create } from "zustand";

export interface MeshMaterial {
  color: [number, number, number];
  metallic: number;
  roughness: number;
}

export interface MeshEntry {
  id: string;
  revision: number;
  positions: Float32Array;
  indices: Uint32Array;
  normals: Float32Array;
  material: MeshMaterial;
}

export interface CameraState {
  position: [number, number, number];
  target: [number, number, number];
  fov: number;
}

interface ViewerState {
  meshes: Map<string, MeshEntry>;
  selectedId: string | null;
  camera: CameraState;

  addMesh: (entry: MeshEntry) => void;
  removeMesh: (id: string) => void;
  updateMesh: (id: string, entry: Partial<MeshEntry>) => void;
  clearMeshes: () => void;
  select: (id: string | null) => void;
  setCamera: (camera: Partial<CameraState>) => void;
}

const DEFAULT_CAMERA: CameraState = {
  position: [50, 50, 50],
  target: [0, 0, 0],
  fov: 50,
};

export const useViewerStore = create<ViewerState>((set) => ({
  meshes: new Map(),
  selectedId: null,
  camera: DEFAULT_CAMERA,

  addMesh: (entry) =>
    set((state) => {
      const next = new Map(state.meshes);
      next.set(entry.id, entry);
      return { meshes: next };
    }),

  removeMesh: (id) =>
    set((state) => {
      const next = new Map(state.meshes);
      next.delete(id);
      const selectedId = state.selectedId === id ? null : state.selectedId;
      return { meshes: next, selectedId };
    }),

  updateMesh: (id, partial) =>
    set((state) => {
      const existing = state.meshes.get(id);
      if (!existing) return state;
      const next = new Map(state.meshes);
      next.set(id, { ...existing, ...partial });
      return { meshes: next };
    }),

  clearMeshes: () => set({ meshes: new Map(), selectedId: null }),

  select: (id) => set({ selectedId: id }),

  setCamera: (partial) =>
    set((state) => ({ camera: { ...state.camera, ...partial } })),
}));
