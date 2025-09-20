# Crew Composer

A modular, configuration-driven composer for building CrewAI apps that are easy to update, extend, and integrate with tools and MCP. Ships with a Typer-based CLI and is compatible with the CrewAI CLI (`crewai run`).

## Table of Contents

- [Features](#features)
- [Project Structure](#project-structure)
- [Documentation](#documentation)
- [Setup (Windows PowerShell)](#setup-windows-powershell)
- [Streamlit UI](#streamlit-ui)
- [Configuration](#configuration)
  - [Renaming tasks safely (config-driven with context)](#renaming-tasks-safely-config-driven-with-context)
  - [Task enablement and agent mapping](#task-enablement-and-agent-mapping)
  - [Collaborative multi-agent execution (list mapping and pipelines)](#collaborative-multi-agent-execution-list-mapping-and-pipelines)
- [CLI Usage](#cli-usage)
- [MCP Integration](#mcp-integration)
- [Scheduling](#scheduling)
- [Troubleshooting](#troubleshooting)
- [Notes on Extensibility](#notes-on-extensibility)
- [License](#license)

## Features

- **Config-first**: Define agents, tasks, crew, and tools entirely in YAML under `config/`.
- **Tool registry**: Dynamically import and instantiate tools from YAML; supports env var interpolation in args.
- **MCP-ready**: Placeholders and guidance to wire MCP servers and wrappers via config.
- **MCP dynamic tools**: Connect to MCP servers (stdio, SSE, streamable HTTP) from config and auto-register their tools.
- **CLI**: `crew-composer` (alias: `crew-comp`) for validate/list/run/show and `crewai run` compatibility.
- **Validation**: Pydantic-backed validation, clear error messages.
- **.env support**: Environment variable interpolation like `${VAR}` or `${VAR:default}`.
- **Streamlit UI**: Manage configs with Builder UIs, run crews with live logs, quick-add presets for tools/MCP, bulk toggle tools, and browse outputs (Markdown raw/rendered).
- **Scheduling**: File-backed schedules with APScheduler. Manage schedules via CLI and the Streamlit Schedules tab. Optional in-crew tool `schedule_manager` enables agents to create/update/delete schedules.

## Project Structure

```text
.
├─ config/
│  ├─ agents.yaml
│  ├─ tasks.yaml
│  ├─ crews.yaml
│  ├─ tools.yaml
│  └─ mcp_tools.yaml
├─ docs/
│  ├─ README.md
│  ├─ installation.md
│  ├─ getting-started.md
│  ├─ best-practices.md
│  ├─ configuration.md
│  ├─ multi-agent-mapping.md
│  ├─ cli.md
│  ├─ tools-and-mcp.md
│  ├─ knowledge-sources.md
│  ├─ troubleshooting.md
│  └─ faq.md
├─ src/
│  └─ crew_composer/
│     ├─ __init__.py
│     ├─ cli.py
│     ├─ crew.py
│     ├─ config_loader.py
│     ├─ errors.py
│     └─ tool_registry.py
├─ .env.example
├─ pyproject.toml
└─ README.md

## Documentation
- [Docs Home](docs/README.md)
- [Installation](docs/installation.md)
- [Getting Started](docs/getting-started.md)
- [Best Practices](docs/best-practices.md)
- [Configuration Guide](docs/configuration.md)
- [Multi-Agent Task Mapping](docs/multi-agent-mapping.md)
- [CLI Usage](docs/cli.md)
- [Streamlit UI](docs/ui.md)
- [Scheduling](docs/scheduling.md)
- [Tools and MCP Integration](docs/tools-and-mcp.md)
- [Knowledge Sources](docs/knowledge-sources.md)
- [Troubleshooting](docs/troubleshooting.md)
- [FAQ](docs/faq.md)

## Setup (Windows PowerShell)

1. Python 3.10+
1. Create and activate a virtualenv named `venv`:

```powershell
py -3.10 -m venv venv
.\venv\Scripts\Activate.ps1
```

1. Install dependencies (choose one):

- From pyproject (recommended for dev):

```powershell
python -m pip install -e .
```

- From requirements.txt:

```powershell
python -m pip install -r requirements.txt
```

1. Configure environment:

```powershell
Copy-Item .env.example .env
# Edit .env to set your API keys
```

1. Optional: For STDIO MCP servers

```powershell
python -m pip install mcp
```

## Streamlit UI

Launch the UI to manage configs, run crews, and review outputs without editing YAML by hand.

1. Activate your virtual environment

```powershell
./venv/Scripts/Activate.ps1
```

1. Start the app (pick one)

- Recommended: via CLI

  ```powershell
  python -m crew_composer.cli ui
  # options:
  # python -m crew_composer.cli ui --port 8502 --no-headless
  ```

- Packaged app directly (works well with Streamlit hot-reload)

  ```powershell
  python -m streamlit run src/crew_composer/ui/app.py
  ```

- Legacy wrapper (kept for compatibility; delegates to the packaged UI)

  ```powershell
  python -m streamlit run app/streamlit_app.py
  ```

Key capabilities:

- Builder mode for `crews.yaml`, `agents.yaml`, `tasks.yaml`, `tools.yaml`, and `mcp_tools.yaml` with YAML previews and safe backups.
- Quick presets: add common tool specs and MCP server templates (STDIO, SSE, Streamable HTTP) from the UI.
- Bulk enable/disable tools across categories.
- Run a crew with live streaming logs, then save logs to `output/run-logs/<timestamp>_<crew>.log`.
- Outputs tab to browse `output/` with Markdown Raw/Rendered toggle, JSON viewer, and downloads.
- New Schedules tab to list/create/delete schedules and start/stop the scheduler service.

See the full guide: [docs/ui.md](docs/ui.md)

## Configuration

- `config/agents.yaml`: Roles, goals, backstories, LLMs, and tools per agent.
- `config/tasks.yaml`: Descriptions, expected outputs, context deps, and optional `output_file`.
- `config/crews.yaml`: Root `crews:` mapping with named crews. Each crew config controls process (`sequential`/`hierarchical`), verbosity, planning, memory, knowledge, and `tools_files` list.
- `config/tools.yaml`: CrewAi default tool categories with entries `{ name, module, class, enabled, args, env }`.
- `config/mcp_tools.yaml`: MCP servers and tool wrappers. Disabled by default.

Environment variables in configs use `${VAR}` or `${VAR:default}` and resolve from your `.env` and OS env.

### Renaming tasks safely (config-driven with context)

Tasks and their dependency `context` are fully configuration-driven. CrewAI resolves `context` by calling same-named `@task` methods. This template synthesizes those methods dynamically from YAML at runtime, so you do not need to write hardcoded task functions.

When you rename or add tasks in `config/tasks.yaml`:

- Update `config/crews.yaml -> <crew> -> task_order` to reflect the new names, or remove `task_order` to run in YAML order.
- Update any `context` arrays in downstream tasks to reference the new task name(s).
- Ensure each task has the required fields: `description` and `expected_output`.

Notes:

- Task names should be valid Python identifiers (e.g., `web_content_research_task`), which is safest across CrewAI versions.
- Tasks are selected by `config/crews.yaml -> <crew> -> task_order`. To disable a task, omit it from `task_order`. If `task_order` is omitted, tasks run in YAML order.
- Map tasks to agents via `config/crews.yaml -> <crew> -> task_agent_map`. If not provided, this template defaults each task to the first crew agent.
- Agents are listed at the crew level in `config/crews.yaml -> <crew> -> agents` and built from `config/agents.yaml`.

### Task enablement and agent mapping

- Remove per-task `enabled` flags; task selection is driven solely by `config/crews.yaml -> <crew> -> task_order`.
- Provide `task_agent_map` to explicitly attach an agent to each task. Example:

```yaml
task_order:
  - web_content_research_task
  - reporting_task
task_agent_map:
  web_content_research_task: researcher
  reporting_task: reporting_analyst
```

If `task_agent_map` is omitted, the template will default tasks to the first agent listed in `config/crews.yaml -> <crew> -> agents`.

### Collaborative multi-agent execution (list mapping and pipelines)

This template supports collaborative work in two ways:

- Single-agent-per-task (default). Map each task to one agent.
- Multi-agent list mapping. Map a task to a list of agents; the task is cloned per agent in that order. The previous clone is passed as context to the next, and only the final clone writes to any `output_file` to avoid duplicates.

Recommended pipeline pattern (Option B): keep tasks focused and connect them via `context`.

Example:

```yaml
# config/tasks.yaml
web_content_research_task:
  description: >
    Conduct thorough research about {topic}.
  expected_output: >
    A concise list of the 5 most relevant bullet points about {topic}.

reporting_task:
  description: >
    Use ONLY the context from web_content_research_task and turn these into a brief, clear section as bullet points.
    Then save the final markdown report to output/report.md.
  expected_output: >
    A markdown report (no code fences) with a short introduction and one section per bullet point.
  context:
    - web_content_research_task
  output_file: output/report.md
```

```yaml
# config/crews.yaml (under your crew)
agents:
  - researcher
  - report_writer

task_order:
  - web_content_research_task
  - reporting_task

task_agent_map:
  web_content_research_task: researcher
  reporting_task: [researcher, report_writer]
```

Behavior:

- The crew runs `web_content_research_task` with `researcher`.
- It then runs `reporting_task` twice: first with `researcher` (receives `web_content_research_task` as context), then with `report_writer` (receives both the research context and the first clone’s output).
- Only the final clone (`report_writer`) writes `output_file: output/report.md`.

Alternate single-task variant (Option A):

```yaml
# config/crews.yaml (under your crew)
task_agent_map:
  web_content_research_task: [researcher, report_writer]

# config/tasks.yaml
web_content_research_task:
  ...
  output_file: output/report.md
```

Notes:

- In Option A, the first clone (researcher) will not write; the final clone (report_writer) will.
- Delegation remains optional; list mapping does not require `allow_delegation` to be true.

## CLI Usage

After installation (`pip install -e .`), the CLI entry point `crew-composer` is available (short alias: `crew-comp`).

- **Launch Streamlit UI**

```powershell
crew-composer ui
# options: crew-composer ui --port 8502 --no-headless
```

- **Validate configs and tool imports**

```powershell
crew-composer validate
```

- **List available tools**

```powershell
crew-composer list-tools
```

- **Show merged configs**

```powershell
crew-composer show-configs
```

- **Run the example crew**

```powershell
crew-composer run --inputs topic="Hello World"
# or JSON
crew-composer run --inputs-json '{"topic": "Hello World"}'
```

Notes:

- The CLI pre-creates directories for any `output_file` defined in `tasks.yaml`.
- You can also use the CrewAI CLI directly:

```powershell
crewai run
```

It auto-detects `@CrewBase` in `src/crew_composer/crew.py`.

### Scheduling via CLI

Manage scheduled runs and the background service:

```powershell
# Start the background scheduler service
crew-composer schedule-service --poll 5

# Create or update schedules
crew-composer schedule-upsert --name Hourly --trigger interval --interval_seconds 3600 --inputs topic="AI"
crew-composer schedule-upsert --name MorningJob --trigger cron --cron-json '{"minute":"0","hour":"8"}'

# List and delete
crew-composer schedule-list
crew-composer schedule-delete <ID>
```

See the full guide: [docs/scheduling.md](docs/scheduling.md)

## MCP Integration

Use `config/mcp_tools.yaml` to declare MCP servers. Enabled servers are connected at startup and their tools are registered dynamically.

Supported transports:

- stdio (requires `mcp` package): uses `command`, `args`, and `env`.
- sse: uses `url` and optional `headers`.
- streamable-http: uses `url` and optional `headers`.

Example (see file for more):

```yaml
servers:
  - name: brave_search
    enabled: true
    transport: sse
    url: http://localhost:8000/sse
    name_prefix: "brave."
    include_tools: []   # only these tool names if provided
    exclude_tools: []   # exclude by name
```

Discovered tools are exposed with a prefix (default: `<name>.`). You can attach them to agents:

```yaml
# config/agents.yaml
researcher:
  tools: ["brave.*"]     # all tools from the server
  # or specific tools
  # tools: ["brave.local_search", "brave.web_search"]
```

Notes:

- `list-tools` shows all resolved tool names including MCP ones.
- If using stdio, install `mcp` (`pip install mcp`). SSE/HTTP do not require it.

## Observability

This template supports config-driven observability using OpenTelemetry and OpenInference, with optional Arize Phoenix integration.

Key implementation points:

- `src/crew_composer/observability.py` initializes tracing and instrumentation (best-effort, optional deps).
- `src/crew_composer/cli.py` initializes observability in `run()` before building tools and crews.
- `src/crew_composer/crew.py` initializes observability in `ConfigDrivenCrew.__init__()` so Streamlit/UI runs are also covered.

### Enable via `config/crews.yaml`

Add an `observability` block under your crew (values shown include defaults):

```yaml
crews:
  default:
    # ... existing config ...
    observability:
      enabled: true
      provider: phoenix  # or "otlp"
      otlp_endpoint: ${OTEL_EXPORTER_OTLP_ENDPOINT:http://127.0.0.1:4318}
      instrument_crewai: true
      instrument_openai: false
      launch_ui: false
```

Notes:

- **provider: phoenix** registers Phoenix’s OpenTelemetry hooks (`phoenix.otel.register()`).
- **provider: otlp** configures a standard OTLP HTTP exporter at `otlp_endpoint` (default `http://127.0.0.1:4318`).
- **instrument_crewai** uses OpenInference to instrument CrewAI spans.
- **instrument_openai** optionally instruments OpenAI client spans via OpenInference.
- **launch_ui** attempts to auto-launch the Phoenix UI when available (best-effort; optional).

### Install optional dependencies (Windows PowerShell)

Make sure you are in your virtual environment (`venv`) before installing:

```powershell
./venv/Scripts/Activate.ps1
python -m pip install \
  openinference-instrumentation-crewai openinference-instrumentation-openai \
  opentelemetry-sdk opentelemetry-exporter-otlp-proto-http \
  phoenix
```

You can also uncomment the optional lines at the bottom of `requirements.txt` and install from there.

### View traces

- With Phoenix: run your Phoenix collector/UI, enable `provider: phoenix`, then run a crew. Spans will appear in Phoenix.
- With OTLP: point `otlp_endpoint` to your collector (e.g., `http://localhost:4318`) and use your preferred UI (e.g., Phoenix, Tempo + Grafana, etc.).

## Troubleshooting

- **ConfigNotFoundError / InvalidConfigError**: Ensure YAML files exist and are valid mappings.
- **ToolImportError**: The `module` or `class` wasn’t importable. Verify `enabled: true` only for real tools.
- **UnsupportedToolError**: A tool name referenced by an agent/task is not defined/enabled.
- **API key errors**: Check `.env` and environment interpolation in YAML.
- **`crewai run` cannot find crew**: Confirm `@CrewBase` class exists in `src/crew_composer/crew.py`.
- **ValidationError: Task missing `description` or `expected_output`**: The task name may have been renamed without updating `task_order`/`context`, or the YAML entry is incomplete. Fix the names and ensure required fields exist.

## Notes on Extensibility

- Add more YAML files and list them in `config/crews.yaml -> <crew> -> tools_files` to merge tool catalogs.
- Add categories in `tools.yaml` freely; names must be unique across all enabled tools.
- Task-level tool overrides are currently disabled for compatibility; attach tools at the agent level.
- You can use wildcards like `serverprefix.*` to attach all tools from a given MCP server.

## License

MIT

Third-party dependencies used by this project are licensed under permissive licenses such as MIT, BSD, or Apache-2.0. When redistributing builds or source, retain the original license texts and notices for those packages (e.g., Apache-2.0 NOTICE requirements for packages like `streamlit`).

For convenience, you may generate an attribution report (e.g., `THIRD_PARTY_LICENSES.txt`) from your current environment using a license scanner. This repository aims to keep such attributions up to date.
