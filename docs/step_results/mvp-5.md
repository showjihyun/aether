# MVP-5 — 측정할 문서와 양식, 그리고 측정자는 제가 될 수 없다는 사실

TTFSA(Time to First Successful Agent)를 **재는 도구**가 생겼습니다 — [`docs/quickstart.md`](../quickstart.md) 한 장과 [`docs/measurements/ttfsa-TEMPLATE.md`](../measurements/ttfsa-TEMPLATE.md). 숫자 자체는 **여기 없습니다.** 저장소를 처음 보는 사람 한 명이 필요하고(**H-4**), 에이전트는 저장소를 이미 알고 있어 그 사람이 될 수 없습니다. **R-12 는 그 기록이 커밋될 때** 참이 됩니다.

## 무엇이 생겼는가

| 조각 | 내용 |
| --- | --- |
| `docs/quickstart.md` | clone → `.env` → **소형 모델** 적재 → compose up → 키 발급 → `aether agent create`·`run` → `succeeded`. 선택 절로 화면(`:3000`)과 제품 모델 전환 |
| `docs/measurements/ttfsa-TEMPLATE.md` | 측정자·환경·**단계별 시각**·막힌 지점·총 시간. "그중 기다린 시간" 과 "그중 사람이 헤맨 시간" 을 나눠 적게 합니다 — 뒤의 숫자가 저장소의 마찰입니다 |
| `tests/scripts/test_quickstart.py` | 드리프트 7건. 그 문서가 가리키는 **경로·환경변수 키·모델 태그·`aether` 하위 명령**이 실재하는지, 양식이 다섯 칸을 묻는지 |
| `README.md`·`docs/README.md` | 머리말이 Quickstart 를 먼저 가리킵니다. 문서 지도에 두 장 추가 |

## 왜 그렇게 했는가

**측정이 대역폭을 재지 않게 했습니다(D-21, 사람 2026-10-19).** plan 의 Quickstart 경로는 `clone → 모델 적재 → up → 첫 Run` 이었는데 제품 기본 모델이 **17.7 GB** 입니다 — 그 다운로드 하나로 10분이 넘고 막힌 지점이 "다운로드" 한 줄로 끝납니다. 사람이 **소형 모델**(`qwen2.5:0.5b`, 379 MB)로 첫 Run 까지 가는 쪽을 골랐습니다. 대안은 둘이었습니다: 제품 모델 그대로(R-12 문장에 충실하나 네트워크가 숫자를 지배), `fake` 어댑터(다운로드 0 이지만 모델 없이 성공한 Run 을 "Successful **Agent**" 로 세는 것이 Outcome 3 과 어긋납니다).

**그 결정의 절반은 문서가 그 사실을 말하는 것**입니다. Quickstart 머리말과 양식이 "이 숫자는 **제품 모델로 쓸 수 있는 상태까지가 아니다**" 를 적습니다. 숫자를 맞추려고 조건을 바꾸는 것이 이 KPI 를 망치는 유일한 방법이고(EI-3), 그래서 조건을 **먼저 고정해 적었습니다.**

**드리프트 테스트를 더한 이유.** 이 저장소는 **문서가 없는 것을 요구한 일이 세 번** 있었습니다(`improvement-log/2026-10-18-005`). TTFSA 는 문서 하나로 측정되므로, 문서가 없는 파일·키·명령을 가리키면 재는 것이 "저장소의 마찰" 이 아니라 "문서의 거짓" 이 됩니다. 그 후보가 제안한 doc 쪽 검사의 **작은 판**입니다 — 명령이 동작하는지는 보지 않고 **가리키는 대상이 있는지**만 봅니다.

## 하네스 근거

