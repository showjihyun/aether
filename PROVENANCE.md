# PROVENANCE

이 문서는 aether 저장소에 있는 것 중 **우리가 만들지 않은 것**이 어디서 왔는지, 그리고 가져오면서 무엇을 의도적으로 남기지 않았는지를 기록합니다. 출처를 적지 않으면 몇 달 뒤에 "이 규칙은 왜 있는가" 에 답할 수 없고, 답할 수 없는 규칙은 제거 판정도 할 수 없습니다([harness/rules/harness-gc.rule.md](harness/rules/harness-gc.rule.md)).

## 1. 하네스 번들

| 항목 | 값 |
| --- | --- |
| 출처 | https://github.com/showjihyun/harness-zzing |
| 가져온 커밋 | `b89299d7e042a6025181a34dc96117a277802ac9` (2026-09-06) |
| 가져온 날짜 | 2026-09-08 |
| 라이선스 | 원본 저장소의 `LICENSE` (MIT). 번들을 재배포할 때 함께 갑니다 |
| 대상 경로 | [harness/](harness/) 전체 |
| 변경 여부 | **무수정**. 번들 파일을 한 줄도 고치지 않았습니다 |

번들을 고치지 않은 것은 의도입니다. 고치기 시작하면 상류의 개선을 다시 가져올 수 없고, 그 순간 이 저장소가 하네스를 유지보수하게 됩니다. 프로젝트 고유 사정은 번들 밖(`harness.config`, `AGENTS.md`, `evaluation/`)에서 표현합니다.

번들에 고쳐야 할 것이 생기면 여기서 고치지 않고 `improvement-log/` 에 후보로 남긴 뒤 상류에 제안합니다.

## 2. 가져온 것과 그 자리

| 원본 경로 | 이 저장소의 자리 | 성격 |
| --- | --- | --- |
| `harness/` | [harness/](harness/) | 이식 가능한 번들. 무수정 사본 |
| `.claude/settings.json` | `.claude/settings.json` | 훅 등록. 무수정 |
| `.github/workflows/harness.yml` | `.github/workflows/harness.yml` | CI 게이트. 무수정 |
| `.github/CODEOWNERS` | `.github/CODEOWNERS` | 사람 검토 경로. 무수정 |
| `.gitignore` | `.gitignore` | 런타임 산출물 제외 목록 + aether 스택(node/python) 항목 추가 |

## 3. 가져오지 않은 것

| 원본 경로 | 왜 가져오지 않았는가 |
| --- | --- |
| `improvement-log/` (원본 10건) | 하네스 번들 자신에서 관측된 실패입니다. aether 의 실패가 아니므로 가져오면 근거 없는 lesson 이 됩니다(HP-5) |
| `evaluation/runs/` | 같은 이유. 다른 저장소의 판정 기록입니다 |
| `compare_resource/baseline/` | 계보가 다른 외부 프런트엔드 기준 번들입니다. aether 에서 쓸 근거가 아직 없습니다. 필요해지면 그때 근거와 함께 가져옵니다 |
| `README.md`, `README.ko.md` | 하네스 번들 자체를 설명하는 문서입니다. aether 의 README 는 제품을 설명해야 하므로 별도로 씁니다 |
| `harness.config` (원본) | 원본은 "하네스 번들이 성립하는가" 를 검사합니다. 구조는 그대로 따르되 대상은 aether 로 다시 적었습니다 |

## 4. aether 가 스스로 만든 것

| 경로 | 내용 |
| --- | --- |
| [AGENTS.md](AGENTS.md) | 진입점 지침. `harness/templates/AGENTS.md` 의 자리표시자를 aether 로 채운 것 |
| [CLAUDE.md](CLAUDE.md) | 진입 지도. `harness/templates/CLAUDE.md` 기반 |
| `harness.config` | aether 의 verify 단계 정의 |
| [docs/](docs/README.md) | 계층·용어·Phase. 에이전트의 탐색 대상 |
| [evaluation/](evaluation/README.md) | 번들 템플릿의 `{{자리표시자}}` 를 aether 도메인으로 실체화한 사본 |
| [improvement-log/](improvement-log/README.md) | 아직 비어 있습니다. 첫 항목은 실제로 실패가 관측될 때 생깁니다 |
| [intents/](intents/intent.md) | intent → spec → plan 파이프라인의 첫 단계. 출처는 6절 |

