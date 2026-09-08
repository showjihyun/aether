# Agent Observability

이 문서는 "테스트는 다 통과했는데 실제로는 동작하지 않는다"는 상황을 만났을 때, 그리고 새 프로젝트에 하네스를 세우면서 에이전트가 무엇을 볼 수 있어야 하는지 정할 때 읽습니다. Agent Observability를 하네스의 1급 요소로 정의하고, 확보해야 할 관측 채널과 결손 진단 절차, 확보 우선순위를 규정합니다. 채널이 만들어내는 증거가 평가로 이어지는 경로는 [evaluation-layers.md](evaluation-layers.md)에 있습니다.

## 1. 정의와 원칙

Agent Observability는 **에이전트가 자신이 만든 결과를 스스로 관찰할 수 있는 능력**입니다. 하네스에서 이는 선택 요소가 아니라 1급 요소이며, 하네스 요소 인벤토리의 HE-11(scripts), HE-12(tools), HE-14(evaluation)에 걸쳐 구현됩니다.

| ID | 원칙 |
| --- | --- |
| OBS-P1 | 에이전트의 성능은 모델 성능만으로 결정되지 않습니다. 모델 성능 + 자기 결과 관측 능력으로 결정됩니다 |
| OBS-P2 | 사람에게 보이는 것이 에이전트에게는 보이지 않습니다. 사람은 IDE를 열거나 브라우저를 켜서 즉시 알아채지만, 에이전트에게는 그 채널이 연결되어 있지 않으면 존재하지 않는 정보입니다 |
| OBS-P3 | 관측되지 않는 실패는 수정되지 않습니다. 에이전트는 관측 가능한 신호에 대해서만 수렴합니다 |
| OBS-P4 | 관측 채널은 텍스트로 회수 가능해야 합니다. 사람이 눈으로만 확인할 수 있는 신호는 에이전트에게는 채널이 아닙니다 |
| OBS-P5 | 채널을 늘리기 전에, 이미 있는 채널의 출력이 에이전트에게 실제로 도달하는지 먼저 확인합니다. 로그가 파일에 남지 않으면 채널이 없는 것과 같습니다 |

OBS-P2의 결과로 다음 오해가 자주 생깁니다. 버튼이 화면 밖에 있어도, 클릭에 아무 반응이 없어도, Console Error가 계속 나고 있어도, 실제 API가 500을 반환하고 있어도, 단위 테스트는 전부 통과할 수 있습니다. 테스트 통과는 "구현이 의도대로 동작한다"의 증거가 아니라 "테스트가 검사하는 범위 안에서 동작한다"의 증거입니다.

## 2. 관측 채널 카탈로그

이 문서는 채널의 정의, 놓치는 실패, 우선순위만 소유합니다. 각 채널을 특정 언어·프레임워크에서 어떤 명령으로 확보하는지는 언어 팩의 `examples.md` 3절이 소유하며, 실제 단계 등록은 `language/<언어>/<kind>/harness.config.example` 을 `HARNESS_STEPS` 로 옮겨 적는 것으로 합니다. 아래 표의 "확보 방법" 은 도구에 얽매이지 않는 형태로 적었고, 스택 무관 도구(curl, psql, k6, gh)만 명령을 그대로 적었습니다.

| kind | 채널 | 언어 팩 예시 |
| --- | --- | --- |
| frontend | OBS-F1 ~ OBS-F5 | [../language/typescript/frontend/examples.md](../language/typescript/frontend/examples.md) |
| backend | OBS-B1 ~ OBS-B7 | [../language/java/backend/examples.md](../language/java/backend/examples.md), [../language/typescript/backend/examples.md](../language/typescript/backend/examples.md), [../language/python/backend/examples.md](../language/python/backend/examples.md) |

표에서 **감지된 스택의 행 하나만** 읽습니다. 스택과 kind 는 `harness/scripts/verify.sh --list` 로 확정합니다. 다른 팩의 예시는 이 프로젝트와 무관하므로 열지 않습니다.

### 2.1 Frontend 채널

