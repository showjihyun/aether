"""spec 0005 R-1, R-2: Workflow 정의 유스케이스 단위 테스트가 공유하는 지원 코드 — 앱 조립과
여덟 거부 사례. 테스트가 아니라 지원 모듈입니다(`fakes_workflow.py` 와 같은 자리)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from aether_api.adapters.inbound.http.workflows import build_workflows_router
from aether_api.application.usecases.define_workflow import DefineWorkflowUseCase
from aether_api.application.usecases.get_workflow import GetWorkflowUseCase
from aether_api.application.usecases.get_workflow_version import GetWorkflowVersionUseCase
from aether_api.application.usecases.update_workflow import UpdateWorkflowUseCase
from aether_api.domain.api_key import Principal
from aether_workflow.domain.validation import Reason
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from apps.api.tests.fakes_workflow import FakeWorkflowRepository


def _principal(request: Request) -> Principal:
    del request
    return Principal(key_id=uuid4(), label="unit")


def _client() -> tuple[TestClient, FakeWorkflowRepository]:
    repo = FakeWorkflowRepository()
    app = FastAPI()
    app.include_router(
        build_workflows_router(
            _principal,
            DefineWorkflowUseCase(repo),
            GetWorkflowUseCase(repo),
            UpdateWorkflowUseCase(repo),
            GetWorkflowVersionUseCase(repo),
        )
    )
    return TestClient(app), repo


def _n(node_id: str, kind: str, max_iterations: int | None = None) -> dict[str, Any]:
    return {"id": node_id, "kind": kind, "max_iterations": max_iterations}


def _e(source: str, target: str) -> dict[str, Any]:
    return {"source": source, "target": target, "label": None}


def _valid_body() -> dict[str, Any]:
    return {
        "name": "ok",
        "nodes": [_n("s", "START"), _n("a", "AGENT"), _n("e", "END")],
        "edges": [_e("s", "a"), _e("a", "e")],
    }


# 사유 하나당 그래프 하나. 각 그래프는 **그 사유만** 어기도록 만듭니다.
_REJECTIONS: dict[Reason, dict[str, Any]] = {
    Reason.NO_START: {
        "nodes": [_n("a", "AGENT"), _n("e", "END")],
        "edges": [_e("a", "e")],
    },
    Reason.MULTIPLE_START: {
        "nodes": [_n("s1", "START"), _n("s2", "START"), _n("e", "END")],
        "edges": [_e("s1", "e"), _e("s2", "e")],
    },
    Reason.END_UNREACHABLE: {
        "nodes": [_n("s", "START"), _n("e", "END"), _n("dead", "AGENT")],
        "edges": [_e("s", "e"), _e("s", "dead")],
    },
    Reason.ORPHAN_NODE: {
        "nodes": [_n("s", "START"), _n("e", "END"), _n("lonely", "AGENT")],
        "edges": [_e("s", "e")],
    },
    Reason.DANGLING_EDGE: {
        "nodes": [_n("s", "START"), _n("e", "END")],
        "edges": [_e("s", "e"), _e("s", "ghost")],
    },
    Reason.DUPLICATE_NODE_ID: {
        "nodes": [_n("s", "START"), _n("a", "AGENT"), _n("a", "AGENT"), _n("e", "END")],
        "edges": [_e("s", "a"), _e("a", "e")],
    },
    Reason.LOOP_WITHOUT_BOUND: {
        "nodes": [_n("s", "START"), _n("l", "LOOP", None), _n("e", "END")],
        "edges": [_e("s", "l"), _e("l", "e")],
    },
    Reason.PARALLEL_WITHOUT_JOIN: {
        "nodes": [_n("s", "START"), _n("p", "PARALLEL"), _n("a", "AGENT"), _n("e", "END")],
        "edges": [_e("s", "p"), _e("p", "a"), _e("a", "e")],
    },
}