## 5. 로드맵 원본

| 항목 | 값 |
| --- | --- |
| 파일 | [Open_Hybrid_Enterprise_AI_OS_Final_Roadmap.md](Open_Hybrid_Enterprise_AI_OS_Final_Roadmap.md) |
| 출처 | 저장소 밖에서 생성된 초기 분석 문서(다른 LLM 산출물) |
| 신뢰 등급 | 사람이 채택한 **계획**. 하네스 규칙의 근거는 아닙니다 |
| 판정 근거 | [docs/roadmap.md](docs/roadmap.md) 1절, [harness/rules/untrusted-experience.rule.md](harness/rules/untrusted-experience.rule.md) |

이 구분을 두는 이유는 단순합니다. 계획 문서에 적힌 "항상 이렇게 하라" 는 문장이 검증 없이 하네스 규칙이 되면, 그 순간 하네스는 우리가 관측한 실패가 아니라 외부 문서를 반영하게 됩니다.

## 6. intent → spec → plan 파이프라인

| 항목 | 값 |
| --- | --- |
| 출처 | Anthropic, AI-Native SDLC Playbook — Requirements and Design (https://academy.claude.com/courses/ai-native-sdlc-playbook/requirements-and-design) |
| 보조 참고 | https://javaexpert.tistory.com/1823 (한국어 정리. 디렉터리 구조와 템플릿 항목의 근거) |
| 가져온 날짜 | 2026-09-08 |
| 대상 경로 | [intents/](intents/README.md) |

가져온 것과 바꾼 것은 다음과 같습니다.

| 원본 | aether 에서 |
| --- | --- |
| 파일 하나를 `intent.md` 로 부름 | 본문은 `intents/<NNNN>-<슬러그>.md`. 여러 건을 동시에 다루므로 번호를 붙입니다. 플레이북이 부르는 이름은 [intents/intent.md](intents/intent.md) 로 남겨 **활성 intent 를 가리키는 자리**로 씁니다. 본문을 복제하지 않습니다 |
| `intents/` `specs/` `plans/` 세 디렉터리 | `intents/` 만 지금 만듭니다. 나머지는 그 단계의 첫 산출물이 나올 때 만듭니다(AD-P2) |
| 템플릿 항목: Problem, Proposed Outcome, Affected Users, Affected Systems, Constraints, Open Questions | 그대로 채택하고 **Non-goals** 와 **근거** 두 항목을 더했습니다. 범위 확대(REP-6)와 근거 없는 계획을 막기 위한 자리입니다 |
| — | `Affected Systems` 를 [docs/architecture.md](docs/architecture.md) 의 계층 이름으로 강제했습니다. 자유 서술이면 문서와 코드가 다른 이름을 쓰게 됩니다 |
| — | intent 의 문장이 하네스 규칙으로 승격되지 않는다는 경계를 명시했습니다([intents/README.md](intents/README.md) "하네스와의 관계") |

## 7. 도입 이력

| 날짜 | 무엇을 |
| --- | --- |
| 2026-09-08 | 번들 도입(AD-1). verify 단계는 self-check 6개. 제품 코드 없음 |
| 2026-09-08 | `intents/` 추가. Intent 0001(Phase 0) 작성, 승인 대기 |
| 2026-09-08 | `intents/intent.md` 추가. 플레이북의 이름으로 활성 intent 를 가리키는 자리를 만들고, 진입점 문서(AGENTS.md·CLAUDE.md·docs/README.md)의 경로를 그쪽으로 옮겼습니다 |
