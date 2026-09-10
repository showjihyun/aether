/** @type {import('dependency-cruiser').IConfiguration} */
module.exports = {
  // 반드시 저장소 루트에서 실행합니다: pnpm exec depcruise apps/web --config .dependency-cruiser.cjs
  // 아래 path 는 cwd 기준입니다. apps/web 안에서 돌리면 ^apps/web/ 이 매칭되지 않아 규칙이 발화하지 않습니다.
  forbidden: [
    {
      name: "ar1-web-imports-only-sdk",
      comment: "AR-1: apps/web knows only the HTTP contract via packages/sdk (docs/architecture.md)",
      severity: "error",
      from: { path: "^apps/web/" },
      to: { path: "^packages/(?!sdk/)" },
    },
    {
      name: "ar1-web-does-not-import-api",
      severity: "error",
      from: { path: "^apps/web/" },
      to: { path: "^apps/api/" },
    },
  ],
  options: {
    doNotFollow: { path: "node_modules" },
    tsPreCompilationDeps: true,
    tsConfig: { fileName: require("node:path").resolve(__dirname, "apps/web/tsconfig.json") },
    // 확인: pnpm 의 workspace 심링크가 실경로(packages/sdk/…)로 해석되는지 첫 실행에서 봅니다.
    // node_modules/@aether/… 로 보이면 to.path 에 "node_modules/@aether/(?!sdk)" 를 더합니다.
    enhancedResolveOptions: {
      exportsFields: ["exports"],
      conditionNames: ["import", "require", "node", "default"],
    },
  },
};
