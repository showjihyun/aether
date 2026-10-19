# MVP-2d — 답변이 이벤트 스트림에 처음 나온다

Run 의 모델 호출이 `ModelGateway.complete` 를 쓰고 있었기 때문에 **모델의 답변 텍스트가 이벤트 스트림에 전혀 없었습니다.** `model.completed` 의 payload 는 `{finish_reason, usage}` 뿐이고, 텍스트를 담는 `model.delta` 는 spec 0002 2.7 이 "예약" 으로 적어 둔 자리였습니다 — `events.py` 가 "Phase 1 루프는 `complete` 만 쓰므로 이 이벤트를 발생시키지 않는다" 라고 적은 그대로입니다. MVP-2c 에서 대화 화면을 만들려다 그 사실이 드러났고(**D-16**), 이 단위가 그 예약을 끝냈습니다.

## 무엇이 생겼는가

- `execute_run` 의 모델 호출이 **`stream`** 입니다. 텍스트 조각이 도착하는 대로 `model.delta { text }` 를 발행하고, 조각을 모아 `complete` 가 주던 것과 같은 `ModelResponse` 를 만들어 **그 뒤 루프는 그대로** 돕니다 — `messages.append(assistant)`, `model.completed`, 도구 호출 분기, `task.finished` 가 전부 같습니다.
- 그 조각은 **다른 이벤트와 똑같이 저장됩니다**(**D-17**, 사람 2026-10-18). "저장하지 않는 이벤트" 라는 축을 만들지 않았으므로 spec 0002 2.7 의 재생 계약이 그대로이고, 새로고침하면 답변이 재생됩니다.
- `ModelDelta` 의 **종결 조각**이 `finish_reason`·`usage` 를 들고 옵니다. 어댑터 둘이 채웁니다 — fake 는 응답의 값을, `OpenAICompatibleGateway` 는 SSE 의 `choices[0].finish_reason` 과 `stream_options: {"include_usage": true}` 로 받은 `usage` 를.
- `packages/sdk/events.schema.json` 의 `model.delta` 설명을 고쳤습니다(payload 모델의 docstring 이 그 설명으로 나갑니다). 재생성했고 드리프트 0 입니다.

## 왜 그렇게 했는가

**`stream` 으로 바꾸는 것만으로는 계약이 후퇴합니다.** `stream` 의 `ModelDelta` 에는 `finish_reason`·`usage` 자리가 없었습니다. 그대로 바꾸면 `model.completed` 의 payload 가 **조용히 빈 값**이 됩니다 — 그것은 관측성의 후퇴이고, 게이트는 그걸 잡지 못합니다(그 payload 를 값까지 비교하는 테스트가 없었습니다). 그래서 포트의 종결 조각을 넓히는 일이 이 단위의 절반입니다. 지금은 `model.completed` 의 payload 가 **값까지** 고정돼 있습니다.

**조각을 낸 뒤의 실패는 재시도하지 않습니다**(D-17 의 따름 결정). 조각이 저장되는 이벤트이므로 재시도는 같은 답변을 타임라인에 **두 번** 쌓고 재생에서도 두 번 보이게 하며, 이미 사람이 읽은 글자를 되돌릴 방법이 없습니다. 조각을 내기 **전**에 실패한 경우는 지금까지와 똑같이 재시도합니다(`policy.model_retries`, 백오프, timeout·예산 분기 전부 그대로). 둘을 각각 테스트가 고정합니다.

**lease(spec 0002 C-13)가 스트림 소비 전체를 덮습니다.** 조각을 발행하는 중에 lease 를 잃으면 그 호출의 결과를 신뢰하지 않는다는 뜻이 유지돼야 하므로, 소비를 `_guarded_call` 안에서 합니다. 대가는 `EventSink.publish` 가 느릴 때 lease 창이 그만큼 길어지는 것입니다 — 측정하지 않았고 아래에 남깁니다.

**종결 조각 없이 끝난 스트림은 프로토콜 오류입니다.** 잘린 응답을 조용히 `"stop"` 으로 마감하면 "답변이 끝났다" 와 "연결이 끊겼다" 가 구별되지 않습니다. 위임이 제안했고 받았습니다(계획에 없던 결정입니다).

