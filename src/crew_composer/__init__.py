"""Crew Composer Package

A modular, config-driven toolkit for composing CrewAI applications.
"""

import os

# Disable telemetry by default (respect user-provided overrides)
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

__all__ = [
    "__version__",
]

__version__ = "0.2.0"
