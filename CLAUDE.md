@AGENTS.md

# Repository Map

## Harness

| 목적 | 명령 또는 문서 |
| --- | --- |
| 완료 선언 전 검증 | `./harness/scripts/verify.sh` → `.harness/verify.json` |
| 하네스 자기 점검 | `./harness/scripts/self-check.sh` (현재 verify 단계 전부가 이것입니다) |
| 계층별 평가 | `./harness/scripts/eval.sh` → `.harness/latest-eval.json` |
| 개선 후보 기록 | `./harness/scripts/improvement-log.sh new` → `improvement-log/` |
| 보호 목록 확인 | `./harness/hooks/guard-evaluation-tampering.sh --list` |
| 규칙 목록 | `harness/rules/RULES.md` |
| 기준서와 요소 인벤토리 | `harness/HARNESS.md` |
| 도입 다음 단계 | `harness/references/harness-adoption.md` |

## Project

- 진입점 지침: `AGENTS.md`
- 문서 지도: [docs/README.md](docs/README.md)
- 계층·의존 규칙: [docs/architecture.md](docs/architecture.md)
- 도메인 용어: [docs/domain.md](docs/domain.md)
- 현재 Phase: [docs/roadmap.md](docs/roadmap.md)
- 무엇을 왜 만드는가(활성 intent, intent → spec → plan): [intents/intent.md](intents/intent.md)
- 검증 단계 정의: `harness.config`
- 개선 후보: [improvement-log/README.md](improvement-log/README.md)
- 평가 세트: [evaluation/README.md](evaluation/README.md) (held-out 은 승격 판정 때만 엽니다)
- 하네스 출처: [PROVENANCE.md](PROVENANCE.md)

## 아직 없는 것

`apps/`, `packages/`, `infra/` 는 Phase 0 에서 생깁니다. 지금 그 경로를 참조하는 코드를 만들지 않습니다.

## 이 파일의 규칙

- 지식을 이 파일에 쌓지 않습니다. 설명이 필요하면 `docs/` 에 문서를 만들고 여기에는 경로만 둡니다.
- 작업 중에 이 파일을 편집해 규칙을 추가하지 않습니다. 반복 실패는 `improvement-log/` 에 후보로 남깁니다.
- 항목을 추가할 때는 대체·삭제할 항목을 함께 정합니다. 추가만 하는 편집은 받지 않습니다.
