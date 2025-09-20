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
    list_crew_names,
    load_mcp_servers_config,
    validate_all,
)
from .tool_registry import registry
from .observability import init_observability
from .crew import ConfigDrivenCrew
from .scheduler import (
    SchedulerService,
    ScheduleEntry,
    list_schedules as _list_schedules,
    upsert_schedule as _upsert_schedule,
    delete_schedule as _delete_schedule,
)

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


def _ensure_mcp_if_needed(root: Path, crew_name: Optional[str]) -> None:
    """If any MCP server uses stdio transport, ensure 'mcp' package is installed.

    This avoids downstream auto-install prompts that may use an invalid requirement string.
    """
    try:
        crew_cfg = load_crew_config(root, crew_name)
        servers = load_mcp_servers_config(root, crew_cfg.tools_files)
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
def validate(
    crew: Optional[str] = typer.Option(None, help="Crew name from config/crews.yaml (defaults to first)."),
    config_dir: str = typer.Option("config", help="Directory with YAML files."),
):
    """Validate all configuration files and tool imports."""
    load_dotenv(override=False)
    root = get_project_root()
    validate_all(root, crew)
    _ensure_mcp_if_needed(root, crew)
    crew_cfg = load_crew_config(root, crew)
    _ = registry(root, crew_cfg.tools_files)  # build tools
    console.print("[green]Tools loaded successfully.[/green]")


@app.command()
def list_tools(
    crew: Optional[str] = typer.Option(None, help="Crew name from config/crews.yaml (defaults to first)."),
):
    """List all enabled tools resolved from configuration."""
    load_dotenv(override=False)
    root = get_project_root()
    _ensure_mcp_if_needed(root, crew)
    crew_cfg = load_crew_config(root, crew)
    reg = registry(root, crew_cfg.tools_files)
    for name in reg.all_names:
        console.print(f"- {name}")


@app.command()
def show_configs(
    crew: Optional[str] = typer.Option(None, help="Crew name from config/crews.yaml (defaults to first)."),
):
    """Print merged configs useful for debugging."""
    root = get_project_root()
    console.rule("Agents")
    console.print(load_agents_config(root))
    console.rule("Tasks")
    console.print(load_tasks_config(root))
    console.rule("Crew")
    console.print(load_crew_config(root, crew).model_dump())
    try:
        names = list_crew_names(root)
        console.rule("Available Crews")
        for n in names:
            console.print(f"- {n}{' (default)' if (crew is None and n == names[0]) else ''}{' (selected)' if (crew and n == crew) else ''}")
    except Exception:
        pass


@app.command()
def run(
    crew: Optional[str] = typer.Option(None, help="Crew name from config/crews.yaml (defaults to first)."),
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
    _ensure_mcp_if_needed(root, crew)
    crew_cfg = load_crew_config(root, crew)
    # Initialize observability before any heavy lifting
    try:
        init_observability(getattr(crew_cfg, "observability", {}))
    except Exception as e:  # noqa: BLE001
        console.print(f"[yellow]Observability init warning: {e}[/yellow]")
    _ = registry(root, crew_cfg.tools_files)  # ensure tools are instantiated early for clearer errors

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
        crew_cfg = load_crew_config(root, crew)
        crew_instance = ConfigDrivenCrew(crew_name=crew)
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


@app.command()
def ui(
    port: int = typer.Option(8501, help="Port for Streamlit server."),
    headless: bool = typer.Option(True, help="Run Streamlit in headless mode."),
):
    """Launch the Crew Composer Streamlit UI packaged in crew_composer.ui.app."""
    load_dotenv(override=False)
    root = get_project_root()
    # Build the streamlit command to run the packaged app module file
    # We point streamlit to the module file path so it can watch for changes.
    app_path = (Path(__file__).parent / "ui" / "app.py").resolve()
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.port",
        str(port),
    ]
    if headless:
        cmd += ["--server.headless", "true"]
    console.print(f"[bold]Starting UI:[/bold] {' '.join(cmd)}")
    try:
        subprocess.check_call(cmd, cwd=str(root))
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to start Streamlit UI: {e}[/red]")