## 하네스 근거

| 줄 | 내용 |
| --- | --- |
| **요구** | spec 0006 **R-5** 로 가는 길의 절반 — 대화 화면(**MVP-2e**)이 그릴 텍스트가 이제 존재합니다. spec 0002 **R-12**(이벤트 스키마가 api 가 내보내는 것과 같다)는 재생성으로 유지됩니다 |
| **결정** | **D-16**(대화를 별 단위로) · **D-17**(조각을 저장한다 + 조각 뒤 실패는 재시도 없음) · spec 0002 **개정 12**(2.6·2.7 의 예약이 끝났습니다) |
| **단계** | `api-unit`(1105건) · `api-lint` · `api-typecheck` · `api-arch`(14 kept, 0 broken) · `web-typecheck`(스키마 드리프트 0) · `api-integration` · `e2e` |
| **증거** | PR 본문. red 는 새 테스트 14건 중 11건이 각자 다른 이유로 실패한 기록이고, 변이 **일곱**(재시도 조건·`usage` 전달·`seq` 증가·fake 종결 조각·`stream_options` 위치·종결 검사·`model.delta` 발행 자체)이 각각 다른 테스트에서 발화했습니다 |
| **후보** | 없음. 다만 `2026-10-18-005`(문서가 API 에 없는 값을 요구함)의 세 번째 사례가 이 단위를 만든 원인입니다 |

## 정한 것과 다른 점

**단위를 둘로 갈랐습니다** — 이 PR 은 런타임이고 화면은 **MVP-2e** 입니다(plan 개정 4). plan 이 이미 "한 PR 에 섞지 않는다" 를 적었고, 되돌릴 것이 서로 다릅니다: 런타임 쪽은 **모든 Run 의 이벤트 스트림**을 바꾸고, 화면 쪽은 `apps/web` 안에서 끝납니다.

**중계는 넓히지 않습니다**(**D-18**). plan 이 원래 "2c 의 대화가 `POST /agents/{id}/run` 을 더한다" 고 적었지만, 사람이 **서버 액션**을 골랐습니다 — 중계 허용 목록은 `GET` 넷 그대로이고 브라우저가 쓰기를 통과시키지 않습니다. 그 일은 MVP-2e 에 있습니다.

**묶기(coalescing)를 넣지 않았습니다.** 조각을 시간 간격으로 합치는 것은 "얼마로 묶나" 라는 **새 임계값**이고 그것은 사람이 소유합니다(EI-2). 이벤트 수가 문제가 되면 그때 정합니다.

**기존 테스트 하나의 fake 를 고쳤습니다** — `tests/test_policy.py` 의 `_TimeoutThenClockAdvanceGateway` 는 `stream` 이 `NotImplementedError` 였습니다. 그 테스트가 지키는 것("timeout 이고 잔여 예산이 0 이면 재시도 없이 `timed_out`")은 그대로이고, 기대값이 아니라 fake 의 `stream` 이 `complete` 와 같은 timeout 을 내게 했습니다.

## 남긴 것

- **이벤트 수.** fake 로 `"four is the answer"` 를 흘리면 `model.delta` 가 4건(어절당 하나)입니다. 실제 모델은 토큰 단위라 **답변 길이에 거의 비례**합니다 — 긴 답변 하나의 실제 건수는 사람이 모델로 한 번 보는 자리에 남겼습니다(plan 4절). 커지면 묶기를 그때 정합니다(위).
- **lease 창과 `publish` 지연.** 발행이 lease 창 안에 있으므로 sink 가 느리면 창이 길어집니다. 지금은 Redis Stream 한 번 쓰기이고 측정하지 않았습니다.
- **reasoning 은 여전히 이벤트가 없습니다**(D-19 로 `text` 와 분리된 값). 모아서 응답에 담는 것까지만 지금과 같습니다 — 타임라인에 내보내는 것은 이 단위의 결정이 아닙니다.
