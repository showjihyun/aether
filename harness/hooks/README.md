# harness hooks

이 문서는 하네스의 규칙 중 문장으로만 존재하면 지켜지지 않는 것들을 실행 가능한 제약으로 승격시킨 hook 두 개를 설명합니다. hook 을 프로젝트에 붙이거나, 차단 메시지를 만났거나, hook 을 끄려고 할 때 읽습니다.

지시문은 지켜질 수도 있고 지켜지지 않을 수도 있습니다. hook 은 지켜지지 않으면 실행이 멈춥니다. 규칙 문서에 적힌 것 중 결정론적으로 판정할 수 있는 것은 여기로 옮깁니다. 이 디렉터리는 하네스 요소 인벤토리의 `HE-10` 에 해당합니다.

## 구성 파일

| 파일 | 역할 |
| --- | --- |
| `settings.hooks.json` | Claude Code `settings.json` 의 `hooks` 블록에 병합할 JSON 조각 |
| `stop-verify-gate.sh` | Stop hook. 검증 없이 작업을 끝내는 것을 차단 |
| `guard-evaluation-tampering.sh` | PreToolUse hook. 평가·게이트 규정 파일의 변경을 차단 |
| `detect-guarded-change.sh` | PostToolUse hook. 보호 파일이 실제로 바뀌었는지 사후에 검출 |
| `lib/guard-lib.sh` | 두 hook 이 공유하는 보호·경고 패턴, 경로 판정, 감사 기록. source 전용 |
| `../language/<언어>/lang.sh` | 언어별 차단·경고 패턴. guard hook 이 로드된 **모든** 팩의 것을 감지 결과와 무관하게 코어 목록에 합칩니다 (아래 "보호 목록" 절) |

## 각 hook 이 강제하는 것

### stop-verify-gate.sh

에이전트가 "다 했습니다"라고 선언하는 순간에 `.harness/verify.json` 을 확인합니다. 검증이 실행되지 않았거나, 일부 단계만 돌았거나, 검증한 뒤 파일이 바뀌었거나, `status` 가 `pass` 가 아니면 종료를 차단하고 다음 조치를 stderr 로 돌려줍니다.

| 판정 | 결과 |
| --- | --- |
| `stop_hook_active` 가 `true` | exit 0 (무한 루프 방지) |
| `HARNESS_SKIP_STOP_GATE=1` | exit 0 + 우회 사실을 stderr 에 기록 |
| `.harness/verify.json` 없음 | exit 2, 종료 차단 |
| `status` 가 `pass` 가 아님 | exit 2, 실패한 step id 와 함께 차단 |
| `partial` 이 `true` | exit 2, 실행한 단계 수와 정의된 단계 수를 함께 차단 |
| `finished_at` 이 없음 | exit 2, 신선도 근거가 없는 옛 파일이므로 차단 |
| `tree` 가 현재 작업 트리 지문과 다름 | exit 2, 검증 이후 변경이 있으므로 차단 |
| 위 어느 것도 아님 | exit 0 |

`status` 하나만 보면 두 가지 우회가 열립니다. `verify.sh --only <id>` 로 한 단계만 돌린 결과가 전량 통과와 구별되지 않고, 며칠 전의 `pass` 가 오늘의 종료를 통과시킵니다. `partial`·`finished_at`·`tree` 세 키가 그 둘을 각각 닫습니다.

`tree` 는 **작업 트리에 실제로 존재하는 파일의 "경로 + 내용 해시" 목록**을 정렬해 해시한 값입니다. `HEAD` 를 쓰지 않습니다.

| 대상 | 어떻게 구하는가 |
| --- | --- |
| 추적 파일 (수정 없음) | `git ls-files -s` 의 index blob 해시를 그대로 씁니다. 파일을 읽지 않아 빠릅니다 |
| 추적 파일 (작업 트리가 index 와 다름) | `git hash-object` 로 실제 내용을 해시합니다 |
| 미추적 파일 | `git hash-object` 로 내용을 해시합니다 |
| 삭제된 파일 | 목록에서 빠집니다. 줄이 사라지는 것으로 삭제가 드러납니다 |

