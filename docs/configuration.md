# Configuration Guide

All behavior is driven by YAML under `config/`. No hardcoded task functions are required; the crew and tasks are synthesized dynamically from configuration.

## Files

- `config/agents.yaml` — Agent definitions (LLM, tools, behavior).
- `config/tasks.yaml` — Task definitions (description, expected_output, context, optional output_file).
- `config/crew.yaml` — Orchestration (agents list, task order, task→agent mapping, knowledge, etc.).
- `config/tools.yaml` — Static tool catalog (module/class/args/env).
- `config/mcp_tools.yaml` — MCP server connections and optional wrappers.
- `config/agents.knowledge.yaml` — Knowledge source registry.

Environment variables inside YAML use `${VAR}` or `${VAR:default}` and are resolved from `.env` and the OS environment.

---

## Agents (`config/agents.yaml`)

Example:

```yaml
researcher:
  role: "Researcher"
  goal: "Find concise facts on {topic}"
  backstory: "Efficient analyst focused on brevity."
  verbose: false
  allow_delegation: true
  enabled: true
  tool_names: ["web_rag","file_write"]  # alias: 'tools' also works
  llm: gpt-4o-mini
  llm_temperature: 0
  max_iter: 5
```

Notes:

- Use `tool_names` (or `tools`) to attach tool names. Wildcards are supported (e.g., `"brave.*"`).
- `enabled: false` hides an agent unless referenced by a task mapping (the runtime will attempt to build it if needed).
- Agent names are referenced in `crew.yaml -> agents` and `crew.yaml -> task_agent_map`.

---

## Tasks (`config/tasks.yaml`)

Example:

```yaml
web_content_research_task:
  description: >
    Conduct a thorough research about {topic}.
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

Notes:

- Required fields: `description`, `expected_output`.
- Optional: `context` (list of task names), `output_file`.
- Do NOT set `agent` here. Mapping is done in `crew.yaml -> task_agent_map`.
- Per-task `enabled` flags are not used. Task selection is controlled by `crew.yaml -> task_order`.
- Task methods are generated dynamically from names; ensure names are valid Python identifiers.

---

## Crew (`config/crew.yaml`)

Key fields:

```yaml
process: sequential          # sequential | hierarchical
verbose: false
planning: false              # keep disabled to reduce token usage (default here)
memory: false
planning_llm: gpt-4o-mini
manager_llm: gpt-4o-mini     # required if hierarchical and no manager_agent
# manager_agent: summary_analyst

tools_files:
  - config/tools.yaml
  - config/mcp_tools.yaml

agents:
  - researcher
  - report_writer

task_order:
  - web_content_research_task
  - reporting_task

task_agent_map:
  web_content_research_task: researcher
  reporting_task: [researcher, report_writer]

# Knowledge source selection (see knowledge-sources.md)
knowledge_sources: []  # [], ["ALL"], or [names...]
run_async: false
```

Semantics:

- `agents` — allowlist of agents to instantiate for this crew. If omitted, all enabled agents are built.
- `task_order` — the only mechanism to select/sequence tasks. If omitted, runs tasks in YAML order.
- `task_agent_map` — map each task to an agent name or a list of agents (see multi-agent-mapping.md).
  - If omitted for a task, it defaults to the first agent in `agents`.
- `knowledge_sources` — selection filter for sources in `config/agents.knowledge.yaml`:
  - `[]` => none, `null`/omitted => all, `["ALL"]` => all, or a list of keys.

---

## Tools (`config/tools.yaml`)

Each tool entry:

```yaml
- name: file_write
  module: crewai_tools
  class: FileWriterTool
  enabled: true
  args:
    directory: output
  env: {}
```

- Only tools with `enabled: true` are instantiated.
- `env` entries are set with `os.environ.setdefault` prior to construction.
- You can add categories and multiple files; list them in `crew.yaml -> tools_files`.

---

## MCP (`config/mcp_tools.yaml`)

Server spec fields:

```yaml
servers:
  - name: brave_search_mcp
    enabled: false
    transport: sse             # stdio | sse | streamable-http
    url: http://localhost:8000/sse
    name_prefix: "brave."
    include_tools: []
    exclude_tools: []
    connect_timeout: 60
```

- stdio requires `mcp` (`pip install mcp`).
- Discovered tools are registered with `name_prefix` (default `<name>.`).
- Use include/exclude filters to control which tools are exposed.

---

## Knowledge (`config/agents.knowledge.yaml`)

Declare reusable sources (see knowledge-sources.md). Selection is controlled via `crew.yaml -> knowledge_sources`.