# -------------------- Scheduler Commands --------------------


@app.command(name="schedule-service")
def schedule_service(
    poll: int = typer.Option(5, help="Seconds between checks for schedule file changes."),
):
    """Run the background scheduler service that executes scheduled crews.

    This process monitors db/schedules.json and runs jobs accordingly.
    """
    load_dotenv(override=False)
    root = get_project_root()
    service = SchedulerService(root=root, poll_seconds=poll)
    service.run_forever()


@app.command(name="schedule-list")
def schedule_list():
    """List all schedules from the store (db/schedules.json)."""
    load_dotenv(override=False)
    entries = _list_schedules()
    console.print(json.dumps([e.model_dump() for e in entries], indent=2))


@app.command(name="schedule-upsert")
def schedule_upsert(
    id: Optional[str] = typer.Option(None, help="Existing ID to update; omit to create a new one."),
    name: Optional[str] = typer.Option(None, help="Human-friendly schedule name."),
    crew: Optional[str] = typer.Option(None, help="Crew name (from config/crews.yaml); defaults to first when omitted."),
    trigger: str = typer.Option("date", help="Trigger type: date | interval | cron"),
    run_at: Optional[str] = typer.Option(None, help="ISO datetime for date trigger, e.g., 2025-09-19T10:00:00"),
    interval_seconds: Optional[int] = typer.Option(None, help="Interval in seconds for interval trigger."),
    cron_json: Optional[str] = typer.Option(None, help='Cron mapping as JSON, e.g., "{\"minute\": \"0\", \"hour\": \"*\"}"'),
    timezone: Optional[str] = typer.Option(None, help="Timezone identifier (optional)."),
    enabled: bool = typer.Option(True, help="Whether the schedule is enabled."),
    inputs_json: Optional[str] = typer.Option(None, help="JSON string with kickoff inputs."),
    inputs: Optional[list[str]] = typer.Option(None, help="key=value pairs for inputs."),
):
    """Create or update a schedule entry."""
    load_dotenv(override=False)
    cron_map: Optional[Dict[str, str]] = None
    if cron_json:
        try:
            cron_map = json.loads(cron_json)
            if not isinstance(cron_map, dict):
                raise ValueError("cron_json must decode to an object")
        except Exception as e:  # noqa: BLE001
            raise typer.BadParameter(f"Invalid cron_json: {e}")
    data: Dict[str, Any] = {}
    if inputs_json:
        try:
            data.update(json.loads(inputs_json))
        except json.JSONDecodeError as e:
            raise typer.BadParameter(f"Invalid JSON for --inputs-json: {e}")
    data.update(_kv_to_dict(inputs))

    entry = ScheduleEntry(
        id=id or "",  # will be set by store if empty via tool; here we keep explicit
        name=name or (id or ""),
        crew=crew or None,
        trigger=trigger,  # type: ignore[arg-type]
        run_at=run_at,
        interval_seconds=interval_seconds,
        cron=cron_map,
        timezone=timezone or None,
        enabled=enabled,
        inputs=data,
    )
    # If id omitted, generate a UUID-like fallback using name and time
    if not entry.id:
        import uuid as _uuid
        entry.id = str(_uuid.uuid4())
        if not entry.name:
            entry.name = entry.id
    saved = _upsert_schedule(entry)
    console.print(json.dumps(saved.model_dump(), indent=2))


@app.command(name="schedule-delete")
def schedule_delete(id: str = typer.Argument(..., help="Schedule ID to delete.")):
    """Delete a schedule entry by ID."""
    load_dotenv(override=False)
    ok = _delete_schedule(id)
    console.print(json.dumps({"deleted": ok, "id": id}, indent=2))


if __name__ == "__main__":
    app()