`HEAD` 기준 표현(`rev-parse HEAD`, `status --porcelain`, `diff HEAD`)을 쓰지 않는 이유가 있습니다. 그 셋은 커밋만 해도 값이 전부 달라집니다. 커밋 전은 `HEAD=A` + `M` 목록 + 변경 내용이고 커밋 후는 `HEAD=B` + 빈 status + 빈 diff 인데, **파일 내용은 같습니다.** 그래서 검증 → 커밋 → 종료 라는 정상 순서가 항상 차단되었습니다. `git add` 도 같은 이유로 값을 바꿨습니다. 근거: `improvement-log/2026-09-05-003`.

index 는 커밋으로 바뀌지 않으므로 이 정의는 커밋·stage 에 불변이고, 내용이 바뀌면 반드시 달라집니다.

| 동작 | 지문 |
| --- | --- |
| 파일 수정 / 재수정 / 미추적 추가·수정 / 추적 파일 삭제 | **바뀝니다** |
| `git add`, `git commit` (삭제의 stage·commit 포함) | 그대로입니다 |
| 내용을 원래대로 되돌림 | 원래 값으로 돌아옵니다 |

**비용**: 추적 파일 125개 약 0.44초, 1000개 0.57초, 5000개 2.2초(더티 20개면 3.1초)입니다. hook 예산 30초 안이지만 파일 수와 더티 파일 수에 비례합니다. 더티 파일 하나마다 `git hash-object` 프로세스가 하나 뜨므로, 아주 큰 저장소에서 예산에 닿으면 `--stdin-paths` 로 묶는 것이 다음 수순입니다.

git 저장소가 아니거나 해시 도구가 없으면 `tree` 가 빈 문자열이 되고 그때는 신선도를 판정하지 않습니다.

`lib/common.sh` 의 `harness_tree_fingerprint` 가 정본이고 hook 은 `common.sh` 없이도 동작해야 하므로 같은 폴백을 자체 보유합니다. **두 구현의 입력이 다르면 지문이 영원히 어긋나 모든 종료가 막힙니다.** 한쪽을 고치면 반드시 다른 쪽도 고칩니다.

### guard-evaluation-tampering.sh

`Edit` / `Write` / `MultiEdit` / `NotebookEdit` 호출 직전에 대상 경로를 보호 목록과 대조합니다. lint 규칙을 끄거나, 임계값을 낮추거나, 평가 결과 파일을 직접 고쳐 통과시키는 경로를 막습니다.

| 판정 | 결과 |
| --- | --- |
| 차단 목록 일치 | exit 2, 도구 호출 차단 + 사유와 절차 안내 |
| 차단 목록 일치 + `HARNESS_ALLOW_GUARDED_EDIT=1` | exit 0 + 우회 사실을 stderr 에 기록 |
| 경고 목록 일치 | exit 0 + 경고를 stderr 에 기록 |
| 어느 목록에도 없음 | exit 0, 출력 없음 |

### 셸 명령도 봅니다

`file_path` 만 검사하면 가드가 `Edit` 계열에만 걸리고 셸 한 줄로 그대로 우회됩니다.

```bash
printf '{"status":"pass"}' > .harness/verify.json    # 검증 없이 게이트 통과
sed -i 's/THRESHOLD=90/THRESHOLD=0/' harness.config  # 합격선 무력화
```

그래서 `Bash` 도구도 matcher 에 등록하고 `tool_input.command` 를 봅니다. 읽기는 막지 않습니다. `cat`, `grep`, `git diff` 로 보호 파일을 보는 것은 정상 작업입니다. **변경 구문이 실제로 겨냥하는 대상**만 뽑아 대조합니다.

보는 구문은 리다이렉션, `tee`, 제자리 편집, 그리고 복사·이동 계열(`cp`, `mv`, `install`, `truncate`, `dd`, `rsync`, `ln`)입니다. 마지막 묶음은 실제로 뚫린 뒤에 더했습니다. 한 세션에서 `cp` 로 보호 파일 10건이 차단 없이 덮어써졌습니다.

