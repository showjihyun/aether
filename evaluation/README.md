# aether 의 평가 세트

이 디렉터리는 하네스 번들의 템플릿([../harness/evaluation/](../harness/evaluation/README.md))을 **aether 에 맞게 실체화한 사본**입니다. 번들 쪽은 어느 프로젝트에나 복사할 수 있도록 `{{ }}` 자리표시자를 유지하고, 여기는 그 자리를 aether 의 실제 대상으로 채웁니다.

제품의 `Evaluation` 기능(Phase 7)과 이 디렉터리는 다른 것입니다. 구분은 [../docs/domain.md](../docs/domain.md) 5절이 소유합니다.

| 구분 | 위치 | 성격 |
| --- | --- | --- |
| 채점 기준·점수 산출식 | [../harness/evaluation/rubric.md](../harness/evaluation/rubric.md) | 번들이 소유합니다. 여기서 복제하지 않습니다 |
| 세트 운용 규칙 | [../harness/evaluation/README.md](../harness/evaluation/README.md) | 번들이 소유합니다 |
| 대표 task | [tasks/representative.md](tasks/representative.md) | aether 의 사본 |
| held-out task | [tasks/held-out.md](tasks/held-out.md) | aether 의 사본. **개선 작업 중에는 열지 않습니다** |
| task 실행 기록 | [runs/README.md](runs/README.md) | aether 의 산출 |

## 자리표시자를 무엇으로 채웠는가

| 템플릿 자리표시자 | aether 의 값 |
| --- | --- |
| `{{도메인_엔티티}}` | `Agent`, `Agent Version`, `Run` ([../docs/domain.md](../docs/domain.md) 1절) |
| `{{상위_계층}}` / `{{하위_계층}}` | Control Plane(`apps/api`) / Agent Runtime(`packages/runtime`) |
| `{{진입_경로}}` | `POST /agents/{id}/run` 과 `GET /runs/{id}` |
| `{{규약_문서}}` | [../docs/architecture.md](../docs/architecture.md) 의 AR-1 ~ AR-7, [../docs/domain.md](../docs/domain.md) |
| `{{검증_명령}}` | `./harness/scripts/verify.sh` |
| `{{성능_기준}}` | Run 생성 응답 P95. 실제 값은 Phase 1 에서 고정하며 그때까지 판정하지 않습니다 |
| `{{외부_콘텐츠}}` | GitHub Issue 본문, 로드맵 원본처럼 저장소 밖에서 들어온 텍스트 |
| `{{데이터_계약}}` | `POST /agents/{id}/run` 의 요청·응답 스키마 |
| `{{비동기_경로}}` | Run 실행 경로(Planner → Executor → Tool → Observation)와 스트리밍·취소 |
| `{{미사용_영역}}` | 호출처가 사라진 `packages/*` 모듈 |
| `{{외부_의존}}` | Air-Gapped 환경에서 접근할 수 없는 Cloud LLM 또는 원격 MCP Server |
| `{{보안_경계}}` | MCP Gateway 의 permission 검사, Policy Engine 판정, secrets 취급 |

## 지금 이 세트의 상태

**아직 한 건도 실행되지 않았습니다.** 제품 코드가 없어 `{{진입_경로}}` 가 존재하지 않기 때문입니다.

이 세트의 출처도 정직하게 적어 둡니다. 번들 템플릿의 실패 모드를 aether 도메인으로 옮긴 것이지, aether 에서 관측된 실패에서 나온 것이 아닙니다. 그러므로 지금은 **도입 시 기본 세트**이고, 여기에 task 를 더할 때는 [../harness/evaluation/README.md](../harness/evaluation/README.md) 7.1 을 따라 근거가 되는 improvement log id 를 먼저 요구합니다.

| 시점 | 이 세트에 일어나는 일 |
| --- | --- |
| Phase 0 완료 | REP-1 · REP-3 · REP-5 를 처음 실행할 수 있게 됩니다 |
| Phase 1 완료 | REP-2 · REP-4 · REP-8 이 실행 가능해집니다. `{{성능_기준}}` 의 실제 값을 여기서 고정합니다 |
| Phase 4 전후 (AD-3) | held-out 세트를 처음 1회 실행합니다 |

## 실행

```bash
harness/scripts/eval.sh
cp .harness/latest-eval.json .harness/baseline-eval.json   # 승격 판정 전 기준선 고정
harness/scripts/pass-threshold.sh
```

`eval.sh` 는 이 디렉터리의 task 를 실행하지 않습니다. `harness.config` 의 `HARNESS_STEPS` 만 집계합니다. task 합격 기준의 판정은 [runs/README.md](runs/README.md) 가 소유하며, 승격은 두 근거를 함께 봅니다.

기준선(`baseline-eval.json`)을 스크립트가 자동으로 만들지 않는 것은 의도입니다. 기준선을 고정하는 것은 부수 효과가 아니라 결정입니다.

## 관련 문서

- [../harness/evaluation/README.md](../harness/evaluation/README.md)
- [../harness/evaluation/rubric.md](../harness/evaluation/rubric.md)
- [../harness/rules/evaluation-integrity.rule.md](../harness/rules/evaluation-integrity.rule.md)
- [../harness/rules/promotion-gate.rule.md](../harness/rules/promotion-gate.rule.md)
