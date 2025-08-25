from __future__ import annotations

import atexit
import os
from typing import Any, Dict, Iterable, List, Tuple

from crewai_tools import MCPServerAdapter

try:  # Optional dependency, only needed for stdio transport
    from mcp import StdioServerParameters  # type: ignore
except Exception:  # pragma: no cover - optional
    StdioServerParameters = None  # type: ignore


def _build_server_params(spec: "MCPServerSpec") -> Any:
    """Translate an MCPServerSpec into parameters accepted by MCPServerAdapter.

    - stdio: returns StdioServerParameters(...)
    - sse/streamable-http: returns a dict with url/transport/headers
    """
    transport = (spec.transport or "").lower()
    if transport == "stdio" or (not transport and spec.command):
        if StdioServerParameters is None:
            raise ImportError(
                "mcp package is required for stdio transport. Install with: pip install mcp"
            )
        env = {**os.environ, **(spec.env or {})}
        return StdioServerParameters(
            command=spec.command,
            args=list(spec.args or []),
            env=env,
        )

    if transport in {"sse", "streamable-http"} or (not transport and spec.url):
        params: Dict[str, Any] = {
            "url": spec.url,
            "transport": transport or "sse",
        }
        if spec.headers:
            params["headers"] = dict(spec.headers)
        return params

    raise ValueError(
        f"Unsupported MCP transport '{spec.transport}'. Expected one of: stdio, sse, streamable-http"
    )


def connect_mcp_servers(
    servers: Iterable["MCPServerSpec"],
) -> Tuple[Dict[str, Any], List[MCPServerAdapter]]:
    """Connect to enabled MCP servers and collect their tools.

    Returns (tool_map, adapters), where tool_map maps fully-qualified tool names to
    tool objects, and adapters are kept open for the lifetime of the process.
    """
    tool_map: Dict[str, Any] = {}
    adapters: List[MCPServerAdapter] = []

    for spec in servers:
        if not getattr(spec, "enabled", True):
            continue
        try:
            server_params = _build_server_params(spec)
        except Exception as e:  # noqa: BLE001
            # Skip this server but keep going
            print(f"[MCP] Skipping server '{spec.name}': {e}")
            continue

        try:
            adapter = MCPServerAdapter(server_params, connect_timeout=int(spec.connect_timeout or 60))
            # Keep the connection open by manually entering context
            mcp_tools = adapter.__enter__()
            adapters.append(adapter)

            # Ensure cleanup on exit
            def _make_closer(ad: MCPServerAdapter) -> None:
                def _close() -> None:
                    try:
                        ad.__exit__(None, None, None)
                    except Exception:
                        pass
                atexit.register(_close)
            _make_closer(adapter)

            # Register tools with prefix and filters
            prefix = spec.name_prefix or f"{spec.name}."
            include = set(spec.include_tools or [])
            exclude = set(spec.exclude_tools or [])

            for t in mcp_tools:
                tname = getattr(t, "name", None) or getattr(t, "tool_name", None)
                if not isinstance(tname, str):
                    continue
                if include and tname not in include:
                    continue
                if tname in exclude:
                    continue
                fq_name = f"{prefix}{tname}"
                tool_map[fq_name] = t
        except Exception as e:  # noqa: BLE001
            print(f"[MCP] Failed to load tools from '{spec.name}': {e}")
            continue

    return tool_map, adapters
