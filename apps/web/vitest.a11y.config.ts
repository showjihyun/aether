import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// 기본 vitest.config.ts 와 같은 별칭·환경이고, 범위만 a11y 러너 하나입니다.
// `test:unit` 은 `*.test.*` 만 집으므로 `*.a11y.tsx` 는 거기서 돌지 않습니다.
const rootDir = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": rootDir } },
  test: {
    environment: "jsdom",
    include: ["a11y/**/*.a11y.tsx"],
    testTimeout: 30_000,
  },
});