| 줄 | 내용 |
| --- | --- |
| **요구** | spec 0006 **R-12**. 이 단위는 그 요구의 **도구까지**이고 판정은 사람의 측정입니다 |
| **결정** | **D-21**(소형 모델 경로) · **D-7**(TTFSA 는 사람 한 명) |
| **단계** | `links`(새 문서 둘의 링크 대상) · `harness-scripts`(드리프트 7건) |
| **증거** | PR 본문. red 는 두 문서가 없는 상태에서 7건이 각자 다른 이유로 실패한 기록. 변이 셋(경로 오타·모델 태그 변경·없는 환경변수 키) 전부 검출 |

## 정한 것과 다른 점

**`aether up` 을 쓰지 않습니다.** plan 은 "`clone → 모델 적재 → aether up → 첫 Run`" 이라고 적었지만 그 명령으로는 이 경로가 성립하지 않습니다 — `aether up` 은 `.env.example` 로 **임시 `.env`** 를 만들어 쓰므로(`compose.py` 의 `_with_temp_env`) `AETHER_MODEL_ADAPTER`·`AETHER_MODEL_ID` 를 바꿀 자리가 없습니다. Quickstart 는 `docker compose` 를 직접 씁니다. CLI 는 **첫 Run 을 실행하는 자리**(`agent create`·`run`·`runs get`)에서 그대로 쓰입니다 — 거기가 "HTTP 를 직접 치지 않고 제품을 쓴다" 는 MVP-1 의 주장이 사는 자리입니다.

**`-p aether-dev` 를 모든 명령에 박았습니다.** 프로젝트 이름이 다르면 **볼륨이 다르고** 받아 둔 모델이 스택에 보이지 않습니다. README 가 이미 경고하던 것인데, 처음 보는 사람이 가장 자주 밟을 돌이라 Quickstart 에서는 경고가 아니라 **모든 명령줄에 들어가 있습니다.**

## 남긴 것

**🔒 H-4 — 처음 보는 사람 1명.** 에이전트가 대신할 수 없는 유일한 단위입니다. 그 사람이 [양식](../measurements/ttfsa-TEMPLATE.md)을 `ttfsa-<날짜>.md` 로 복사해 채워 커밋하면 R-12 이고, 10분을 넘겼으면 **막힌 지점이 backlog 의 단위로 등록**됩니다. 숫자를 조정하지 않습니다.

**불일치 둘을 보고합니다**(이 단위에서 고치지 않았습니다 — spec 개정 8 에 적었습니다).

1. **`aether up` 이 `web` 을 띄우지 않습니다.** `apps/cli/src/aether_cli/compose.py` 의 `SERVICES` 에 없고, 그 자리 주석은 "`web` 은 화면 단위(MVP-2)가 들어올 때 더합니다" 인데 **MVP-2 는 2a~2e 로 끝났습니다.** 고치는 것이 한 줄이 아닌 이유: web 은 `AETHER_WEB_API_KEY` 가 필요하고 그 키는 **스택이 뜬 뒤에** 발급되므로 `aether up` 이 임시 `.env` 로 한 번에 띄우는 구조와 맞지 않습니다. 키 주입 순서를 함께 푸는 **별 단위**입니다.
2. **루트 `README.md` 가 "지금은 Phase 0" 이라고 적고 있었습니다.** 이것은 처음 보는 사람이 **가장 먼저** 읽는 문장이라 TTFSA 에 직접 걸립니다 — 정본(`docs/roadmap.md`: Phase 4 완료)에 맞춰 고쳤고 Quickstart 를 먼저 가리키게 했습니다.

## 관련 문서

- [../quickstart.md](../quickstart.md) — 이 단위가 만든 문서
- [../measurements/ttfsa-TEMPLATE.md](../measurements/ttfsa-TEMPLATE.md) — 측정 양식
- [../../specs/0006-mvp-integration.md](../../specs/0006-mvp-integration.md) — R-12, 2.7, D-7·D-21
- [mvp-1.md](mvp-1.md) — Quickstart 가 쓰는 CLI 를 만든 단위
- [README.md](README.md) — 단계 결과 모음
