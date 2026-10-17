"""출력은 로케일이 아니라 UTF-8 입니다.

`aether_api.adapters.inbound.cli._write` 와 같은 모양을 **다시 적었습니다**(AR-14: 제품 코드를
import 하지 않습니다). `sys.stdout` 의 인코딩은 실행 환경의 로케일이 정하고, Windows 한국어
콘솔(cp949)은 em dash 등을 인코딩하지 못해 `UnicodeEncodeError` 로 죽습니다(2026-10-13,
improvement-log 2026-09-11-005). 그래서 `stream.buffer` 에 UTF-8 바이트로 씁니다.
"""

from __future__ import annotations

from typing import Any


def write(stream: Any, text: str) -> None:
    """`text` 를 UTF-8 로 `stream` 에 쓰고 **즉시 flush** 합니다(스트림 출력이 도착하는 대로
    보이게). `.buffer` 가 없는 스트림은 텍스트로 씁니다 - 죽는 것보다 낫습니다."""
    buffer = getattr(stream, "buffer", None)
    if buffer is None:
        stream.write(text)
        stream.flush()
        return
    stream.flush()
    buffer.write(text.encode("utf-8"))
    buffer.flush()
