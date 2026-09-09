// @ts-check
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import next from "@next/eslint-plugin-next"; // 확인: 설치된 버전의 flat config export 이름

export default tseslint.config(
  { ignores: ["**/dist/**", "**/.next/**", "**/node_modules/**", "packages/sdk/src/generated/**"] },
  js.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked,
  {
    languageOptions: {
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
  },
  {
    files: ["apps/web/**/*.{ts,tsx}"],
    plugins: { "@next/next": next },
    rules: { ...next.configs["core-web-vitals"].rules },
  },
);