| ID | 채널 | 무엇을 드러내는가 | 이것이 없을 때 놓치는 실패 | 확보 방법 |
| --- | --- | --- | --- | --- |
| OBS-F1 | Browser | 실제 렌더 결과와 사용자 조작에 대한 반응 | 빌드는 성공하는데 화면이 비어 있거나, 클릭해도 아무 일도 일어나지 않습니다 | 헤드리스 브라우저 러너(Playwright, Cypress 등)를 verify 의 `e2e` 단계로 등록합니다 |
| OBS-F2 | DOM | 요소의 존재, 접근 가능한 이름, 계산된 스타일, 화면 밖 배치 | 버튼이 뷰포트 밖에 있거나 다른 요소에 가려져 조작 불가능한 상태를 놓칩니다 | 브라우저 러너 안에서 대상 영역의 DOM 을 텍스트로 덤프해 `.harness/logs/dom.log` 로 저장합니다. 접근성 트리는 axe 계열 도구로 같은 자리에서 검사합니다 |
| OBS-F3 | Screenshot | 레이아웃 붕괴, 겹침, 잘림처럼 DOM만으로 판정하기 어려운 시각적 결과 | 요소는 전부 존재하지만 레이아웃이 무너져 사용할 수 없는 화면을 놓칩니다 | 러너 설정에서 실패 시 자동 캡처를 켜고 산출 경로를 `.harness/logs/` 아래로 모읍니다 |
| OBS-F4 | Console | 런타임 예외, 경고, 미처리 Promise 거부 | 화면은 그려지는데 상호작용 시점에 예외가 나서 이후 동작이 전부 죽는 상태를 놓칩니다 | 러너에서 console 이벤트를 수집해 파일로 남기고, 에러가 하나라도 있으면 종료 코드를 0이 아닌 값으로 만듭니다 |
| OBS-F5 | Network | 요청 URL, 상태 코드, 페이로드, 실패·재시도 | 프론트엔드는 정상인데 API가 401이나 500을 돌려주고 있는 상태를 놓칩니다 | 러너에서 응답을 가로채 `status >= 400` 을 집계하고 `.harness/logs/network.log` 로 남깁니다 |

### 2.2 Backend 채널

| ID | 채널 | 무엇을 드러내는가 | 이것이 없을 때 놓치는 실패 | 확보 방법 |
| --- | --- | --- | --- | --- |
| OBS-B1 | Integration Test | 실제 의존성(DB, 큐, 외부 API 대역)을 포함한 경로의 동작 | 각 단위는 통과하지만 조립하면 깨지는 결합 실패를 놓칩니다 | 통합 테스트를 단위 테스트와 분리해 별도 verify step(`integration`)으로 등록합니다. 실제 DB·큐는 컨테이너로 띄웁니다. 언어별 명령은 `language/<언어>/backend/harness.config.example` |
| OBS-B2 | curl | 배포된 엔드포인트의 실제 응답 코드·헤더·본문 | 테스트 환경에서만 동작하고 실제 기동 시 라우팅·직렬화·인증에서 깨지는 실패를 놓칩니다 | 스모크 체크를 스크립트화합니다. 예: `curl -sS -o /dev/null -w '%{http_code}' http://localhost:8080/health` |
| OBS-B3 | Database Query | 실제로 저장된 행, 제약 위반, 마이그레이션 반영 여부 | 애플리케이션은 성공을 반환했지만 데이터가 저장되지 않았거나 잘못된 형태로 저장된 실패를 놓칩니다 | 검증 쿼리를 스크립트로 고정합니다. 예: `psql -Atc "select count(*) from orders where status='PAID'"` |
| OBS-B4 | Application Log | 처리 경로, 예외 스택, 무시되고 있는 오류 | 요청은 200을 돌려주는데 내부에서 예외를 삼키고 있는 실패를 놓칩니다 | 로그를 파일로 고정하고 verify 단계에서 위험 패턴을 집계합니다. 예: `grep -cE '"level":"(ERROR|FATAL)"' .harness/logs/app.log` |
| OBS-B5 | Metric | 처리량, 오류율, 자원 사용량의 추세 | 기능은 동작하지만 오류율이 서서히 올라가는 열화를 놓칩니다 | 지표 엔드포인트를 조회해 임계값과 비교합니다. 예: `curl -sS http://localhost:8080/metrics \| grep http_server_errors_total` |
| OBS-B6 | Trace | 요청 하나가 지나간 구간별 지연과 실패 지점 | 느린 원인이 어느 구간인지 특정하지 못해 엉뚱한 곳을 최적화합니다 | 추적을 켜고 대표 요청의 span 요약을 텍스트로 회수합니다. 예: 수집기 조회 결과를 `.harness/logs/trace.log` 로 저장 |
| OBS-B7 | Load Test | 동시성 조건에서만 드러나는 경합, 커넥션 고갈, 타임아웃 | 단건으로는 통과하지만 부하에서 무너지는 실패를 놓칩니다 | 부하 시나리오를 verify의 선택 단계로 둡니다. 예: `k6 run load/smoke.js` |

### 2.3 공통 채널