**이 목록은 닫히지 않습니다.** `python -c`, `node -e`, `make`, 임의 스크립트는 여전히 통과합니다. `cp` 를 막으면 `mv` 가, `mv` 를 막으면 인터프리터가 남습니다. `bash` 를 허용하는 순간 전부 허용한 것입니다. 열거를 늘려 닫으려 하지 마십시오. 남는 경로는 사후 검출과 CI 가 담당합니다. 여기서 하는 일은 **가장 손쉬운 지름길을 막고 판단 지점을 만드는 것**까지입니다.

반대 방향의 오탐도 남습니다. 이 검사는 명령 문자열을 봅니다. heredoc 본문이나 인용부호 안에 보호 경로가 등장하기만 해도 걸릴 수 있습니다. 실제로 이 문단을 쓰는 명령이 그 이유로 두 번 차단되었습니다. 근거: improvement-log/2026-09-05-004.

| 검사하는 대상 | 예 |
| --- | --- |
| 리다이렉션 대상 | `> 파일`, `>> 파일` (`2>&1` 은 대상이 `&1` 이라 걸리지 않습니다) |
| `tee` 의 인자 | `tee 파일`, `tee -a 파일` |
| 제자리 편집의 인자 | `sed -i`, `perl -pi` 가 있으면 경로 같은 토큰 전부 |

명령 전체에서 경로를 찾지 않는 이유는 오탐 때문입니다. `bash harness/scripts/verify.sh >/dev/null` 은 보호 파일을 *실행*할 뿐인데 그렇게 하면 걸립니다.

**이것은 완전한 셸 파서가 아닙니다.** 변수 확장, `eval`, base64, 별도 스크립트 작성 후 실행 등으로 우회할 수 있습니다. 이 검사는 실수와 손쉬운 지름길을 막는 것이지 적대적 회피를 막지 못합니다. 평가 무결성의 마지막 보루는 hook 이 아니라 사람의 리뷰와 `improvement-log` 의 기록입니다.

### hook 명령에 `bash` 를 붙입니다

`settings.hooks.json` 은 hook 명령을 `bash "$CLAUDE_PROJECT_DIR/..."` 형태로 씁니다. 스크립트 경로만 적으면 실행 비트가 없는 체크아웃에서 exit 126 이 나고, Windows 처럼 shebang 을 따르지 않는 환경에서는 실행 자체가 실패합니다. 두 경우 모두 종료 코드가 0 도 2 도 아니어서 **차단 없음으로 읽히고 가드가 조용히 사라집니다.**

차단 목록과 경고 목록은 두 층으로 이루어집니다.

| 층 | 위치 | 담는 것 |
| --- | --- | --- |
| 코어 | [`lib/guard-lib.sh`](lib/guard-lib.sh) 의 `HARNESS_PROTECTED_PATTERNS`, `HARNESS_WARN_PATTERNS` | `harness.config`, `harness/evaluation/*`, `harness/rules/*`, `harness/language/*/lang.sh` 처럼 언어와 무관한 하네스 자체의 파일. 프로젝트 고유 추가분도 여기 적습니다 |
| 언어 팩 | `harness/language/<언어>/lang.sh` 의 `HARNESS_LANG_<언어>_PROTECTED_PATTERNS` 등 | lint·타입·테스트 러너·아키텍처 규칙 설정처럼 언어에 종속된 파일 |

**보호 목록은 스택 감지 결과에 의존하지 않습니다.** hook 은 로드된 **모든** 팩의 패턴(공통 + 모든 kind)을 코어 목록에 합칩니다. Java 저장소에서도 `tsconfig.json` 이 차단되고, 스택을 감지하지 못한 저장소에서도 `checkstyle.xml` 과 `ruff.toml` 이 차단됩니다.

감지에 의존하면 다음 상황에서 보호가 조용히 사라지기 때문입니다.

