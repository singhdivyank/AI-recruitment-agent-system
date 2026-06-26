"""
Full observability stack:
  - Prometheus metrics (via prometheus-fastapi-instrumentator)
  - OpenTelemetry distributed tracing
  - LangSmith LLM tracing (configured via env vars)
  - Structured logging via structlog
"""
from __future__ import annotations
import time
import structlog
from functools import wraps
from typing import Callable

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

from prometheus_fastapi_instrumentator import Instrumentator

from core.config import get_settings
from utils.prometheus_metrics import (
    AGENT_CALLS,
    LLM_CALLS,
    LLM_TOKENS,
    LLM_COST,
    LLM_LATENCY,
    TOOL_CALLS,
    TOOL_LATENCY,
    TOOL_FAILURES,
    ACTIVE_WORKFLOWS,
)

settings = get_settings()

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.ConsoleRenderer() if settings.app_env == "development"
        else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()

def setup_tracing() -> None:
    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)

    otlp_exporter = OTLPSpanExporter(
        endpoint=settings.otel_exporter_otlp_endpoint,
        insecure=True,
    )
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    trace.set_tracer_provider(provider)
    logger.info("otel_tracing_initialized", endpoint=settings.otel_exporter_otlp_endpoint)


def get_tracer(name: str) -> trace.Tracer:
    return trace.get_tracer(name)

def setup_prometheus(app) -> None:
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

def observe_agent(agent_name: str):
    """
    Decorator that wraps an agent call with:
      - structured log entry/exit
      - Prometheus counter + latency histogram
      - OTel span
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = get_tracer(agent_name)
            start = time.monotonic()
            log = logger.bind(agent=agent_name)
            log.info("agent_start")
            ACTIVE_WORKFLOWS.inc()

            with tracer.start_as_current_span(agent_name) as span:
                try:
                    result = await func(*args, **kwargs)
                    elapsed = time.monotonic() - start
                    AGENT_CALLS.labels(agent_name=agent_name, jd_id="", status="success").inc()
                    log.info("agent_success", latency_s=round(elapsed, 2))
                    span.set_attribute("status", "success")
                    return result
                except Exception as exc:
                    elapsed = time.monotonic() - start
                    AGENT_CALLS.labels(agent_name=agent_name, jd_id="", status="error").inc()
                    log.error("agent_error", error=str(exc), latency_s=round(elapsed, 2))
                    span.record_exception(exc)
                    span.set_attribute("status", "error")
                    raise
                finally:
                    ACTIVE_WORKFLOWS.dec()

        return wrapper
    return decorator

def record_llm_usage(
    agent_name: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_s: float,
    cost_usd: float,
    success: bool = True,
) -> None:
    """Called after every LLM API call to update metrics."""
    status = "success" if success else "error"
    LLM_CALLS.labels(agent_name=agent_name, model=model, status=status).inc()
    LLM_TOKENS.labels(agent_name=agent_name, model=model, token_type="input").inc(input_tokens)
    LLM_TOKENS.labels(agent_name=agent_name, model=model, token_type="output").inc(output_tokens)
    LLM_COST.labels(agent_name=agent_name, model=model).inc(cost_usd)
    LLM_LATENCY.labels(agent_name=agent_name, model=model).observe(latency_s)

    logger.info(
        "llm_call",
        agent=agent_name,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=round(cost_usd, 6),
        latency_s=round(latency_s, 2),
        success=success,
    )


def record_tool_call(tool_name: str, latency_s: float, success: bool = True) -> None:
    status = "success" if success else "error"
    TOOL_CALLS.labels(tool_name=tool_name, status=status).inc()
    TOOL_LATENCY.labels(tool_name=tool_name).observe(latency_s)

    if status == "error":
        TOOL_FAILURES.labels(tool_name=tool_name).inc()
    
    logger.info("tool_call", tool=tool_name, latency_s=round(latency_s, 2), success=success)