from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional

import yaml
from pydantic import BaseModel, Field
from rich.console import Console

from .errors import ConfigNotFoundError, InvalidConfigError

console = Console()


class ToolSpec(BaseModel):
    name: str
    module: str
    class_name: str = Field(alias="class")
    enabled: bool = True
    args: Dict[str, Any] = Field(default_factory=dict)
    env: Dict[str, str] = Field(default_factory=dict)


class ToolsConfig(BaseModel):
    tools: Dict[str, List[ToolSpec]] = Field(default_factory=dict)


class MCPServerSpec(BaseModel):
    """Configuration for an MCP server connection.

    Supports stdio, SSE, and streamable HTTP transports.
    """
    name: str
    enabled: bool = True
    # Transport: 'stdio', 'sse', or 'streamable-http'. If omitted, inferred from fields
    transport: Optional[str] = None
    # Stdio fields
    command: Optional[str] = None
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    # Network fields
    url: Optional[str] = None
    headers: Dict[str, str] = Field(default_factory=dict)
    # Extras
    connect_timeout: Optional[int] = 60
    name_prefix: Optional[str] = None  # defaults to '<name>.' when not provided
    include_tools: List[str] = Field(default_factory=list)
    exclude_tools: List[str] = Field(default_factory=list)


class CrewConfig(BaseModel):
    process: Optional[str] = Field(default="sequential")
    verbose: bool = Field(default=True)
    planning: bool = Field(default=False)
    planning_llm: Optional[str] = None
    manager_llm: Optional[str] = Field(default="gpt-4o-mini")
    memory: bool = Field(default=False)
    knowledge: Dict[str, Any] = Field(default_factory=dict)
    # Optional list of knowledge source keys to load from agents.knowledge.yaml
    knowledge_sources: Optional[List[str]] = None
    # When true, CLI will kickoff the crew asynchronously
    run_async: bool = Field(default=False)
    # Optional manager agent name from agents.yaml (e.g., 'researcher')
    manager_agent: Optional[str] = None
    # Crew-level orchestration (config-driven)
    # If provided, limit built agents to this allowlist
    agents: List[str] = Field(default_factory=list)
    # Preferred task execution order for this crew
    task_order: List[str] = Field(default_factory=list)
    # Map each task name to an agent name
    task_agent_map: Dict[str, str] = Field(default_factory=dict)
    tools_files: List[str] = Field(default_factory=lambda: [
        "config/tools.yaml",
        "config/mcp_tools.yaml",
    ])


def _resolve_env_placeholders(value: Any) -> Any:
    """Resolve ${VAR} or ${VAR:default} placeholders in strings."""
    if isinstance(value, str):
        out = ""
        i = 0
        while i < len(value):
            if value[i : i + 2] == "${":
                j = value.find("}", i + 2)
                if j == -1:
                    out += value[i:]
                    break
                token = value[i + 2 : j]
                if ":" in token:
                    var, default = token.split(":", 1)
                    out += os.getenv(var, default)
                else:
                    out += os.getenv(token, "")
                i = j + 1
            else:
                out += value[i]
                i += 1
        return out
    if isinstance(value, Mapping):
        return {k: _resolve_env_placeholders(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env_placeholders(v) for v in value]
    return value


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ConfigNotFoundError(str(path))
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise InvalidConfigError(f"YAML root must be a mapping: {path}")
    return data


def load_agents_config(root: Path) -> Dict[str, Any]:
    data = _load_yaml(root / "config" / "agents.yaml")
    return _resolve_env_placeholders(data)


def load_tasks_config(root: Path) -> Dict[str, Any]:
    data = _load_yaml(root / "config" / "tasks.yaml")
    return _resolve_env_placeholders(data)


def load_crew_config(root: Path) -> CrewConfig:
    raw = _load_yaml(root / "config" / "crew.yaml")
    raw = _resolve_env_placeholders(raw)
    return CrewConfig.model_validate(raw)


def load_tools_config(root: Path, tools_files: Optional[List[str]] = None) -> ToolsConfig:
    tools_files = tools_files or ["config/tools.yaml"]
    merged: Dict[str, List[Dict[str, Any]]] = {}
    for rel in tools_files:
        path = (root / rel).resolve()
        if not path.exists():
            # Skip silently to allow optional files like mcp_tools.yaml
            continue
        raw = _load_yaml(path)
        section = raw.get("tools", {})
        if not isinstance(section, dict):
            raise InvalidConfigError(f"'tools' must be a mapping in {path}")
        for category, items in section.items():
            if not isinstance(items, list):
                raise InvalidConfigError(
                    f"Category '{category}' must be a list in {path}"
                )
            merged.setdefault(category, []).extend(items)
    # Normalize to ToolSpec
    normalized: Dict[str, List[ToolSpec]] = {}
    for cat, items in merged.items():
        specs = []
        for item in items:
            # Support both 'class' and 'class_name' in YAML
            if "class_name" in item and "class" not in item:
                item["class"] = item["class_name"]
            spec = ToolSpec.model_validate(item)
            # Resolve env placeholders inside args and env
            spec.args = _resolve_env_placeholders(spec.args)
            spec.env = _resolve_env_placeholders(spec.env)
            specs.append(spec)
        normalized[cat] = specs
    return ToolsConfig(tools=normalized)


def load_mcp_servers_config(root: Path, tools_files: Optional[List[str]] = None) -> List[MCPServerSpec]:
    """Load and merge MCP server specs from any files in tools_files that contain a 'servers' list.

    Missing files are ignored to allow optional mcp_tools.yaml.
    """
    tools_files = tools_files or ["config/mcp_tools.yaml"]
    servers: List[MCPServerSpec] = []
    for rel in tools_files:
        path = (root / rel).resolve()
        if not path.exists():
            continue
        raw = _load_yaml(path)
        section = raw.get("servers", [])
        if section is None:
            continue
        if not isinstance(section, list):
            raise InvalidConfigError(f"'servers' must be a list in {path}")
        for item in section:
            if not isinstance(item, dict):
                raise InvalidConfigError(f"Each server entry must be a mapping in {path}")
            item = _resolve_env_placeholders(item)
            spec = MCPServerSpec.model_validate(item)
            # Resolve placeholders also in nested fields explicitly
            spec.args = [_resolve_env_placeholders(x) for x in (spec.args or [])]
            spec.env = _resolve_env_placeholders(spec.env)
            spec.headers = _resolve_env_placeholders(spec.headers)
            servers.append(spec)
    return servers


def get_project_root() -> Path:
    """Best-effort project root: 2 levels up from this file (src/pkg -> repo)."""
    return Path(__file__).resolve().parents[2]


def validate_all(root: Optional[Path] = None) -> None:
    root = root or get_project_root()
    # Presence checks
    _ = load_agents_config(root)
    _ = load_tasks_config(root)
    crew_conf = load_crew_config(root)
    _ = load_tools_config(root, crew_conf.tools_files)
    # Parse MCP servers (may be optional if file absent)
    _ = load_mcp_servers_config(root, crew_conf.tools_files)
    console.print("[green]Configuration validated successfully.[/green]")
