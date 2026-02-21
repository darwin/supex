import { Canvas } from "@react-three/fiber";
import * as THREE from "three";
import { SceneMesh } from "./SceneMesh";
import { ViewerControls } from "./ViewerControls";
import { useViewerStore } from "./store";

const BG = "#222222";

export function Viewport() {
  const meshes = useViewerStore((s) => s.meshes);
  const clearSelection = useViewerStore((s) => s.select);

  return (
    <div className="w-full h-full">
      <Canvas
        frameloop="demand"
        camera={{ position: [50, 50, 50], fov: 50, near: 0.1, far: 10000 }}
        onPointerMissed={() => clearSelection(null)}
        shadows
        gl={{
          antialias: true,
          logarithmicDepthBuffer: true,
          toneMapping: THREE.ACESFilmicToneMapping,
          toneMappingExposure: 1.0,
        }}
        style={{ background: BG }}
      >
        <ambientLight intensity={0.4} />
        <directionalLight
          position={[50, 80, 50]}
          intensity={1.2}
          castShadow
          shadow-mapSize-width={2048}
          shadow-mapSize-height={2048}
        />
        <directionalLight position={[-30, 40, -20]} intensity={0.3} />

        {Array.from(meshes.values()).map((entry) => (
          <SceneMesh key={entry.id} entry={entry} />
        ))}

        <ViewerControls />
      </Canvas>
    </div>
  );
}
