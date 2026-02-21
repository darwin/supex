import { OrbitControls, Grid, GizmoHelper, GizmoViewport } from "@react-three/drei";

export function ViewerControls() {
  return (
    <>
      <OrbitControls makeDefault />
      <Grid
        infiniteGrid
        cellSize={10}
        cellThickness={0.5}
        cellColor="#444444"
        sectionSize={50}
        sectionThickness={1}
        sectionColor="#666666"
        fadeDistance={500}
        fadeStrength={1}
      />
      <GizmoHelper alignment="bottom-right" margin={[80, 80]}>
        <GizmoViewport
          axisColors={["#f73b3b", "#3bf73b", "#3b3bf7"]}
          labelColor="white"
        />
      </GizmoHelper>
    </>
  );
}