| 상황 | 감지 의존 시 | 지금 |
| --- | --- | --- |
| 지원하지 않는 언어의 저장소(스택 미감지) | 언어별 보호 전면 해제 | 전부 유지 |
| monorepo (`pom.xml` 루트 + `frontend/package.json`) | `frontend/tsconfig.json` 무방비 | 차단 |
| polyglot 단일 루트 (Django + React) | 먼저 감지된 한 언어만 보호 | 둘 다 보호 |
| kind 오판정 (Playwright 로 API 만 도는 Nest) | `playwright.config.*` 무방비 | 차단 |
| 루트에 빈 `package.json` 주입 | Java·Python 보호가 통째로 사라짐 | 영향 없음 |

패턴 이름은 언어 간에 겹치지 않으므로(Java 저장소에 `tsconfig.json` 은 없습니다) 합집합의 오탐 비용은 없습니다. `HARNESS_STACK` 과 `HARNESS_KIND` 는 `verify.sh` 의 기본 단계 선택에만 영향을 주고 보호 목록은 바꾸지 않습니다. 현재 프로젝트에서 합쳐진 목록은 다음으로 확인합니다.

```bash
./harness/hooks/guard-evaluation-tampering.sh --list
```

패턴 매칭 규칙은 두 가지입니다. `/` 가 없는 패턴은 경로 전체와 파일명 양쪽에 대해 검사하므로 `tsconfig.json` 이 `apps/web/tsconfig.json` 도 잡습니다. `/` 가 있는 패턴은 경로 전체와 **하위 경로 접미사** 양쪽에 대해 검사하므로 `harness/hooks/*` 가 `tools/harness/hooks/x.sh` 도 잡습니다. 하네스를 하위 디렉터리에 벤더링해도 가드가 자기 자신을 지킵니다. Windows 역슬래시 경로는 슬래시로 정규화한 뒤 대조합니다.

각 언어 팩이 어떤 파일을 왜 보호하는지는 `harness/language/<언어>/README.md` 와 `<kind>/examples.md` 4절이 설명합니다.

### hook 은 harness.config 를 읽지 않습니다

`harness.config` 는 bash 파일입니다. hook 이 그것을 `source` 하면 가드 프로세스 안에서 임의 명령이 실행되고, `exit 0` 한 줄만으로 가드 전체가 무력화됩니다. `harness.config` 자체는 차단 목록에 있지만 hook 은 파일 편집 도구만 가로채므로 Bash 로 쓰는 경로가 남습니다. 그래서 hook 은 설정 파일을 읽지 않고 환경변수만 봅니다. `verify.sh` 와 `loop.sh` 는 `HARNESS_STEPS` 가 필요하므로 계속 읽습니다.

### 팩이 계약을 어기면 시끄럽게 실패합니다

`language/<언어>/lang.sh` 가 필수 함수를 빠뜨리거나 패턴 변수를 배열이 아닌 값으로 선언하면, 로더가 그 팩을 비활성화하고 사유를 stderr 에 남깁니다. 조용히 넘어가면 그 언어의 보호가 사라진 사실이 아무 데도 드러나지 않기 때문입니다. 팩 하나의 문법 오류는 다른 팩과 코어로 번지지 않습니다.

```bash
./harness/hooks/guard-evaluation-tampering.sh --list   # 계약 위반이 있으면 목록 앞에 출력됩니다
```

## 어떤 규칙을 승격시킨 것인가

hook 은 규칙 문서의 조항 중 결정론적으로 판정 가능한 부분만 옮긴 것입니다. 조항 번호는 각 규칙 문서의 규칙 표에서 확인합니다.

| hook | 승격시킨 규칙 | 근거 문서 |
| --- | --- | --- |
| `stop-verify-gate.sh` | 검증 없이 작업을 완료로 선언하지 않는다 | [rules/loop-budget.rule.md](../rules/loop-budget.rule.md) |
| `stop-verify-gate.sh` | 검증되지 않은 결과를 승격 대상으로 올리지 않는다 | [rules/promotion-gate.rule.md](../rules/promotion-gate.rule.md) |
| `guard-evaluation-tampering.sh` | 평가 기준·임계값·lint 규칙을 완화해 점수를 얻지 않는다 (EI 규칙군) | [rules/evaluation-integrity.rule.md](../rules/evaluation-integrity.rule.md) |
| `guard-evaluation-tampering.sh` | 하네스 변경은 한 번에 하나씩, 검토를 거쳐 적용한다 (CC 규칙군) | [rules/harness-change-control.rule.md](../rules/harness-change-control.rule.md) |

