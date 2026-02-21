import { useEffect, useRef, useMemo } from "react";
import * as THREE from "three";
import type { ThreeEvent } from "@react-three/fiber";
import type { MeshEntry } from "./store";
import { useViewerStore } from "./store";

const HOVER_EMISSIVE = new THREE.Color(0xffb800);

interface SceneMeshProps {
  entry: MeshEntry;
}

export function SceneMesh({ entry }: SceneMeshProps) {
  const geoRef = useRef<THREE.BufferGeometry>(null);
  const meshRef = useRef<THREE.Mesh>(null);
  const selectedId = useViewerStore((s) => s.selectedId);
  const select = useViewerStore((s) => s.select);
  const selected = selectedId === entry.id;

  // Build geometry from mesh data
  useEffect(() => {
    const geo = geoRef.current;
    if (!geo) return;

    const positions = new Float32Array(entry.positions);
    const indices = new Uint32Array(entry.indices);

    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.setIndex(new THREE.BufferAttribute(indices, 1));

    if (entry.normals.length === positions.length && positions.length > 0) {
      const normals = new Float32Array(entry.normals);
      geo.setAttribute("normal", new THREE.BufferAttribute(normals, 3));
    } else {
      geo.computeVertexNormals();
    }

    geo.computeBoundingSphere();
    geo.computeBoundingBox();

    return () => {
      geo.dispose();
    };
  }, [entry.positions, entry.indices, entry.normals]);

  const materialColor = useMemo(
    () =>
      new THREE.Color(
        entry.material.color[0],
        entry.material.color[1],
        entry.material.color[2],
      ),
    [entry.material.color],
  );

  const emissiveColor = useMemo(() => {
    if (selected) return materialColor.clone().multiplyScalar(0.3);
    return undefined;
  }, [selected, materialColor]);

  const emissiveIntensity = selected ? 0.2 : 0;

  const handleClick = (e: ThreeEvent<MouseEvent>) => {
    e.stopPropagation();
    select(entry.id);
  };

  return (
    <mesh
      ref={meshRef}
      castShadow
      receiveShadow
      onClick={handleClick}
    >
      <bufferGeometry ref={geoRef} />
      <meshStandardMaterial
        color={materialColor}
        emissive={emissiveColor ?? HOVER_EMISSIVE}
        emissiveIntensity={emissiveIntensity}
        metalness={entry.material.metallic}
        roughness={entry.material.roughness}
        envMapIntensity={0.8}
        flatShading={false}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}
