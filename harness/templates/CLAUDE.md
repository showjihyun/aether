# CLAUDE.md 템플릿 (얇은 진입점)

이 파일은 프로젝트 루트에 `CLAUDE.md` 로 복사해 쓰는 진입점 템플릿입니다. CLAUDE.md 는 지식을 담는 백과사전이 아니라 프로젝트를 탐색하기 위한 지도이므로, 지침 본문은 [AGENTS.md](AGENTS.md) 한 곳에만 두고 여기서는 그것을 가져오는 라우팅만 남깁니다. 새 지시를 추가하고 싶어지면 이 파일이 아니라 [../rules/context-hygiene.rule.md](../rules/context-hygiene.rule.md) 의 판정 절차를 먼저 실행합니다. 아래 구분선부터가 복사 대상입니다.

---

@AGENTS.md

# Repository Map

## Harness

| 목적 | 명령 또는 문서 |
| --- | --- |
| 완료 선언 전 검증 | `./harness/scripts/verify.sh` → `.harness/verify.json` |
| 계층별 평가 | `./harness/scripts/eval.sh` → `.harness/latest-eval.json` |
| 개선 후보 기록 | `./harness/scripts/improvement-log.sh new` → `improvement-log/` |
| 규칙 목록 | `harness/rules/RULES.md` |

## Project

- 진입점 지침: `AGENTS.md`
- 아키텍처 문서: {{아키텍처_문서_경로}}
- 실행·개발 명령: {{개발_명령_문서_경로}}

## 이 파일의 규칙

- 지식을 이 파일에 쌓지 않습니다. 설명이 필요하면 문서를 만들고 여기에는 경로만 둡니다.
- 작업 중에 이 파일을 편집해 규칙을 추가하지 않습니다. 반복 실패는 `improvement-log/` 에 후보로 남깁니다.
- 항목을 추가할 때는 대체·삭제할 항목을 함께 정합니다. 추가만 하는 편집은 받지 않습니다.
