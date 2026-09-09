/** @type {import('dependency-cruiser').IConfiguration} */
// Deliberately-violating fixture for tests/arch/test_depcruise.py.
// Named depcruise.fixture.cjs (not `.dependency-cruiser.*`) so the harness
// protection guard does not block it -- only the real root config is guarded.
// Mirrors the AR-1 rule from the real .dependency-cruiser.cjs, scoped to this
// fixture tree. Run from this fixture's directory:
//   pnpm exec depcruise apps/web --config depcruise.fixture.cjs
module.exports = {
  forbidden: [
    {
      name: "ar1-web-imports-only-sdk",
      comment: "AR-1 (fixture): apps/web must not import packages/* directly",
      severity: "error",
      from: { path: "^apps/web/" },
      to: { path: "^packages/" },
    },
  ],
  options: {
    doNotFollow: { path: "node_modules" },
    tsPreCompilationDeps: true,
  },
};
