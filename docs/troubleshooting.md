# Troubleshooting

- __InvalidConfigError / ConfigNotFoundError__
  - Ensure YAML files exist and their roots are mappings.
- __ToolImportError__
  - Verify `module` and `class` names, `enabled: true`, and required environment variables.
- __UnsupportedToolError__
  - An agent references a tool name that isn’t enabled/defined.
- __API key errors__
  - Set variables in `.env`, e.g., `OPENAI_API_KEY`, and re-run `crew-composer validate`.
- __`crewai run` cannot find crew__
  - Confirm `@CrewBase` class exists in `src/crew_composer/crew.py` (it does: `ConfigDrivenCrew`).
- __ValidationError: Task missing fields__
  - Ensure every task has `description` and `expected_output`; update `task_order` and `context` if you renamed tasks.
- __Knowledge source errors__
  - Check file paths and install extras (e.g., `docling` for web content).
- __MCP connection issues__
  - For stdio, install `mcp`. Check `url/headers` for network transports. Use `list-tools` to verify discovery.
