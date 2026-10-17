"""명령 본문 - `Transport` 에만 기대고 출력은 `output.write` 로만 합니다.

반환값은 종료 코드입니다(0 성공, 1 실행 실패). 사용 오류(2)는 `main` 이 정합니다.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from typing import Any

from aether_cli import contract
from aether_cli.output import write
from aether_cli.sse import parse_sse
from aether_cli.transport import ConnectionFailed, Transport

DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant."
LIST_PAGE_SIZE = 200
_FINISHED = "run.finished"
_SUCCEEDED = "succeeded"


def _cell(value: object) -> str:
    return "-" if value is None else str(value)


def agent_create(transport: Transport, out: Any, name: str, prompt: str | None) -> int:
    """`POST /agents` 후 생성된 id 만 한 줄로 출력합니다(스크립트가 받아 쓰게)."""
    body = {
        "name": name,
        "definition": {
            "schema_version": 1,
            "system_prompt": DEFAULT_SYSTEM_PROMPT if prompt is None else prompt,
        },
    }
    created = transport.request(contract.CREATE_AGENT, body=body)
    write(out, f"{created['id']}\n")
    return 0


def _all_agents(transport: Transport) -> Iterator[dict[str, Any]]:
    cursor: str | None = None
    while True:
        query = {"limit": str(LIST_PAGE_SIZE)}
        if cursor is not None:
            query["cursor"] = cursor
        page = transport.request(contract.LIST_AGENTS, query=query)
        yield from page["items"]
        cursor = page.get("next_cursor")
        if cursor is None:
            return


def agent_list(transport: Transport, out: Any) -> int:
    """`GET /agents` 의 모든 페이지를 표로 출력합니다."""
    rows = [
        (a["id"], a["name"], _cell(a["current_version"]), _cell(a["updated_at"]))
        for a in _all_agents(transport)
    ]
    header = ("ID", "NAME", "CURRENT_VERSION", "UPDATED_AT")
    widths = [max(len(str(r[i])) for r in [header, *rows]) for i in range(len(header))]
    for row in [header, *rows]:
        write(
            out,
            "  ".join(str(c).ljust(w) for c, w in zip(row, widths, strict=True)).rstrip() + "\n",
        )
    return 0


def _format_event(envelope: dict[str, Any]) -> str:
    payload = json.dumps(envelope.get("payload", {}), ensure_ascii=False)
    return f"{envelope.get('seq', '?'):>4}  {envelope.get('type', '?'):<16}  {payload}\n"


def _close(iterator: Iterable[bytes]) -> None:
    close = getattr(iterator, "close", None)
    if callable(close):
        close()


def run(transport: Transport, out: Any, err: Any, agent_id: str, text: str) -> int:
    """Run 을 요청하고 이벤트를 **도착하는 대로** 출력합니다. `run.finished` 에서 끝납니다.

    종결 상태가 `succeeded` 면 0, 그 밖(failed·cancelled·timed_out)이나 스트림이 끊기면 1.
    """
    accepted = transport.request(
        contract.RUN_AGENT, params={"agent_id": agent_id}, body={"input": text}
    )
    run_id = str(accepted["run_id"])
    write(out, f"run: {run_id}\n")

    status: str | None = None
    lines = transport.stream(contract.RUN_EVENTS, params={"run_id": run_id})
    try:
        for sse in parse_sse(lines):
            try:
                envelope = json.loads(sse.data)
            except ValueError:
                write(out, f"      {sse.event}  {sse.data}\n")
                continue
            write(out, _format_event(envelope))
            if envelope.get("type") == _FINISHED:
                status = str(envelope.get("payload", {}).get("status"))
                break
    except ConnectionFailed as exc:
        write(err, f"error: {exc}\n")
        write(err, f"  run 은 서버에서 계속될 수 있습니다: aether runs get {run_id}\n")
        return 1
    finally:
        _close(lines)

    if status is None:
        write(err, "error: 스트림이 run.finished 없이 끝났습니다 (연결이 끊겼습니다)\n")
        write(err, f"  run 은 서버에서 계속될 수 있습니다: aether runs get {run_id}\n")
        return 1

    write(out, f"status: {status}\n")
    if status == _SUCCEEDED:
        return 0
    detail = transport.request(contract.GET_RUN, params={"run_id": run_id})
    write(out, f"failure_reason: {_cell(detail.get('failure_reason'))}\n")
    return 1


def runs_get(transport: Transport, out: Any, run_id: str) -> int:
    """`GET /runs/{id}` - 상태·시각·실패 사유."""
    detail = transport.request(contract.GET_RUN, params={"run_id": run_id})
    fields = (
        "run_id",
        "status",
        "agent_id",
        "agent_version",
        "requested_at",
        "started_at",
        "finished_at",
        "failure_reason",
        "trace_id",
    )
    for field in fields:
        write(out, f"{field}: {_cell(detail.get(field))}\n")
    return 0
