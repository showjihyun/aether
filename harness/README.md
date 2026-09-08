# harness 번들

이 문서는 `harness/` 번들에 처음 들어올 때 읽습니다. 이 번들이 무엇을 담고 있는지, 어떤 파일을 어떤 순서로 읽어야 하는지, 아무것도 없는 프로젝트에서 무엇부터 도입해야 하는지를 안내하는 지도입니다. 규범적 기준은 여기가 아니라 [HARNESS.md](HARNESS.md)와 [rules/RULES.md](rules/RULES.md)에 있습니다.

## 이 번들은 무엇인가

이 번들은 **Self-Improving Harness 구축 킷**입니다. 에이전트가 작업하면서 발견한 실패, 테스트 결과, 리뷰 피드백을 다음 작업에서 더 잘하도록 개발 환경과 실행 방식에 반영하는 구조를, 문서·규칙·스크립트·스키마의 형태로 제공합니다.

- 개선 대상은 모델이 아니라 하네스입니다. 모델 weight를 바꾸는 방법은 다루지 않습니다.
- 특정 언어나 프레임워크에 고정되지 않습니다. 언어에 종속된 감지·기본 단계·보호 패턴·문서 예시는 `language/<언어>/` 팩이 소유하고, 스크립트는 팩으로 스택과 kind(frontend/backend)를 자동 감지하며 `harness.config` 로 재정의합니다.
- 산출물은 읽을거리가 아니라 실행 가능한 형태여야 합니다. lesson은 가능한 한 test, lint rule, architecture rule, hook, script 로 승격시킵니다.

## 파일 트리

```text
harness/
  README.md
  HARNESS.md
  SKILL.md
  agents/openai.yaml
  references/
    harness-elements.md
    maturity-levels.md
    inner-outer-loop.md
    agent-observability.md
    evaluation-layers.md
    generator-evaluator.md
    lesson-placement.md
    harness-adoption.md
    source-mapping.md
  rules/
    RULES.md
    lesson-placement.rule.md
    promotion-gate.rule.md
    untrusted-experience.rule.md
    loop-budget.rule.md
    evaluation-integrity.rule.md
    harness-change-control.rule.md
    context-hygiene.rule.md
    harness-gc.rule.md
  skills/
    harness-verify/SKILL.md
    harness-retro/SKILL.md
    harness-promote/SKILL.md
    harness-gardener/SKILL.md
    harness-score/SKILL.md
    harness-score/rubric.md
  subagents/
    harness-reviewer.md
    harness-evaluator.md
  scripts/
    verify.sh
    self-check.sh
    eval.sh
    pass-threshold.sh
    loop.sh
    improvement-log.sh
    protected-diff.sh
    lib/common.sh
    lib/detect-stack.sh
    harness.config.example
  hooks/
    README.md
    settings.hooks.json
    stop-verify-gate.sh
    guard-evaluation-tampering.sh
    detect-guarded-change.sh
    lib/guard-lib.sh
  improvement-log/
    README.md
    schema.md
    _template.yaml
    2026-08-09-001.example.yaml
  evaluation/
    README.md
    rubric.md
    tasks/representative.md
    tasks/held-out.md
    runs/_template.md
  templates/
    AGENTS.md
    CLAUDE.md
  language/
    README.md
    _template/  (README.md, lang.sh, backend/)
    typescript/
      README.md
      lang.sh
      frontend/  (harness.config.example, examples.md, improvement-log.example.yaml)
      backend/   (harness.config.example, examples.md, improvement-log.example.yaml)
    java/
      README.md
      lang.sh
      backend/   (harness.config.example, examples.md, improvement-log.example.yaml)
    python/
      README.md
      lang.sh
      backend/   (harness.config.example, examples.md, improvement-log.example.yaml)
    go/
      README.md
      lang.sh
      backend/   (harness.config.example)
    rust/
      README.md
      lang.sh
      backend/   (harness.config.example)
    ruby/
      README.md
      lang.sh
      backend/   (harness.config.example)
```

`go` 와 `rust` 는 예시 문서가 없는 최소 팩입니다. 팩 문서는 관측된 필요가 생겼을 때만 만듭니다.

| 경로 | 한 줄 설명 |
| --- | --- |
| `README.md` | 번들 지도. 무엇이 있고 어떤 순서로 읽는지 안내합니다. |
| `HARNESS.md` | 이 번들의 기준서. 하네스의 정의, 요소 인벤토리, 불변 원칙을 소유합니다. |
| `SKILL.md` | 진입점 스킬. 구축·감사·개선 세 모드 중 하나를 선택해 해당 문서만 읽게 합니다. |
| `agents/` | 에이전트 런타임별 인터페이스 선언 파일을 담습니다. |
| `references/` | 판단 근거가 되는 설명 문서입니다. 규칙 ID를 발급하지 않고 개념과 절차를 서술합니다. |
| `rules/` | 규범 문서입니다. `LP`, `PG`, `UT`, `LB`, `EI`, `CC`, `CX`, `GC` 여덟 개 prefix로 규칙 ID를 발급합니다. |
| `skills/` | 반복 절차를 스킬로 고정한 실행 문서입니다. verify, retro, promote, gardener, score 다섯 종입니다. |
| `subagents/` | 전문 판단을 분리해 맡기는 서브에이전트 정의입니다. 리뷰어와 평가자 두 종입니다. |
| `scripts/` | 하네스의 실행 표면입니다. verify, eval, loop, improvement-log 진입점과 공용 라이브러리를 담습니다. |
| `hooks/` | 반드시 실행되어야 하는 검사를 에이전트 재량 밖으로 밀어내는 hook 설정과 스크립트입니다. |
| `improvement-log/` | improvement candidate 기록의 스키마·템플릿·예시입니다. 실제 로그는 프로젝트 루트의 `improvement-log/` 에 쌓입니다. |
| `evaluation/` | 평가 계층 rubric과 representative / held-out 과제 목록입니다. |
| `templates/` | 대상 프로젝트에 배치할 `AGENTS.md`, `CLAUDE.md` 초안입니다. 작게 유지하는 것이 원칙입니다. |
| `language/` | 언어 팩입니다. 스택 감지, 기본 verify 단계, 평가 보호 패턴, 언어별 문서 예시처럼 특정 언어에 종속된 것만 담으며 `<언어>/{frontend,backend}/` 로 FE/BE 를 나눕니다. 코어는 언어를 알지 못합니다. |

