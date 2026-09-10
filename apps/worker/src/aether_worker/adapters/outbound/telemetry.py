"""OpenTelemetry SDK 초기화. `application.ports` 와 `domain` 외 aether 모듈을 import 하지 않습니다.

exporter 는 `OTEL_EXPORTER_OTLP_ENDPOINT` 가 있을 때만 붙습니다. 없으면 no-op 이고,
있어도 부팅을 막지 않습니다(spec 2.3, DP-4).

`apps/api` 의 같은 파일과 모양이 같습니다 — AR-7 준비(worker 는 api 를 import 하지
않음)로 복제한 것이지 공유 코드가 아닙니다.
"""

from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider


def init_telemetry(service_name: str) -> None:
    """`service.name = service_name` 으로 TracerProvider 를 등록합니다."""
    resource = Resource.create({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)

    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

    trace.set_tracer_provider(provider)
