from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from rich.console import Console

from .config_loader import (
    ToolsConfig,
    load_tools_config,
    load_crew_config,
    load_mcp_servers_config,
    MCPServerSpec,
    get_project_root,
)
from .mcp_integration import connect_mcp_servers
from .errors import ToolImportError, UnsupportedToolError

console = Console()


class ToolRegistry:
    """Loads and instantiates tool objects declared in YAML files.

    Tools are referenced by unique names in YAML and can be attached to agents or tasks.
    """

    def __init__(self, root: Optional[Path] = None, tools_files: Optional[List[str]] = None) -> None:
        self.root = root or get_project_root()
        if tools_files is None:
            # Fallback to the first crew defined in config/crews.yaml
            crew_cfg = load_crew_config(self.root, None)
            tools_files = crew_cfg.tools_files
        self._tools_files: List[str] = list(tools_files)
        self.tools_config: ToolsConfig = load_tools_config(self.root, self._tools_files)
        self.mcp_servers: List[MCPServerSpec] = load_mcp_servers_config(self.root, self._tools_files)
        self._instances: Dict[str, Any] = {}
        self._mcp_adapters: List[Any] = []
        self._build()

    def _build(self) -> None:
        for category, specs in self.tools_config.tools.items():
            for spec in specs:
                if not spec.enabled:
                    continue
                try:
                    module = importlib.import_module(spec.module)
                except Exception as e:  # noqa: BLE001
                    raise ToolImportError(spec.module, spec.class_name, extra=str(e)) from e
                try:
                    cls = getattr(module, spec.class_name)
                except AttributeError as e:
                    raise ToolImportError(
                        spec.module,
                        spec.class_name,
                        extra="Class not found in module",
                    ) from e
                # Apply env vars if declared
                for k, v in spec.env.items():
                    os.environ.setdefault(k, str(v))
                try:
                    instance = cls(**spec.args) if spec.args else cls()
                except TypeError as e:
                    raise ToolImportError(
                        spec.module,
                        spec.class_name,
                        extra=f"Constructor failed with args {spec.args}: {e}",
                    ) from e
                if spec.name in self._instances:
                    console.print(
                        f"[yellow]Duplicate tool name '{spec.name}' encountered; overriding previous instance[/yellow]"
                    )
                self._instances[spec.name] = instance

        # Load MCP servers and dynamically register their tools
        try:
            mcp_tool_map, adapters = connect_mcp_servers(self.mcp_servers)
            self._mcp_adapters = adapters
            for name, tool in mcp_tool_map.items():
                # Warn on duplicates, then override
                if name in self._instances:
                    console.print(
                        f"[yellow]Duplicate tool name '{name}' encountered from MCP; overriding previous instance[/yellow]"
                    )
                self._instances[name] = tool
        except Exception as e:  # noqa: BLE001
            console.print(f"[yellow]Warning: MCP integration partially failed: {e}[/yellow]")

    @property
    def all_names(self) -> List[str]:
        return list(self._instances.keys())

    def get(self, name: str) -> Any:
        if name not in self._instances:
            raise UnsupportedToolError(name)
        return self._instances[name]

    def resolve(self, names: Iterable[str]) -> List[Any]:
        """Resolve tool names, supporting wildcard suffix '*'.

        Example: 'brave_search.*' resolves all tools with that prefix.
        """
        resolved: List[Any] = []
        seen: set[str] = set()
        for n in names:
            if isinstance(n, str) and n.endswith("*"):
                prefix = n[:-1]
                for key, obj in self._instances.items():
                    if key.startswith(prefix) and key not in seen:
                        resolved.append(obj)
                        seen.add(key)
            else:
                obj = self.get(n)
                # Deduplicate by id/name to avoid repeats
                if n not in seen:
                    resolved.append(obj)
                    seen.add(n)
        return resolved


# Crew-aware registry cache keyed by (root, tools_files)
_registry_cache: Dict[tuple[str, tuple[str, ...]], ToolRegistry] = {}


def registry(root: Optional[Path] = None, tools_files: Optional[List[str]] = None) -> ToolRegistry:
    r = (root or get_project_root()).resolve()
    if tools_files is None:
        # Resolve default tools_files via first crew
        crew_cfg = load_crew_config(r, None)
        tools_files = crew_cfg.tools_files
    # Use absolute normalized paths for cache key stability
    tf_tuple = tuple(str((r / Path(p)).resolve()) for p in tools_files)
    key = (str(r), tf_tuple)
    if key not in _registry_cache:
        _registry_cache[key] = ToolRegistry(r, list(tools_files))
    return _registry_cache[key]