`guard-evaluation-tampering.sh` 는 EI 규칙군을 문장에서 실행 가능한 제약으로 옮긴 것입니다. "Lint Errors = 0" 이라는 목표를 가장 싸게 달성하는 방법은 lint 규칙을 끄는 것이므로, 그 경로를 사람의 주의력이 아니라 hook 으로 막습니다.

## settings.json 병합 방법

`settings.hooks.json` 은 완결된 설정 파일이 아니라 `hooks` 블록만 담은 조각입니다. 다음 중 한 곳에 병합합니다.

| 위치 | 적용 범위 |
| --- | --- |
| `.claude/settings.json` | 저장소 전체(팀 공유, 커밋 대상) |
| `.claude/settings.local.json` | 개인 설정(커밋하지 않음) |
| `~/.claude/settings.json` | 사용자 전역 |

병합 결과는 다음 형태입니다.

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit|NotebookEdit",
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/harness/hooks/guard-evaluation-tampering.sh",
            "timeout": 10
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "$CLAUDE_PROJECT_DIR/harness/hooks/stop-verify-gate.sh",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

`jq` 가 있으면 다음처럼 병합합니다.

```bash
jq -s '.[0] * .[1]' .claude/settings.json harness/hooks/settings.hooks.json > .claude/settings.json.new
mv .claude/settings.json.new .claude/settings.json
```

이미 `hooks.PreToolUse` 항목이 있다면 `*` 병합은 배열을 통째로 대체합니다. 기존 항목이 있는 프로젝트는 배열에 원소를 직접 추가합니다.

절대 경로 대신 `$CLAUDE_PROJECT_DIR` 를 씁니다. 클론 위치가 달라도 동작해야 합니다. 실행 권한이 없으면 hook 은 조용히 실패하므로 병합 후 한 번 확인합니다.

```bash
chmod +x harness/hooks/*.sh
```

설정을 바꾼 뒤에는 세션을 다시 시작하거나 `/hooks` 로 등록 상태를 확인합니다.

## 동작 확인

hook 은 stdin 으로 JSON 을 받으므로 직접 실행해 확인할 수 있습니다.

```bash
# 코어 목록: 어느 스택에서든 차단되어야 합니다(exit 2)
echo '{"tool_name":"Edit","tool_input":{"file_path":"harness/evaluation/rubric.md"}}' \
  | ./harness/hooks/guard-evaluation-tampering.sh; echo "exit=$?"

# 언어 팩 목록: 스택과 무관하게 차단되어야 합니다(exit 2)
echo '{"tool_name":"Edit","tool_input":{"file_path":"eslint.config.mjs"}}' \
  | ./harness/hooks/guard-evaluation-tampering.sh; echo "exit=$?"

# 하위 디렉터리와 벤더링 배치도 차단되어야 합니다(exit 2)
echo '{"tool_name":"Edit","tool_input":{"file_path":"frontend/tsconfig.json"}}' \
  | ./harness/hooks/guard-evaluation-tampering.sh; echo "exit=$?"

# 검증 결과가 없으면 차단되어야 합니다(exit 2)
echo '{"stop_hook_active":false}' | ./harness/hooks/stop-verify-gate.sh; echo "exit=$?"

# 루프 방지 경로는 항상 통과합니다(exit 0)
echo '{"stop_hook_active":true}' | ./harness/hooks/stop-verify-gate.sh; echo "exit=$?"
```

두 스크립트 모두 `--help` 를 지원하고, `jq` 가 없으면 순수 bash 폴백으로 같은 판정을 냅니다.

## 무한 루프 방지 장치

Stop hook 이 종료를 막으면 에이전트는 작업을 계속하다가 다시 종료를 시도합니다. 이때 hook 이 같은 이유로 또 막으면 세션은 끝나지 않습니다. 다음 세 가지로 막습니다.

