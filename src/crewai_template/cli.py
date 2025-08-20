from __future__ import annotations

import json
from pathlib import Path
import sys
import subprocess
from typing import Any, Dict, Optional
import asyncio

import typer
from dotenv import load_dotenv
from rich.console import Console

from .config_loader import (
    get_project_root,
    load_agents_config,
    load_tasks_config,
    load_crew_config,
    load_mcp_servers_config,
    validate_all,
)
from .tool_registry import registry
from .crew import ConfigDrivenCrew

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()


def _kv_to_dict(items: Optional[list[str]]) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    if not items:
        return data
    for item in items:
        if "=" not in item:
            raise typer.BadParameter(f"Invalid input pair: '{item}'. Use key=value format.")
        k, v = item.split("=", 1)
        data[k] = v
    return data


def _ensure_mcp_if_needed(root: Path) -> None:
    """If any MCP server uses stdio transport, ensure 'mcp' package is installed.

    This avoids downstream auto-install prompts that may use an invalid requirement string.
    """
    try:
        servers = load_mcp_servers_config(root)
    except Exception:
        return
    needs_mcp = False
    for spec in servers:
        transport = (getattr(spec, "transport", "") or "").lower()
        if transport == "stdio" or (not transport and getattr(spec, "command", None)):
            needs_mcp = True
            break
    if not needs_mcp:
        return
    try:
        import mcp  # type: ignore  # noqa: F401
        return
    except Exception:
        pass
    if typer.confirm("MCP stdio servers detected. Install required 'mcp' package now?", default=True):
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "mcp"])  # nosec B603
            console.print("[green]'mcp' installed successfully.[/green]")
        except subprocess.CalledProcessError as e:
            console.print(f"[red]Failed to install 'mcp' via pip: {e}[/red]")
            # Let subsequent steps raise clearer errors if needed
    else:
        console.print("[yellow]Proceeding without 'mcp'; stdio MCP servers will be skipped.[/yellow]")


@app.command()
def validate(config_dir: str = typer.Option("config", help="Directory with YAML files.")):
    """Validate all configuration files and tool imports."""
    load_dotenv(override=False)
    root = get_project_root()
    validate_all(root)
    _ensure_mcp_if_needed(root)
    _ = registry(root)  # build tools
    console.print("[green]Tools loaded successfully.[/green]")


@app.command()
def list_tools():
    """List all enabled tools resolved from configuration."""
    load_dotenv(override=False)
    root = get_project_root()
    _ensure_mcp_if_needed(root)
    reg = registry(root)
    for name in reg.all_names:
        console.print(f"- {name}")


@app.command()
def show_configs():
    """Print merged configs useful for debugging."""
    root = get_project_root()
    console.rule("Agents")
    console.print(load_agents_config(root))
    console.rule("Tasks")
    console.print(load_tasks_config(root))
    console.rule("Crew")
    console.print(load_crew_config(root).model_dump())


@app.command()
def run(
    inputs_json: Optional[str] = typer.Option(None, help="JSON string with kickoff inputs."),
    inputs: Optional[list[str]] = typer.Option(
        None,
        help="Provide key=value pairs as kickoff inputs. Example: --inputs topic='AI agents'",
    ),
):
    """Run the crew using dynamic inputs.

    Note: You can also use `crewai run` from the project root to execute via CrewAI CLI.
    """
    load_dotenv(override=False)
    root = get_project_root()
    _ensure_mcp_if_needed(root)
    _ = registry(root)  # ensure tools are instantiated early for clearer errors

    data: Dict[str, Any] = {}
    if inputs_json:
        try:
            data.update(json.loads(inputs_json))
        except json.JSONDecodeError as e:
            raise typer.BadParameter(f"Invalid JSON for --inputs-json: {e}")
    data.update(_kv_to_dict(inputs))
    # Ensure any task output_file directories exist
    try:
        tasks_cfg = load_tasks_config(root)
        for task_name, task_cfg in tasks_cfg.items():
            output_file = task_cfg.get("output_file")
            if output_file:
                out_path = (root / output_file).resolve()
                out_dir = out_path.parent
                out_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:  # noqa: BLE001
        console.print(f"[yellow]Warning: unable to pre-create output directories: {e}[/yellow]")

    try:
        crew_cfg = load_crew_config(root)
        crew_instance = ConfigDrivenCrew()
        if getattr(crew_cfg, "run_async", False):
            async def _run():
                result = await crew_instance.kickoff_async(inputs=data or {"topic": "Hello World"})
                return result
            result = asyncio.run(_run())
        else:
            result = crew_instance.crew().kickoff(inputs=data or {"topic": "Hello World"})
        console.print("\n[bold]Result:[/bold]\n")
        console.print(result)
    except Exception as e:  # noqa: BLE001
        import traceback
        console.print("[red]Run failed with an exception:[/red]")
        console.print(traceback.format_exc())


if __name__ == "__main__":
    app()
