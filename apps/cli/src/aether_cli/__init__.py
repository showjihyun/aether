"""`aether` CLI (spec 0006 D-1·D-2, plan 0006 Wave 0~2) — 지금은 **빈 패키지**입니다.

왜 빈 채로 먼저 있는가: `.importlinter` 의 **AR-14**(CLI 는 제품 패키지를 import 하지
않는다)가 가리킬 모듈이 있어야 그 계약을 세울 수 있습니다. 계약을 먼저 세우면 첫 CLI
코드가 **처음부터** 위반할 수 없습니다 — Phase 4 가 AR-13 을 P4-1 앞에 둔 것과 같은
순서입니다(plan 0006 1절 문제 2).

명령과 HTTP 호출은 **MVP-1** 이 채웁니다. 그때도 이 패키지는 제품 코드를 import 하지
않고 `packages/sdk/openapi.json` 이 정한 계약만 씁니다.
"""
