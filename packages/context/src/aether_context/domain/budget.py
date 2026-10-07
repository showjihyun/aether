"""spec 0004 2.2, 2.9, D-6: 기본 예산 상수.

실제 값은 `AgentDefinition.context_budget_tokens`(D-5)가 있으면 그것, 없으면
`AETHER_CONTEXT_BUDGET_TOKENS`(기본 8192)입니다 — 환경변수를 읽는 것은 I/O 이므로
worker 의 조립(main.py)이 하고, 이 상수는 그 기본값과 같은 숫자를 테스트·조립 양쪽이
한 곳에서 참조하도록 둡니다(AR-9 — domain 은 I/O 를 하지 않습니다).
"""

from __future__ import annotations

DEFAULT_BUDGET_TOKENS = 8192
