"""Observability bootstrap for CrewAI template.

Best-effort initialization of OpenTelemetry tracing, OpenInference
instrumentation for CrewAI, and optional Arize Phoenix integration.

All dependencies are optional and this module will fail gracefully when
packages are not installed. Configure via crews.yaml under `observability`.

Example crews.yaml snippet:

crews:
  default:
    # ...
    observability:
      enabled: true
      provider: "phoenix"  # or "otlp"
      otlp_endpoint: "${OTEL_EXPORTER_OTLP_ENDPOINT:http://127.0.0.1:4318}"
      instrument_crewai: true
      instrument_openai: false
      launch_ui: false
"""
from __future__ import annotations

from typing import Any, Dict, Optional
import os

from rich.console import Console

_console = Console()

_initialized = False


def _setup_tracing_with_otlp(endpoint: Optional[str] = None) -> None:
    try:
        # Core OpenTelemetry SDK
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        # HTTP/proto exporter (works with default Phoenix collector or any OTLP endpoint)
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
    except Exception as e:  # noqa: BLE001
        _console.print(
            f"[yellow]OTel SDK/exporter not available; skipping tracing init ({e})[/yellow]"
        )
        return

    # Respect existing provider if already set up
    if isinstance(trace.get_tracer_provider(), TracerProvider):
        # Already configured by caller; don't override
        return

    resource = Resource.create({
        "service.name": os.getenv("OTEL_SERVICE_NAME", "crew-composer"),
        "service.version": os.getenv("OTEL_SERVICE_VERSION", "dev"),
    })
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    endpoint = endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:4318")
    try:
        exporter = OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")
        provider.add_span_processor(BatchSpanProcessor(exporter))
        _console.print(
            f"[green]OpenTelemetry tracing configured (OTLP: {endpoint}).[/green]"
        )
    except Exception as e:  # noqa: BLE001
        _console.print(
            f"[yellow]Failed to initialize OTLP exporter at {endpoint}: {e}[/yellow]"
        )


def _register_phoenix(launch_ui: bool = False) -> None:
    """Register Phoenix OTel hooks if available.

    Phoenix exposes a helper in phoenix.otel to auto-wire exporters/processor.
    This call is a no-op if the lib is missing.
    """
    try:
        from phoenix.otel import register  # type: ignore
    except Exception as e:  # noqa: BLE001
        _console.print(
            f"[yellow]Arize Phoenix not installed; skipping Phoenix registration ({e})[/yellow]"
        )
        return

    try:
        # phoenix.otel.register accepts optional arguments; we call with defaults.
        register()
        _console.print("[green]Phoenix OpenTelemetry integration registered.[/green]")
    except Exception as e:  # noqa: BLE001
        _console.print(
            f"[yellow]Phoenix registration failed; continuing without Phoenix ({e})[/yellow]"
        )
        return

    if launch_ui:
        try:
            # Best-effort local UI launch (no-op if unsupported)
            import phoenix as _px  # type: ignore

            if hasattr(_px, "launch_app"):
                _px.launch_app()  # type: ignore[attr-defined]
                _console.print("[green]Phoenix UI launched.[/green]")
        except Exception:
            # Silent; UI is optional
            pass


def _instrument_openinference_crewai(enable_openai: bool = False) -> None:
    # Instrument CrewAI via OpenInference
    try:
        from openinference.instrumentation.crewai import CrewAIInstrumentor  # type: ignore

        CrewAIInstrumentor().instrument()
        _console.print("[green]OpenInference CrewAI instrumentation enabled.[/green]")
    except Exception as e:  # noqa: BLE001
        _console.print(
            f"[yellow]OpenInference CrewAI instrumentation unavailable ({e}); skipping[/yellow]"
        )

    if enable_openai:
        # Optionally instrument OpenAI client calls as well
        try:
            from openinference.instrumentation.openai import OpenAIInstrumentor  # type: ignore

            OpenAIInstrumentor().instrument()
            _console.print("[green]OpenInference OpenAI instrumentation enabled.[/green]")
        except Exception:
            pass



def init_observability(config: Optional[Dict[str, Any]]) -> None:
    """Initialize observability stack based on a simple dict config.

    Keys:
      - enabled (bool)
      - provider ("phoenix" | "otlp")
      - otlp_endpoint (str)
      - instrument_crewai (bool)
      - instrument_openai (bool)
      - launch_ui (bool)
    """
    global _initialized
    if _initialized:
        return

    cfg = config or {}
    if not bool(cfg.get("enabled", False)):
        return

    provider = str(cfg.get("provider", "otlp")).lower()
    if provider == "phoenix":
        _register_phoenix(launch_ui=bool(cfg.get("launch_ui", False)))
    else:
        _setup_tracing_with_otlp(endpoint=cfg.get("otlp_endpoint"))

    if bool(cfg.get("instrument_crewai", True)):
        _instrument_openinference_crewai(enable_openai=bool(cfg.get("instrument_openai", False)))

    _initialized = True
