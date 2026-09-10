import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// tsconfig.json 의 "@/*" -> "./*" 와 같은 별칭입니다(paths 는 보호 파일이라 여기서 맞춰 줍니다).
const rootDir = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": rootDir,
    },
  },
  test: {
    environment: "jsdom",
  },
});
