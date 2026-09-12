"""spec 0002 2.3: `AgentDefinition` 검증 규칙 전부 — `schema_version` 아닌 값, 빈
`system_prompt`, `BUILTIN_TOOL_NAMES` 밖 도구, 범위 밖 정책 값.
"""

from __future__ import annotations

import pytest
from aether_runtime.domain.agent import AgentDefinition
from pydantic import ValidationError


def _minimal(**overrides: object) -> dict[object, object]:
    base: dict[object, object] = {
        "schema_version": 1,
        "system_prompt": "You are a helpful agent.",
    }
    base.update(overrides)
    return base


def test_defaults_match_spec_example() -> None:
    definition = AgentDefinition.model_validate(_minimal())

    assert definition.model.id is None
    assert definition.tools == []
    assert definition.policy.timeout_seconds == 120
    assert definition.policy.max_steps == 8
    assert definition.policy.model_retries == 2
    assert definition.policy.tool_retries == 1
    assert definition.policy.backoff.base_seconds == 0.5
    assert definition.policy.backoff.max_seconds == 8.0


def test_accepts_full_example_from_spec() -> None:
    definition = AgentDefinition.model_validate(
        {
            "schema_version": 1,
            "system_prompt": "You are …",
            "model": {"id": None},
            "tools": ["clock", "calculator"],
            "policy": {
                "timeout_seconds": 120,
                "max_steps": 8,
                "model_retries": 2,
                "tool_retries": 1,
                "backoff": {"base_seconds": 0.5, "max_seconds": 8.0},
            },
        }
    )

    assert definition.tools == ["clock", "calculator"]


def test_model_id_accepts_explicit_string() -> None:
    definition = AgentDefinition.model_validate(_minimal(model={"id": "gpt-x"}))

    assert definition.model.id == "gpt-x"


@pytest.mark.parametrize("bad_schema_version", [0, 2, "1", None])
def test_rejects_schema_version_other_than_literal_one(bad_schema_version: object) -> None:
    with pytest.raises(ValidationError):
        AgentDefinition.model_validate(_minimal(schema_version=bad_schema_version))


@pytest.mark.parametrize("blank", ["", "   ", "\n\t"])
def test_rejects_blank_system_prompt(blank: str) -> None:
    with pytest.raises(ValidationError):
        AgentDefinition.model_validate(_minimal(system_prompt=blank))


def test_rejects_tool_outside_builtin_tool_names() -> None:
    with pytest.raises(ValidationError):
        AgentDefinition.model_validate(_minimal(tools=["clock", "web_search"]))


def test_rejects_duplicate_tools() -> None:
    with pytest.raises(ValidationError):
        AgentDefinition.model_validate(_minimal(tools=["clock", "clock"]))


@pytest.mark.parametrize("value", [0, 3601])
def test_rejects_timeout_seconds_outside_one_to_thirty_six_hundred(value: int) -> None:
    with pytest.raises(ValidationError):
        AgentDefinition.model_validate(_minimal(policy={"timeout_seconds": value}))


@pytest.mark.parametrize("value", [0, 65])
def test_rejects_max_steps_outside_one_to_sixty_four(value: int) -> None:
    with pytest.raises(ValidationError):
        AgentDefinition.model_validate(_minimal(policy={"max_steps": value}))


@pytest.mark.parametrize("field", ["model_retries", "tool_retries"])
@pytest.mark.parametrize("value", [-1, 11])
def test_rejects_retries_outside_zero_to_ten(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        AgentDefinition.model_validate(_minimal(policy={field: value}))


def test_rejects_backoff_base_seconds_not_positive() -> None:
    with pytest.raises(ValidationError):
        AgentDefinition.model_validate(
            _minimal(policy={"backoff": {"base_seconds": 0, "max_seconds": 1.0}})
        )


def test_rejects_backoff_max_seconds_below_base_seconds() -> None:
    with pytest.raises(ValidationError):
        AgentDefinition.model_validate(
            _minimal(policy={"backoff": {"base_seconds": 2.0, "max_seconds": 1.0}})
        )


def test_accepts_backoff_max_seconds_equal_to_base_seconds() -> None:
    definition = AgentDefinition.model_validate(
        _minimal(policy={"backoff": {"base_seconds": 2.0, "max_seconds": 2.0}})
    )

    assert definition.policy.backoff.max_seconds == 2.0
