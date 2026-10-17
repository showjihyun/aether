"""`aether` CLI (spec 0006 D-1·D-2·D-8, plan 0006 MVP-1).

이 패키지는 **제품 코드를 import 하지 않습니다**(`.importlinter` AR-14). 공유하고 싶은 타입이
있어도 다시 적습니다 - HTTP 계약(`packages/sdk/openapi.json`)만 공유하는 것이 이 계약의 뜻이고,
`tests/test_aether_cli_contract_drift.py` 가 `contract.py` 의 경로가 그 파일에 실재하는지 봅니다.
HTTP 는 표준 라이브러리 `urllib` 만 씁니다(AR-5, spec D-1) - `pyproject.toml` 의 `dependencies`
는 비어 있어야 합니다.

모듈: `contract`(경로), `transport`(HTTP·SSE 바이트), `sse`(파싱), `output`(UTF-8 쓰기),
`commands`(명령 본문), `compose`(`aether up`), `main`(argparse·종료 코드).
"""
