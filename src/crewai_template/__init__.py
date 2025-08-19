"""CrewAI Template Package

A modular, config-driven template for building CrewAI applications.
"""

import os

# Disable CrewAI telemetry only
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"

__all__ = [
    "__version__",
]

__version__ = "0.1.0"
