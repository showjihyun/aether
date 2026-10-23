"""spec 0007 R-2, D-2 (P5-4): 브라우저의 쓰기는 서버 액션만 받고, 액션은 **통과 구멍**이 아니다.

`"use server"` 파일의 함수는 어떤 브라우저 요청이든 닿는 진입점입니다. 중계(`lib/relay.ts`)를
늘리지 않는 대신 쓰기를 받는 곳이므로, 그 파일이 지켜야 할 것을 **파일을 읽어** 고정합니다
(TypeScript 라 `ast` 를 못 씁니다 - 주석과 문자열 내용을 지운 뒤 판정하는 작은 분석기입니다).

판정 셋:

1. **api 호출은 SDK 로만.** import 는 `@aether/sdk` 와 `next/cache`·`next/navigation` 뿐이고,
   `fetch(`·`XMLHttpRequest`·동적 import·`require` 가 없으며, `process.env.AETHER_API_URL` 은
   `createClient(...)` 의 인자 안에서만 읽습니다(그 값으로 직접 요청을 만들 수 없습니다).
2. **검증 없이 통과시키지 않는다.** 내보내는 함수의 인자는 원시 타입(`string`·`number`·`boolean`)
   뿐이고(`FormData`·`unknown`·객체를 통째로 받지 않습니다), 각 인자는 본문에서 **처음 나오는 곳이**
   `typeof 인자` 검사이며, 그 `if` 의 조건에 값 내용을 보는 검사가 하나 더 있고(모양 정규식·공백·
   길이), 그 `if` 는 `return`/`throw` 로 끝나며, 이 모두가 `createClient(` 보다 앞입니다.
3. **브라우저 쪽 코드(`"use client"`)는 쓰기 메서드를 부르지 않는다.** 쓰기는 서버 액션만 합니다.

한계(숨기지 않습니다): 분석기는 템플릿 리터럴 안의 `${}` 를 문자열로 취급하고, 정규식 리터럴 안의
따옴표를 모릅니다. 액션 파일에서 그런 모양을 쓰면 이 테스트가 먼저 어긋나 드러납니다.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "apps" / "web"

ALLOWED_IMPORTS = frozenset({"@aether/sdk", "next/cache", "next/navigation"})
PRIMITIVE_TYPES = frozenset({"string", "number", "boolean"})
# 브라우저 코드가 부르면 안 되는 SDK 쓰기 메서드 (읽기와 스트림은 허용)
CLIENT_FORBIDDEN_WRITES = ("createAgent", "updateAgent", "runAgent", "cancelRun")
# 이 단위가 세운 서버 액션 파일. 목록에서 사라지면(이름 변경·삭제) 그 사실이 드러나야 합니다.
EXPECTED_ACTION_FILES = {
    "apps/web/app/agents/[id]/chat/actions.ts",
    "apps/web/app/agents/actions.ts",
}

# --- 분석기 --------------------------------------------------------------------------------


def scan(src: str) -> tuple[str, str]:
    """`(raw, code)` - 같은 길이, 주석은 공백. `code` 는 문자열 내용도 `_` 로 지운다."""
    raw: list[str] = []
    code: list[str] = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c in "\"'`":
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == "\\" else 1
            j = min(j, n - 1)
            raw.append(src[i : j + 1])
            code.append(c + "_" * (j - i - 1) + c)
            i = j + 1
        elif src.startswith("//", i):
            j = src.find("\n", i)
            j = n if j == -1 else j
            raw.append(" " * (j - i))
            code.append(" " * (j - i))
            i = j
        elif src.startswith("/*", i):
            j = src.find("*/", i + 2)
            j = n if j == -1 else j + 2
            blank = "".join("\n" if ch == "\n" else " " for ch in src[i:j])
            raw.append(blank)
            code.append(blank)
            i = j
        else:
            raw.append(c)
            code.append(c)
            i += 1
    return "".join(raw), "".join(code)


def balanced(code: str, open_index: int, opener: str, closer: str) -> int:
    """`code[open_index] == opener` 에 짝지어지는 닫는 문자의 위치(없으면 -1)."""
    depth = 0
    for k in range(open_index, len(code)):
        if code[k] == opener:
            depth += 1
        elif code[k] == closer:
            depth -= 1
            if depth == 0:
                return k
    return -1


def is_use_server(src: str) -> bool:
    raw, _ = scan(src)
    return re.match(r"\s*([\"'])use server\1", raw) is not None


def is_use_client(src: str) -> bool:
    raw, _ = scan(src)
    return re.match(r"\s*([\"'])use client\1", raw) is not None


def _exported_functions(code: str) -> list[tuple[str, list[tuple[str, str]], str]]:
    """`(이름, [(인자, 타입)], 본문)`. 본문은 `code` 의 부분 문자열(문자열 내용이 지워진 것)."""
    found = []
    for match in re.finditer(r"\bexport\s+async\s+function\s+(\w+)\s*\(", code):
        open_paren = match.end() - 1
        close_paren = balanced(code, open_paren, "(", ")")
        params_text = code[open_paren + 1 : close_paren]
        params: list[tuple[str, str]] = []
        depth, start = 0, 0
        pieces = []
        for k, ch in enumerate(params_text + ","):
            if ch in "<({[":
                depth += 1
            elif ch in ">)}]":
                depth -= 1
            elif ch == "," and depth == 0:
                pieces.append(params_text[start:k])
                start = k + 1
        for piece in pieces:
            if not piece.strip():
                continue
            name, _, type_ = piece.partition(":")
            params.append((name.strip().rstrip("?"), type_.strip()))
        # 반환 타입(`Promise<{ ... }>` 의 중괄호)을 건너뛰고 본문 `{` 를 찾는다.
        angle = 0
        body_open = -1
        for k in range(close_paren + 1, len(code)):
            if code[k] == "<":
                angle += 1
            elif code[k] == ">":
                angle -= 1
            elif code[k] == "{" and angle == 0:
                body_open = k
                break
        body_close = balanced(code, body_open, "{", "}")
        found.append((match.group(1), params, code[body_open + 1 : body_close]))
    return found


def _guard_problems(function: str, params: list[tuple[str, str]], body: str) -> list[str]:
    problems: list[str] = []
    first_client = body.find("createClient(")
    for name, type_ in params:
        if type_ not in PRIMITIVE_TYPES:
            problems.append(f"{function}({name}: {type_}) 인자가 원시 타입이 아닙니다")
            continue
        first = re.search(rf"\b{re.escape(name)}\b", body)
        if first is None:
            problems.append(f"{function}: 인자 {name} 을(를) 쓰지 않습니다")
            continue
        if not body[: first.start()].rstrip().endswith("typeof"):
            problems.append(f"{function}: {name} 의 첫 사용이 typeof 검사가 아닙니다")
            continue
        ifs = [m for m in re.finditer(r"\bif\s*\(", body[: first.start()])]
        if not ifs:
            problems.append(f"{function}: {name} 의 typeof 검사가 if 안에 없습니다")
            continue
        open_paren = ifs[-1].end() - 1
        close_paren = balanced(body, open_paren, "(", ")")
        if not open_paren < first.start() < close_paren:
            problems.append(f"{function}: {name} 의 typeof 검사가 if 조건 안에 없습니다")
            continue
        condition = body[open_paren + 1 : close_paren]
        if len(re.findall(rf"\b{re.escape(name)}\b", condition)) < 2:
            problems.append(f"{function}: {name} 은 typeof 검사뿐이고 값 내용을 검사하지 않습니다")
        after = body[close_paren + 1 :].lstrip()
        if not re.match(r"(return|throw)\b|\{\s*(return|throw)\b", after):
            problems.append(f"{function}: {name} 의 검증 실패가 return/throw 로 끝나지 않습니다")
        if first_client != -1 and close_paren > first_client:
            problems.append(f"{function}: {name} 의 검증이 createClient 보다 뒤입니다")
    return problems


def action_violations(src: str) -> list[str]:
    """`"use server"` 파일이 지켜야 할 것을 어긴 곳(없으면 빈 목록)."""
    raw, code = scan(src)
    problems: list[str] = []

    for match in re.finditer(r"\bimport\b(?:[^;\"'`]*?\bfrom\s*)?([\"'])([^\"']+)\1", raw):
        if match.group(2) not in ALLOWED_IMPORTS:
            problems.append(f"허용되지 않은 import: {match.group(2)}")
    for pattern, label in (
        (r"\bfetch\s*\(", "fetch( 직접 호출"),
        (r"\bXMLHttpRequest\b", "XMLHttpRequest"),
        (r"\bWebSocket\b", "WebSocket"),
        (r"\bEventSource\b", "EventSource"),
        (r"\brequire\s*\(", "require("),
        (r"\bimport\s*\(", "동적 import("),
        (r"\bprocess\.env(?!\.\w)", "process.env 를 이름 없이 읽음"),
    ):
        if re.search(pattern, code):
            problems.append(label)

    spans = []
    for match in re.finditer(r"\bcreateClient\s*\(", code):
        open_paren = match.end() - 1
        spans.append((open_paren, balanced(code, open_paren, "(", ")")))
    for match in re.finditer(r"\bAETHER_API_URL\b", code):
        if not any(a < match.start() < b for a, b in spans):
            problems.append("AETHER_API_URL 을 createClient 인자 밖에서 읽음")

    for match in re.finditer(
        r"^[ \t]*export\s+(?!async\s+function\b|type\b|interface\b)", code, re.M
    ):
        problems.append(f"함수가 아닌 export: {code[match.start() : match.start() + 40].strip()}")

    for name, params, body in _exported_functions(code):
        problems += _guard_problems(name, params, body)
    return problems


def client_write_violations(src: str) -> list[str]:
    _, code = scan(src)
    return [
        f".{method}( 호출"
        for method in CLIENT_FORBIDDEN_WRITES
        if re.search(rf"\.{method}\s*\(", code)
    ]


# R-11 (P5-7): 도구 허용 목록(`control.tool_permissions`, 기본 deny)을 바꾸는 길은
# CLI 가 소유합니다.
# 화면 코드에는 그 이름도, 그것을 부르는 모양도 없어야 합니다. 문자열은 보존하고 주석만 지운 `raw`
# 에서 봅니다 - 경로(`"/permissions"`)는 문자열 안에 있기 때문입니다.
POLICY_WRITE_PATTERNS = (
    (r"permission", "허용 목록(permission) 이름"),
    (r"\.(allow|grant|revoke|deny)\w*\s*\(", "허용·거부를 바꾸는 메서드 호출"),
)


def policy_write_violations(src: str) -> list[str]:
    raw, _ = scan(src)
    return [label for pattern, label in POLICY_WRITE_PATTERNS if re.search(pattern, raw, re.I)]


def web_sources() -> list[Path]:
    return sorted(
        p
        for ext in ("ts", "tsx")
        for p in WEB.rglob(f"*.{ext}")
        if not {"node_modules", ".next"} & set(p.relative_to(WEB).parts)
    )


# --- 고정값: 통과하는 모양 --------------------------------------------------------------------

GOOD = """"use server";
import { AetherHttpError, createClient } from "@aether/sdk";
export type R = { ok: true } | { ok: false; message: string };
const ID_SHAPE = /^[A-Za-z0-9_-]{1,128}$/;
// fetch( 는 주석 안이라 무시됩니다
export async function save(agentId: string, input: string): Promise<R> {
  if (typeof agentId !== "string" || !ID_SHAPE.test(agentId)) return fail("fetch(");
  if (typeof input !== "string" || input.trim() === "") {
    return fail("x");
  }
  const client = createClient({
    baseUrl: process.env.AETHER_API_URL ?? "x",
    apiKey: process.env.AETHER_API_KEY,
  });
  await client.runAgent(agentId, { input });
  return { ok: true };
}
"""


def test_the_good_shape_passes() -> None:
    assert action_violations(GOOD) == []
    assert is_use_server(GOOD)


# --- 고정값: 구멍 (판정기가 공허하지 않은지 - 양성 대조) -----------------------------------------


def _replace(old: str, new: str) -> str:
    assert old in GOOD
    return GOOD.replace(old, new, 1)


def test_it_fires_on_a_direct_fetch() -> None:
    bad = _replace(
        "await client.runAgent(agentId, { input });",
        'await fetch("http://x/run", { method: "POST" });',
    )
    assert "fetch( 직접 호출" in action_violations(bad)


def test_it_fires_on_a_request_built_from_the_api_url() -> None:
    bad = _replace("  const client", "  const url = process.env.AETHER_API_URL;\n  const client")
    assert "AETHER_API_URL 을 createClient 인자 밖에서 읽음" in action_violations(bad)


def test_it_fires_on_a_forbidden_import() -> None:
    bad = _replace(
        "import { AetherHttpError", 'import axios from "axios";\nimport { AetherHttpError'
    )
    assert "허용되지 않은 import: axios" in action_violations(bad)


def test_it_fires_on_the_relay_import() -> None:
    bad = _replace(
        "import { AetherHttpError", 'import { relay } from "@/lib/relay";\nimport { AetherHttpError'
    )
    assert "허용되지 않은 import: @/lib/relay" in action_violations(bad)


def test_it_fires_on_a_whole_object_parameter() -> None:
    bad = (
        '"use server";\nimport { createClient } from "@aether/sdk";\n'
        "export async function save(body: unknown) {\n"
        "  const client = createClient({ baseUrl: process.env.AETHER_API_URL });\n"
        "  return client.createAgent(body);\n}\n"
    )
    assert any("원시 타입이 아닙니다" in p for p in action_violations(bad))


def test_it_fires_on_form_data_passthrough() -> None:
    bad = (
        '"use server";\nimport { createClient } from "@aether/sdk";\n'
        "export async function save(form: FormData) {\n"
        "  const client = createClient({ baseUrl: process.env.AETHER_API_URL });\n"
        "  return client.createAgent(Object.fromEntries(form));\n}\n"
    )
    assert any("FormData" in p for p in action_violations(bad))


def test_it_fires_on_a_typeof_only_check() -> None:
    bad = _replace(
        'if (typeof input !== "string" || input.trim() === "") {',
        'if (typeof input !== "string") {',
    )
    assert any("값 내용을 검사하지 않습니다" in p for p in action_violations(bad))


def test_it_fires_when_the_parameter_is_used_before_its_guard() -> None:
    bad = _replace("  if (typeof agentId", "  console.log(agentId);\n  if (typeof agentId")
    assert any("첫 사용이 typeof 검사가 아닙니다" in p for p in action_violations(bad))


def test_it_fires_when_the_guard_does_not_return() -> None:
    bad = _replace('return fail("fetch(");', "{}")
    assert any("return/throw 로 끝나지 않습니다" in p for p in action_violations(bad))


def test_it_fires_when_the_guard_comes_after_the_client() -> None:
    bad = (
        '"use server";\nimport { createClient } from "@aether/sdk";\n'
        "export async function save(input: string) {\n"
        "  const client = createClient({ baseUrl: process.env.AETHER_API_URL });\n"
        '  if (typeof input !== "string" || input.trim() === "") return 1;\n'
        "  return client.runAgent('a', { input });\n}\n"
    )
    assert any("createClient 보다 뒤" in p for p in action_violations(bad))


def test_it_fires_on_a_parameter_that_is_never_checked() -> None:
    bad = (
        '"use server";\nimport { createClient } from "@aether/sdk";\n'
        "export async function save(name: string) {\n"
        "  const client = createClient({ baseUrl: process.env.AETHER_API_URL });\n"
        "  return client.createAgent({ name });\n}\n"
    )
    assert any("typeof 검사가 아닙니다" in p for p in action_violations(bad))


def test_it_fires_on_a_non_function_export() -> None:
    bad = _replace("const ID_SHAPE", "export const LIMIT = 1;\nconst ID_SHAPE")
    assert any("함수가 아닌 export" in p for p in action_violations(bad))


def test_it_fires_on_an_unnamed_process_env_read() -> None:
    bad = _replace("  const client", "  const env = process.env;\n  const client")
    assert "process.env 를 이름 없이 읽음" in action_violations(bad)


def test_client_code_calling_a_write_method_is_found() -> None:
    assert client_write_violations("const c = createClient(x); await c.updateAgent(id, b);") == [
        ".updateAgent( 호출"
    ]
    assert client_write_violations("for await (const e of c.streamRunEvents(id)) {}") == []


# --- 실제 저장소 -----------------------------------------------------------------------------


def _action_files() -> dict[str, Path]:
    return {
        p.relative_to(REPO_ROOT).as_posix(): p
        for p in web_sources()
        if is_use_server(p.read_text(encoding="utf-8"))
    }


def test_the_known_server_action_files_are_found() -> None:
    """파일을 못 찾아 빈 목록을 '통과' 로 읽는 일을 막는다 (쓰기 경로가 늘면 이 목록도 는다)."""
    assert set(_action_files()) == EXPECTED_ACTION_FILES


def test_every_server_action_file_is_sdk_only_and_validates_its_arguments() -> None:
    failures = {
        name: problems
        for name, path in _action_files().items()
        if (problems := action_violations(path.read_text(encoding="utf-8")))
    }
    assert failures == {}


def test_browser_code_never_calls_an_sdk_write_method() -> None:
    offenders = {}
    for path in web_sources():
        text = path.read_text(encoding="utf-8")
        if is_use_client(text) and (found := client_write_violations(text)):
            offenders[path.relative_to(REPO_ROOT).as_posix()] = found
    assert offenders == {}


def test_it_fires_on_a_path_or_call_that_changes_the_tool_allow_list() -> None:
    """R-11 양성 대조: 판정기가 공허하지 않다 (경로 문자열·SDK 메서드·변수 이름 셋 다 잡는다)."""
    assert policy_write_violations('await fetch("/permissions", { method: "POST" });')
    assert policy_write_violations("await client.allowTool(agentId, name);")
    assert policy_write_violations("await client.setToolPermissions(x);")
    assert policy_write_violations("const tool_permissions = [];")
    # 주석은 무시한다 (설명이 걸리지 않는다). Agent 정의의 policy 블록도 해당 없다
    assert policy_write_violations("// permission 은 CLI 가 소유합니다") == []
    assert policy_write_violations("const policy = current.definition.policy;") == []


def test_web_has_no_path_that_changes_the_tool_allow_list() -> None:
    """spec 0007 R-11, D-5: `apps/web` 어디에도 도구 허용 목록을 바꾸는 경로가 없다 (0건).

    읽는 경로도 지금은 없습니다(api 에 허용 목록을 읽는 HTTP 경로가 없음) - 이 테스트는 그 이름
    자체가 화면 코드에 나타나면 사람이 보도록 합니다."""
    sources = web_sources()
    assert sources, "web 소스를 하나도 못 찾았습니다 (빈 목록을 통과로 읽지 않습니다)"
    offenders = {
        p.relative_to(REPO_ROOT).as_posix(): found
        for p in sources
        if (found := policy_write_violations(p.read_text(encoding="utf-8")))
    }
    assert offenders == {}


def test_the_relay_allow_list_still_has_no_write_route() -> None:
    """R-2: 중계는 GET 만 허용한다 (개수 고정은 route.test.ts 가, 여기서는 메서드를 본다)."""
    relay = (WEB / "lib" / "relay.ts").read_text(encoding="utf-8")
    _, code = scan(relay)
    assert not re.search(r"\b(POST|PUT|PATCH|DELETE)\b", code)
