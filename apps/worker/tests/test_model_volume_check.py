"""spec 0006 R-9, D-5, DP-4 (MVP-3): 모델 볼륨이 비어 있으면 worker 가 **시작 지점**에서
받는 방법을 적은 명확한 오류로 멈춘다. 부팅 경로는 모델을 받지 않는다."""

from __future__ import annotations

import io
from contextlib import redirect_stderr
from threading import Event

import pytest
from aether_runtime.application.ports.outbound.model_gateway import ModelError
from aether_worker.main import WorkerStartupError, check_model_available, serve
from aether_worker.settings import Settings

FETCH = "scripts/fetch-model.sh"


def _real(model_id: str = "qwen2.5:0.5b", api_key: str | None = None) -> Settings:
    return Settings(
        model_adapter="openai_compatible",
        model_base_url="http://llm:11434/v1",
        model_id=model_id,
        model_api_key=api_key,
    )


def _boom() -> list[str]:
    raise AssertionError("fake 어댑터는 모델 서버에 묻지 않는다")


def test_fake_adapter_never_asks_the_model_server() -> None:
    """spec 0006 C-7/D-10: 기본값 fake 는 볼륨과 무관하다 - 서버에 묻지 않는다."""
    check_model_available(Settings(), list_models=_boom)


def test_present_model_passes() -> None:
    """spec 0006 R-9: 볼륨에 모델이 있으면 조용히 통과한다."""
    check_model_available(_real(), list_models=lambda: ["other:1b", "qwen2.5:0.5b"])


def test_missing_model_stops_with_fetch_instruction() -> None:
    """spec 0006 R-9: 비어 있으면 WorkerStartupError - 메시지에 모델 id 와 받는 스크립트."""
    with pytest.raises(WorkerStartupError) as exc_info:
        check_model_available(_real(), list_models=lambda: [])

    message = str(exc_info.value)
    assert "qwen2.5:0.5b" in message
    assert FETCH in message


def test_other_models_only_is_still_missing() -> None:
    """spec 0006 R-9: 다른 모델만 있는 볼륨도 '없음' 이다."""
    with pytest.raises(WorkerStartupError):
        check_model_available(_real(), list_models=lambda: ["other:1b"])


def test_untagged_id_matches_latest_tag() -> None:
    """spec 0006 R-9: Ollama 는 태그 없는 id 를 `:latest` 로 본다 - 오탐으로 막지 않는다."""
    check_model_available(_real("tiny"), list_models=lambda: ["tiny:latest"])


def test_unreachable_server_is_a_clear_error_naming_the_url() -> None:
    """spec 0006 R-9/DP-4: 서버가 안 보이는 것도 애매한 Run 실패가 아니라 시작 오류."""

    def down() -> list[str]:
        raise ModelError(kind="protocol", message="connect refused")

    with pytest.raises(WorkerStartupError) as exc_info:
        check_model_available(_real(), list_models=down)

    assert "http://llm:11434/v1" in str(exc_info.value)


def test_error_never_contains_the_api_key() -> None:
    """AGENTS.md Trust: 비밀값은 어떤 메시지에도 남지 않는다."""
    with pytest.raises(WorkerStartupError) as exc_info:
        check_model_available(_real(api_key="s3cret-key"), list_models=lambda: [])

    assert "s3cret-key" not in str(exc_info.value)


def test_serve_returns_1_before_touching_redis_when_model_missing() -> None:
    """spec 0006 R-9: serve 는 Redis 연결 전에 1 로 끝나고 stderr 에 받는 방법을 적는다."""
    connects: list[int] = []

    def make_client() -> object:
        connects.append(1)
        raise AssertionError("모델이 없으면 Redis 에 연결하지 않는다")

    stderr = io.StringIO()
    with redirect_stderr(stderr):
        code = serve(
            _real(),
            stop=Event(),
            make_client=make_client,  # type: ignore[arg-type]
            list_models=lambda: [],
        )

    assert code == 1
    assert connects == []
    assert FETCH in stderr.getvalue()
