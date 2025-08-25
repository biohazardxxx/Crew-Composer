# CrewAI Modular Config Template

A modular, configuration-driven template for building CrewAI apps that are easy to update, extend, and integrate with tools and MCP. Ships with a Typer-based CLI and is compatible with the CrewAI CLI (`crewai run`).

## Features

- **Config-first**: Define agents, tasks, crew, and tools entirely in YAML under `config/`.
- **Tool registry**: Dynamically import and instantiate tools from YAML; supports env var interpolation in args.
- **MCP-ready**: Placeholders and guidance to wire MCP servers and wrappers via config.
- **MCP dynamic tools**: Connect to MCP servers (stdio, SSE, streamable HTTP) from config and auto-register their tools.
- **CLI**: `crewai-template` for validate/list/run/show and `crewai run` compatibility.
- **Validation**: Pydantic-backed validation, clear error messages.
- **.env support**: Environment variable interpolation like `${VAR}` or `${VAR:default}`.

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
│  └─ crewai_template/
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

After installation (`pip install -e .`), the CLI entry point `crewai-template` is available.

- **Validate configs and tool imports**

```powershell
crewai-template validate
```

- **List available tools**

```powershell
crewai-template list-tools
```

- **Show merged configs**

```powershell
crewai-template show-configs
```

- **Run the example crew**

```powershell
crewai-template run --inputs topic="Hello World"
# or JSON
crewai-template run --inputs-json '{"topic": "Hello World"}'
```

Notes:

- The CLI pre-creates directories for any `output_file` defined in `tasks.yaml`.
- You can also use the CrewAI CLI directly:

```powershell
crewai run
```

It auto-detects `@CrewBase` in `src/crewai_template/crew.py`.

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

## Troubleshooting

- **ConfigNotFoundError / InvalidConfigError**: Ensure YAML files exist and are valid mappings.
- **ToolImportError**: The `module` or `class` wasn’t importable. Verify `enabled: true` only for real tools.
- **UnsupportedToolError**: A tool name referenced by an agent/task is not defined/enabled.
- **API key errors**: Check `.env` and environment interpolation in YAML.
- **`crewai run` cannot find crew**: Confirm `@CrewBase` class exists in `src/crewai_template/crew.py`.
- **ValidationError: Task missing `description` or `expected_output`**: The task name may have been renamed without updating `task_order`/`context`, or the YAML entry is incomplete. Fix the names and ensure required fields exist.

## Notes on Extensibility

- Add more YAML files and list them in `config/crews.yaml -> <crew> -> tools_files` to merge tool catalogs.
- Add categories in `tools.yaml` freely; names must be unique across all enabled tools.
- Task-level tool overrides are currently disabled for compatibility; attach tools at the agent level.
- You can use wildcards like `serverprefix.*` to attach all tools from a given MCP server.

## License

MIT
