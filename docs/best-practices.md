# Best Practices

Practical guidance to keep your config-driven crew maintainable, robust, and easy to evolve.

## YAML conventions

- Use snake_case for keys and names, e.g. `web_content_research_task`.
- Task names should be valid Python identifiers for maximal compatibility.
- Keep task entries concise: at minimum `description` and `expected_output`.
- Prefer explicit mapping in `config/crews.yaml` (under your selected crew):
  - `task_order` controls which tasks run and in what order.
  - `task_agent_map` binds tasks to agents; can be a single agent or a list for collaborative cloning.

## Task design

- Keep tasks single-responsibility and composable.
- Use `context` to pass downstream dependencies:

```yaml
reporting_task:
  description: Create a brief report using only the research context.
  expected_output: A markdown section with bullet points.
  context:
    - web_content_research_task
  output_file: output/report.md
```

- Only the final step should write `output_file` (the template enforces this for cloned tasks).
- Provide clear `expected_output` for better model alignment.

## Agent design

- Keep `role`, `goal`, and `backstory` short and specific.
- Tune `llm_temperature` conservatively (0–0.7 for most tasks).
- Use `verbose: true` temporarily when debugging; revert for normal runs.
- Limit `max_iter` to prevent runaway loops.

## Tools

- Attach tools at the agent level via `tool_names`.
- Keep tool sets minimal and purposeful; avoid loading everything by default.
- Use `crew-composer list-tools` to verify which tool names are available (including MCP tools with prefixes).

## MCP integration

- Prefer SSE/HTTP transports when possible; use STDIO only when needed (requires `mcp`).
- Use `name_prefix` to avoid collisions and make discovery predictable, e.g. `brave.`.
- Filter noisy tools with `include_tools`/`exclude_tools`.
- In agents, you can reference all tools from a server with a wildcard, e.g. `"brave.*"`.

## Knowledge sources

- Place local data under the `knowledge/` directory. Relative paths are normalized for you.
- Provide the correct fields per source type:
  - `text_file`, `pdf`, `csv`, `excel`, `json`, `string`, `web_content` (Docling optional).
- Example (CSV):

```yaml
knowledge_sources:
  products:
    type: csv
    file_path: knowledge/products.csv
    source_column: description
    metadata_columns: [id, name]
```

- If a path doesn’t exist, the loader will raise a clear error. Fix the file location or update the YAML.

## Environment and secrets

- Copy `.env.example` to `.env` and set API keys (e.g., `OPENAI_API_KEY`).
- Use `${VAR}` or `${VAR:default}` in YAML for robust config.
- Do not commit `.env`.

## Orchestration hints

- Collaborative list mapping creates per-agent clones of a task, passing prior clone outputs forward. Only the final clone writes to disk.
- Prefer pipelines of focused tasks connected via `context` to keep prompts short and grounded.
- Use `run_async` in `crews.yaml` (under the selected crew) only when your environment and tools are safe for concurrency.

## Debugging

- `crew-composer validate` to verify YAML and imports.
- `crew-composer show-configs` to inspect merged configs.
- Turn `verbose: true` on specific agents to audit reasoning for that segment.