1. **`stop_hook_active` 확인.** 이 hook 때문에 이미 한 번 종료가 막힌 상태로 재진입하면 `stop-verify-gate.sh` 는 아무 판정도 하지 않고 exit 0 합니다. 판정은 한 번의 종료 시도당 한 번만 일어납니다.
2. **`timeout` 설정.** `settings.hooks.json` 의 `timeout` 으로 hook 자체가 매달리는 것을 막습니다.
3. **명시적 우회 변수.** 검증이 구조적으로 불가능한 상황에서는 `HARNESS_SKIP_STOP_GATE=1` 로 한 번 빠져나갑니다. 우회 사실은 항상 stderr 에 남습니다.

`guard-evaluation-tampering.sh` 는 상태를 바꾸지 않고 판정만 하므로 재진입 문제가 없습니다.

### detect-guarded-change.sh

사전 차단은 명령 문자열을 보고 "바꿀 것 같은가" 를 **추정**합니다. 그 추정은 두 방향으로 틀립니다.

| 방향 | 예 |
| --- | --- |
| 미탐 | `cp new old`, `mv`, `python -c`, `make`, 임의 스크립트. 열거로는 닫히지 않습니다 |
| 오탐 | 인용부호 안에 보호 경로를 언급한 명령, heredoc 본문의 코드 |

`bash` 를 허용하는 순간 전부 허용한 것이고, 쓰기가 hook 이 읽을 수 없는 프로그램 안에서 일어날 수도 있습니다. 그래서 **추정을 보완하는 관측**을 둡니다. 이 hook 은 도구 호출이 끝난 뒤 보호 파일의 내용 해시를 `.harness/guard-snapshot.tsv` 와 비교합니다. 무엇이 바꿨는지와 무관하게 바뀐 사실이 드러나므로 미탐이 없고, 명령을 파싱하지 않으므로 오탐도 없습니다.

대신 **막지 못합니다.** PostToolUse 는 이미 일어난 일을 되돌리지 못하므로 exit 0 만 씁니다. 사전 차단과 사후 검출은 대체 관계가 아니라 짝입니다. 하나는 강제력이 있고 관측이 새며, 다른 하나는 관측이 완전하고 강제력이 없습니다.

| 항목 | 값 |
| --- | --- |
| 감시 대상 | 코어 보호 패턴 + 로드된 모든 언어 팩 패턴. `.harness/*` 는 스크립트가 매 실행 다시 쓰므로 제외 |
| 스냅숏 | `.harness/guard-snapshot.tsv`. 없으면 만들고 아무것도 보고하지 않습니다 |
| 기록 | `.harness/guard-events.log` |
| 비용 | 이 저장소에서 감시 39개, 정상 상태 0.72초. 팩 병합 결과는 `.harness/guard-patterns.cache` 에 캐시하고 `lang.sh` 가 더 새로울 때만 다시 만듭니다 |
| 확인 | `harness/hooks/detect-guarded-change.sh --status` |

git 저장소가 아니면 아무것도 하지 않습니다. 해시를 비교할 기준이 없기 때문입니다.

### 감사 기록

`.harness/guard-events.log` 는 탭 구분이며 `시각 / HEAD / 종류 / 경로 / 상세` 다섯 열입니다. 종류는 `block`, `bypass`, `warn`, `change` 입니다.

이것이 없으면 `HARNESS_ALLOW_GUARDED_EDIT=1` 우회가 stderr 한 줄로 사라지고, 대표 task REP-3 의 합격 기준인 "guard hook 이 차단 메시지를 낸 흔적이 없음" 을 관측할 수단이 없습니다. 기록은 승인을 막지 않습니다. 승인이 있었다는 사실을 남길 뿐입니다.

로그는 런타임 산출물이라 커밋하지 않습니다. 세션을 넘어 남는 근거가 필요하면 CI 가 담당합니다.

## 이 hook 들이 보장하지 않는 것

로컬 hook 은 **에이전트가 도는 곳에서** 돕니다. 그래서 결정적인 우회는 원리적으로 막지 못합니다.

