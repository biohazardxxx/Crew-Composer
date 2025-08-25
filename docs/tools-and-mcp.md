# Tools and MCP Integration

This template dynamically loads tools declared in YAML and discovers MCP tools at startup.

## Static tools (`config/tools.yaml`)

Each tool entry defines the import location and constructor args:

```yaml
- name: file_write
  module: crewai_tools
  class: FileWriterTool
  enabled: true
  args:
    directory: output
  env: {}
```

- Only `enabled: true` tools are instantiated.
- `env` values are exported via `os.environ.setdefault` before constructing the tool.
- Use `config/crews.yaml -> <crew> -> tools_files` to merge multiple tool catalogs.

Attach tools to agents via `config/agents.yaml` under `tool_names` (alias: `tools`):

```yaml
report_writer:
  tool_names: ["file_read","file_write"]
```

Wildcards are supported: `"serverprefix.*"` adds all tools with that prefix.

## MCP servers (`config/mcp_tools.yaml`)

Supported transports:

- `stdio` — requires `mcp` (`pip install mcp`). Uses `command`, `args`, and `env`.
- `sse` — uses `url` and optional `headers`.
- `streamable-http` — uses `url` and optional `headers`.

Example:

```yaml
servers:
  - name: brave_search_mcp
    enabled: true
    transport: sse
    url: http://localhost:8000/sse
    name_prefix: "brave."
    include_tools: []
    exclude_tools: []
    connect_timeout: 60
```

Behavior:

- Tools from each server are registered as `<name_prefix><tool_name>` (prefix defaults to `<name>.`).
- `include_tools` and `exclude_tools` filter by the remote tool name.
- All resolved tools (static + MCP) are visible via `crew-composer list-tools`.
