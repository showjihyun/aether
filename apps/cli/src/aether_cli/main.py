"""`aether` 진입점 - argparse, 환경변수, 종료 코드.

종료 코드: 0 성공, 1 실행 실패(서버 오류·Run 실패·연결 끊김), 2 사용 오류(인자·키 없음).
키는 `AETHER_API_KEY` 환경변수로만 받고(D-8) 어느 출력에도 싣지 않습니다. 주소는
`AETHER_API_URL`(기본 `http://localhost:8000`).
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, NoReturn

from aether_cli import commands, compose
from aether_cli.output import write
from aether_cli.transport import ApiError, ConnectionFailed, Transport, UrllibTransport

DEFAULT_API_URL = "http://localhost:8000"
KEY_VARIABLE = "AETHER_API_KEY"
URL_VARIABLE = "AETHER_API_URL"

TransportFactory = Callable[[str, str], Transport]


class _Parser(argparse.ArgumentParser):
    """argparse 의 출력도 UTF-8 로 씁니다(`output.write`) - 도움말에 한국어가 있습니다."""

    def __init__(self, *args: Any, streams: tuple[Any, Any], **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._streams = streams

    def _print_message(self, message: str, file: Any = None) -> None:
        if message:
            write(self._streams[1] if file is sys.stderr else self._streams[0], message)

    def error(self, message: str) -> NoReturn:
        self.print_usage(self._streams[1])
        write(self._streams[1], f"{self.prog}: error: {message}\n")
        raise SystemExit(2)


def build_parser(stdout: Any, stderr: Any) -> argparse.ArgumentParser:
    streams = (stdout, stderr)
    parser = _Parser(
        prog="aether",
        description="aether CLI - 환경변수 AETHER_API_KEY(필수), AETHER_API_URL(기본 "
        f"{DEFAULT_API_URL})",
        streams=streams,
    )
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    def add(name: str, help_text: str, parent: Any = sub) -> Any:
        child = parent.add_parser(name, help=help_text, streams=streams)
        return child

    up = add("up", "compose 로 스택을 띄웁니다 (격리 프로젝트)")
    up.add_argument("--down", action="store_true", help="스택과 볼륨을 내립니다(그 프로젝트만)")
    up.add_argument("--project", default=compose.DEFAULT_PROJECT, help="compose 프로젝트 이름")
    up.add_argument("--compose-file", action="append", default=[], help="추가 compose 파일")
    up.add_argument("--no-build", action="store_true", help="이미지를 빌드하지 않습니다")

    agent = add("agent", "Agent 관리")
    agent_sub = agent.add_subparsers(dest="agent_command", required=True, parser_class=_Parser)
    create = add("create", "Agent 를 만들고 id 를 출력합니다", agent_sub)
    create.add_argument("--name", required=True)
    create.add_argument("--prompt", default=None, help="system prompt")
    add("list", "Agent 목록", agent_sub)

    run = add("run", "Agent 를 실행하고 이벤트를 스트림으로 출력합니다")
    run.add_argument("agent_id")
    run.add_argument("--input", required=True, dest="text", help="Run 입력")

    runs = add("runs", "Run 조회")
    runs_sub = runs.add_subparsers(dest="runs_command", required=True, parser_class=_Parser)
    get = add("get", "Run 의 상태·시각·실패 사유", runs_sub)
    get.add_argument("run_id")
    return parser


def main(
    argv: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    stdout: Any = None,
    stderr: Any = None,
    transport_factory: TransportFactory = UrllibTransport,
    runner: compose.Runner = compose.default_runner,
    root: Path | None = None,
) -> int:
    environment = os.environ if env is None else env
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    parser = build_parser(out, err)
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    api_url = environment.get(URL_VARIABLE) or DEFAULT_API_URL

    if args.command == "up":
        if not compose.valid_project(args.project):
            write(err, f"error: --project 이름이 올바르지 않습니다: {args.project!r}\n")
            return 2
        if args.down:
            return compose.down(
                root=root,
                project=args.project,
                extra_files=args.compose_file,
                runner=runner,
                out=out,
                err=err,
            )
        return compose.up(
            root=root,
            project=args.project,
            extra_files=args.compose_file,
            build_images=not args.no_build,
            runner=runner,
            api_url=api_url,
            out=out,
            err=err,
        )

    key = environment.get(KEY_VARIABLE, "").strip()
    if not key:
        write(
            err, f"error: {KEY_VARIABLE} 환경변수를 설정하십시오 (API 키는 환경변수로만 받습니다)\n"
        )
        return 2

    transport = transport_factory(api_url, key)
    try:
        if args.command == "agent" and args.agent_command == "create":
            return commands.agent_create(transport, out, args.name, args.prompt)
        if args.command == "agent":
            return commands.agent_list(transport, out)
        if args.command == "run":
            return commands.run(transport, out, err, args.agent_id, args.text)
        return commands.runs_get(transport, out, args.run_id)
    except ApiError as exc:
        write(err, f"error: {exc}\n")
        return 1
    except ConnectionFailed as exc:
        write(err, f"error: {exc}\n")
        return 1


def cli() -> None:
    sys.exit(main(sys.argv[1:]))
