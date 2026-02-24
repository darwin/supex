import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@react-three/fiber": "@react-three/fiber/dist/react-three-fiber.esm.js",
      "@react-three/test-renderer":
        "@react-three/test-renderer/dist/react-three-test-renderer.esm.js",
    },
  },
  test: {
    environment: "happy-dom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["src/__tests__/setup.ts"],
  },
});