## 읽는 순서

| 순서 | 문서 | 목적 |
| --- | --- | --- |
| 1 | [HARNESS.md](HARNESS.md) | 하네스의 정의, `HE-*` 요소 인벤토리, `HP-*` 불변 원칙을 확정합니다. |
| 2 | [SKILL.md](SKILL.md) | 지금 필요한 모드가 구축인지 감사인지 개선인지 선택합니다. |
| 3 | [references/inner-outer-loop.md](references/inner-outer-loop.md) | Inner Loop와 Outer Loop의 경계를 잡습니다. |
| 4 | [references/maturity-levels.md](references/maturity-levels.md) | 현재 프로젝트가 L0~L5 중 어디인지 판정합니다. |
| 5 | [rules/RULES.md](rules/RULES.md) | 적용될 규칙 ID 전체를 확인합니다. |
| 6 | 선택한 모드의 스킬 문서 | 실제 작업을 수행합니다. |

선택하지 않은 모드의 문서는 읽지 않습니다. 번들 전체를 순서대로 읽어야 하는 상황은 없습니다.

## 빠르게 시작하기

L5부터 만들 필요는 없습니다. L3와 L4를 제대로 만드는 편이 훨씬 중요하며, 다음 세 가지만 도입해도 에이전트를 사용하는 방식이 달라집니다. 아래 순서를 지킵니다. 앞 단계 없이 뒤 단계를 도입하면 검증되지 않은 경험이 그대로 쌓입니다.

### 1. 통합된 verify 명령

에이전트에게 명확한 feedback channel을 하나 만듭니다. compile, unit test, integration test, architecture test, lint, static analysis 를 명령 하나로 묶고 결과를 `.harness/verify.json` 으로 남깁니다.

```bash
harness/scripts/verify.sh
```

- 산출물: [scripts/verify.sh](scripts/verify.sh), [scripts/harness.config.example](scripts/harness.config.example), [language/README.md](language/README.md) 의 언어 팩, [skills/harness-verify/SKILL.md](skills/harness-verify/SKILL.md)
- 근거 문서: [references/agent-observability.md](references/agent-observability.md)

### 2. Improvement Log

작업이 끝날 때마다 "다음 작업을 위해 시스템에 남겨야 할 것은 무엇인가"를 한 번 묻고, 답을 `candidate` 상태의 YAML 한 건으로 남깁니다. 한 번 발생한 문제를 곧바로 영구 규칙으로 만들지 않습니다.

```bash
harness/scripts/improvement-log.sh new
```

- 산출물: [improvement-log/README.md](improvement-log/README.md), [improvement-log/schema.md](improvement-log/schema.md), [improvement-log/_template.yaml](improvement-log/_template.yaml), [scripts/improvement-log.sh](scripts/improvement-log.sh)
- 근거 문서: [references/lesson-placement.md](references/lesson-placement.md)

### 3. Harness Retrospective

쌓인 candidate 를 주기적으로 검토해 반복 가능한 실패를 골라내고, 회귀 검증을 통과한 것만 승격합니다. 여기까지 만들면 Outer Loop가 닫힙니다.

```bash
harness/scripts/eval.sh
```

- 산출물: [skills/harness-retro/SKILL.md](skills/harness-retro/SKILL.md), [skills/harness-promote/SKILL.md](skills/harness-promote/SKILL.md), [evaluation/README.md](evaluation/README.md), [scripts/eval.sh](scripts/eval.sh)
- 근거 문서: [references/harness-adoption.md](references/harness-adoption.md), [rules/promotion-gate.rule.md](rules/promotion-gate.rule.md)

## 런타임 산출 경로

| 경로 | 생성 주체 | 내용 |
| --- | --- | --- |
| `.harness/verify.json` | `scripts/verify.sh` | 검증 단계별 결과 |
| `.harness/latest-eval.json` | `scripts/eval.sh` | 계층별 평가 점수와 임계값 판정 |
| `.harness/loop-state.json` | `scripts/loop.sh` | 반복 횟수와 종료 조건 상태 |
| `improvement-log/` | `scripts/improvement-log.sh` | improvement candidate YAML (프로젝트 루트 기준) |

승격 판정에서는 `.harness/latest-eval.json` 을 `.harness/baseline-eval.json` 으로 복사해 기준선을 고정합니다. 이 파일은 스크립트가 자동으로 만들지 않으며, 절차는 [evaluation/README.md](evaluation/README.md)를 따릅니다.

## 출처

- 이 번들의 개념적 근거: "AI Agentic Coding의 Self-Improving Loop란 무엇인가", codex.epril.com, 2026-08-08
- 원문 문장과 이 번들 산출물의 대응 관계: [references/source-mapping.md](references/source-mapping.md)