- 명령 열거는 닫히지 않습니다. `cp` 를 막으면 `mv` 가, `mv` 를 막으면 `python -c` 가 남습니다.
- 쓰기가 hook 이 읽을 수 없는 프로그램 안에서 일어날 수 있습니다.
- hook 을 등록하는 파일을 고치면 hook 자체가 사라집니다.
- `HARNESS_ALLOW_GUARDED_EDIT=1` 은 정당한 작업을 위해 반드시 있어야 하는 탈출구입니다.

여기서 막으려는 것은 악의적 사람이 아니라 **게이트를 통과시키려는 압력을 받는 에이전트**입니다. 그 상대는 회피에 끈질기지 않고 숨기지도 않습니다. 처음 통하는 경로를 즉시 쓸 뿐입니다. 그래서 차단과 검출의 조합이 실제로 효과가 있습니다. 설계 목표는 "속일 의도가 없는 에이전트는 실수로도 속이지 못하고, 속인 에이전트는 흔적을 남긴다" 입니다.

**무결성 보장은 저장소 밖에 있어야 합니다.** 에이전트는 자기 머신의 어떤 hook 도 이길 수 있지만 다른 곳에서 도는 검사는 이기지 못합니다. `.github/workflows/harness.yml` 이 그 역할을 합니다.

## 비활성화 방법과 그 위험

| 방법 | 범위 | 위험 |
| --- | --- | --- |
| `settings.json` 의 해당 항목 제거 | 영구 | 하네스가 규칙 문서만 남고 강제력을 잃습니다 |
| `HARNESS_SKIP_STOP_GATE=1` | 해당 실행 1회 | 검증되지 않은 결과가 완료로 보고됩니다 |
| `HARNESS_ALLOW_GUARDED_EDIT=1` | 해당 실행 1회 | 평가 기준이 검토 없이 바뀔 수 있습니다. `.harness/guard-events.log` 에 `bypass` 로 남습니다 |
| `HARNESS_DETECT_SKIP_PACKS=1` | 해당 실행 1회 | 사후 검출의 감시 범위가 코어 패턴으로 좁아집니다 |
| 보호 배열에서 패턴 삭제 | 영구 | 삭제한 경로는 다시 조작 가능한 상태가 됩니다 |
| 언어 팩 `lang.sh` 에서 패턴 삭제 | 영구 | 그 언어의 lint·타입·테스트 설정이 다시 조작 가능한 상태가 됩니다. `lang.sh` 자체가 코어 차단 목록에 있으므로 에이전트는 편집 도구로 우회할 수 없습니다 |
| `language/` 디렉터리 삭제 또는 `lang.sh` 파손 | 영구 | 언어별 보호가 전부 사라집니다. hook 이 매 호출마다 stderr 로 알리므로 조용히 진행되지는 않습니다 |

hook 을 끄면 규칙은 문서로만 남습니다. 문서는 지켜졌는지 확인되지 않습니다. 특히 `guard-evaluation-tampering.sh` 를 끈 상태에서 자동 루프를 돌리면, 점수를 올리는 가장 값싼 방법이 평가를 약화시키는 것이 되어 Self-Improvement 가 Self-Drift 로 바뀝니다.

끄기로 결정했다면 다음을 남깁니다.

1. 왜 껐는지와 언제 다시 켤지
2. 그동안 무엇으로 대체하는지(사람 검토, CI 게이트 등)
3. `improvement-log/` 에 후보 기록. 반복해서 꺼야 한다면 hook 이 아니라 hook 의 판정 기준이 잘못된 것입니다

## 관련 문서

- [rules/evaluation-integrity.rule.md](../rules/evaluation-integrity.rule.md)
- [rules/harness-change-control.rule.md](../rules/harness-change-control.rule.md)
- [rules/loop-budget.rule.md](../rules/loop-budget.rule.md)
- [rules/promotion-gate.rule.md](../rules/promotion-gate.rule.md)
- [references/harness-elements.md](../references/harness-elements.md)
- [skills/harness-verify/SKILL.md](../skills/harness-verify/SKILL.md)
- [skills/harness-promote/SKILL.md](../skills/harness-promote/SKILL.md)
- [subagents/harness-reviewer.md](../subagents/harness-reviewer.md)
- [language/README.md](../language/README.md) — 언어별 보호 패턴을 소유하는 팩 규약