| ID | 채널 | 무엇을 드러내는가 | 이것이 없을 때 놓치는 실패 | 확보 방법 |
| --- | --- | --- | --- | --- |
| OBS-C1 | exit code | 각 검증 단계의 성공·실패에 대한 기계 판정 | 출력에 에러 문구가 있는데도 명령이 0으로 끝나 통과로 집계되는 실패를 놓칩니다 | 모든 step에서 종료 코드를 기록합니다. 예: `cmd; echo "exit=$?"` 를 남기고 `verify.json` 의 `exit_code` 에 반영합니다 |
| OBS-C2 | structured log | 검증 결과를 키로 조회 가능한 형태 | 사람이 읽어야만 판정할 수 있어 에이전트가 자동으로 다음 행동을 정하지 못합니다 | `.harness/verify.json` 과 `.harness/latest-eval.json` 을 스키마대로 생성합니다. 예: `jq -r '.steps[] \| select(.status!="pass") \| .id' .harness/verify.json` |
| OBS-C3 | diff | 이번 변경이 실제로 건드린 범위 | 요청 범위 밖의 변경이 함께 섞여 들어간 것을 놓칩니다 | 변경 범위를 텍스트로 회수합니다. 예: `git diff --stat` 및 `git diff --name-only` |
| OBS-C4 | CI 결과 | 로컬과 다른 환경에서의 재현 여부 | 로컬에서만 통과하는 상태를 완료로 착각합니다 | CI 실행 결과를 조회 가능한 형태로 둡니다. 예: `gh run list --limit 1` 과 `gh run view --log-failed` |

## 3. 관측 결손 진단

"테스트는 다 통과했는데 동작하지 않는다"는 보고는 코드 결함 보고가 아니라 **채널 결손 보고**로 취급합니다. 다음 절차로 역추적합니다.

1. **현상을 관측 가능한 문장으로 다시 씁니다.** "동작하지 않는다"를 "무엇이, 어떤 조작 뒤에, 어떤 상태가 되는가"로 바꿉니다. 이 문장이 만들어지지 않으면 사람에게 재현 절차를 먼저 확보합니다.
2. **그 현상을 드러내는 채널을 2장 카탈로그에서 특정합니다.** 화면이 비어 있다면 OBS-F1/F3, 클릭 무반응이라면 OBS-F4, 데이터가 없다면 OBS-B3, 응답이 이상하다면 OBS-B2/F5입니다.
3. **그 채널이 verify에 연결되어 있는지 확인합니다.** `HARNESS_STEPS` 에 해당 step이 있는지, `.harness/verify.json` 의 `steps` 에 나타나는지 확인합니다.
4. **연결되어 있지 않다면 결손으로 확정합니다.** 코드를 고치기 전에 채널을 먼저 확보합니다. 채널 없이 고치면 고쳤는지 확인할 수 없습니다.
5. **연결되어 있는데도 통과했다면 채널이 무디게 연결된 것입니다.** 다음 세 가지를 점검합니다. 종료 코드가 실패를 반영하는가(OBS-C1). 출력이 파일로 남는가(OBS-P5). 판정 대상 범위가 실제 실패 지점을 포함하는가.
6. **결손을 improvement candidate로 승격합니다.** `harness_element` 는 대개 HE-5 또는 HE-11이고, `preferred_enforcement` 는 `test` 또는 `script` 입니다. `regression_check` 는 "채널을 붙이면 현재 코드에서 실패한다"로 씁니다. 절차는 [inner-outer-loop.md](inner-outer-loop.md)의 Outer Loop를 따릅니다.
7. **채널을 붙인 상태에서 코드를 고칩니다.** 순서를 바꾸지 않습니다.

이 절차에서 도출되는 candidate는 코드 수정이 아니라 관측 능력 추가입니다. 같은 증상이 두 번 반복되었는데 3단계에서 매번 "연결되어 있지 않다"가 나온다면, 그 프로젝트의 실제 병목은 구현 품질이 아니라 관측 결손입니다.

## 4. 채널 확보 우선순위

비용 대비 효과 순서입니다. 위에서부터 확보하고, 앞 단계를 건너뛰고 뒤 단계를 먼저 만들지 않습니다.

