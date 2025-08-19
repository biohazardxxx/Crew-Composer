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
│  ├─ crew.yaml
│  ├─ tools.yaml
│  └─ mcp_tools.yaml
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
```

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
- `config/tasks.yaml`: Descriptions, expected outputs, default agent, context deps, and optional `output_file`.
- `config/crew.yaml`: Process (`sequential`/`hierarchical`), verbosity, planning, memory, knowledge, and `tools_files` list.
- `config/tools.yaml`: CrewAi default tool categories with entries `{ name, module, class, enabled, args, env }`.
- `config/mcp_tools.yaml`: MCP servers and tool wrappers. Disabled by default.

Environment variables in configs use `${VAR}` or `${VAR:default}` and resolve from your `.env` and OS env.

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

## Notes on Extensibility

- Add more YAML files and list them in `crew.yaml.tools_files` to merge tool catalogs.
- Add categories in `tools.yaml` freely; names must be unique across all enabled tools.
- Task-level tool overrides are currently disabled for compatibility; attach tools at the agent level.
- You can use wildcards like `serverprefix.*` to attach all tools from a given MCP server.

## License

MIT