| 순위 | 채널 | 근거 |
| --- | --- | --- |
| 1 | OBS-C1 exit code + OBS-C2 structured log | 확보 비용이 가장 낮고, 다른 모든 채널이 이 위에 얹힙니다. 이것이 없으면 채널을 늘려도 에이전트가 판정하지 못합니다 |
| 2 | OBS-B1 Integration Test | 이미 있는 테스트 도구를 재사용하므로 추가 비용이 작고, 단위 테스트가 놓치는 결합 실패를 가장 많이 잡습니다 |
| 3 | OBS-B2 curl / OBS-B4 Application Log | 기동한 애플리케이션의 실제 응답과 삼켜진 예외를 드러냅니다. 스크립트 몇 줄로 확보됩니다 |
| 4 | OBS-C3 diff | 비용이 거의 없고 범위 이탈을 즉시 드러냅니다 |
| 5 | OBS-F4 Console / OBS-F5 Network | 프론트엔드에서 가장 흔한 무증상 실패를 잡습니다. 브라우저 러너를 도입하면 F1과 함께 확보됩니다 |
| 6 | OBS-F1 Browser / OBS-F2 DOM | 도입 비용이 있지만 프론트엔드에서는 이 채널 없이 완료를 선언할 수 없습니다 |
| 7 | OBS-C4 CI 결과 | 환경 차이를 드러냅니다. 로컬 채널이 갖춰진 뒤에 의미가 생깁니다 |
| 8 | OBS-B3 Database Query | 데이터 정합이 중요한 도메인에서는 순위를 3까지 올립니다 |
| 9 | OBS-F3 Screenshot | 시각적 판정이 필요한 화면이 있을 때 추가합니다. 판정에 사람이나 별도 평가자가 필요합니다 |
| 10 | OBS-B5 Metric / OBS-B6 Trace / OBS-B7 Load Test | 운영 관측 기반이 필요해 비용이 큽니다. 성능 계층을 평가에 넣기로 결정한 뒤 확보합니다 |

우선순위 조정은 도메인 특성에 따라 허용되지만, 1순위를 뒤로 미루는 조정은 허용하지 않습니다.

## 5. evaluation/ 의 behavior 계층과의 연결

평가 계층 6종(`correctness`, `architecture`, `quality`, `behavior`, `performance`, `subjective`) 중 `behavior` 는 **관측 채널이 있어야만 채점 가능한 계층**입니다. 관측 채널은 `behavior` 계층의 증거 공급원이며, 채널이 없으면 이 계층은 점수를 만들 수 없습니다.

| 채널 | 주로 공급하는 평가 계층 | `latest-eval.json` 의 `evidence` 예시 |
| --- | --- | --- |
| OBS-F1, OBS-F2, OBS-F3 | `behavior` | `.harness/logs/e2e.log` |
| OBS-F4, OBS-F5 | `behavior` | `.harness/logs/console.log`, `.harness/logs/network.log` |
| OBS-B1, OBS-B2, OBS-B3 | `behavior`, `correctness` | `.harness/logs/integration.log` |
| OBS-B4 | `behavior` | `.harness/logs/app.log` |
| OBS-B5, OBS-B6, OBS-B7 | `performance` | `.harness/logs/load.log`, `.harness/logs/trace.log` |
| OBS-C1, OBS-C2 | 전 계층의 판정 기반 | `.harness/verify.json` |
| OBS-C3 | `architecture`, `quality` | `.harness/logs/diff.log` |
| OBS-C4 | 전 계층의 재현성 확인 | CI 실행 링크 |

연결 규약은 다음과 같습니다.

- `behavior` 계층의 `deterministic` 이 `true` 인 항목은 반드시 위 채널 중 하나에서 나온 파일 경로를 `evidence` 로 가집니다. 근거 파일이 없는 `behavior` 점수는 무효로 취급합니다.
- 채널이 하나도 확보되지 않은 상태에서 `behavior` 가중치를 0이 아닌 값으로 두지 않습니다. 관측 없이 매긴 점수는 평가가 아니라 추정이며, 이는 [../rules/evaluation-integrity.rule.md](../rules/evaluation-integrity.rule.md)가 금지하는 조작에 해당합니다.
- `latest-eval.json` 의 `largest_failure` 가 `behavior` 로 반복해서 지목되면, 다음 개선 대상은 구현이 아니라 4장 우선순위표의 다음 채널입니다.
- 채널을 새로 확보하면 `evaluation/tasks/` 의 대표 과제에 그 채널로만 잡히는 시나리오를 하나 이상 추가합니다. 채널과 과제를 함께 늘려야 관측 능력이 평가에 반영됩니다.

## 관련 문서

- [evaluation-layers.md](evaluation-layers.md) — 6개 계층의 정의와 가중치 규약
- [inner-outer-loop.md](inner-outer-loop.md) — 결손을 candidate로 넘기는 Outer Loop 절차
- [harness-adoption.md](harness-adoption.md) — 채널을 언제 확보하는지의 도입 순서
- [harness-elements.md](harness-elements.md) — HE-11, HE-12, HE-14 정의
- [../evaluation/README.md](../evaluation/README.md) — 평가 실행과 증거 보관 규약
- [../evaluation/rubric.md](../evaluation/rubric.md) — `behavior` 채점 기준
- [../scripts/verify.sh](../scripts/verify.sh) — 채널을 step으로 등록하는 지점
- [../rules/evaluation-integrity.rule.md](../rules/evaluation-integrity.rule.md) — 관측 없는 점수의 취급
- [../language/README.md](../language/README.md) — 채널을 언어·kind 별 실제 명령으로 옮긴 팩
