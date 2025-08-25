# FAQ

- __How do I map tasks to agents?__
  - Use `config/crews.yaml -> <crew> -> task_agent_map`. Values can be a string (single agent) or a list (multi-agent pipeline).

- __How do I disable a task?__
  - Remove it from `config/crews.yaml -> <crew> -> task_order`. Per-task `enabled` flags are not used.

- __Can I attach tools to tasks?__
  - Not in this template. Attach tools at the agent level via `config/agents.yaml -> tool_names`.

- __How do I rename a task safely?__
  - Update `task_order` and any `context` references to the new name. Ensure `description` and `expected_output` exist.

- __Do I need to list all agents in `crews.yaml -> <crew> -> agents`?__
  - Recommended. If `task_agent_map` references an enabled agent not listed, the runtime will attempt to build it and warn.

- __How do I run hierarchical crews?__
  - Set `process: hierarchical` and provide either `manager_agent` or `manager_llm` in `config/crews.yaml` (under the selected crew).

- __How do I attach all tools from an MCP server?__
  - Use a wildcard prefix like `"brave.*"` in `tool_names`.

- __Where are outputs saved?__
  - Wherever `output_file` points in `config/tasks.yaml`. The CLI ensures directories exist before running.

- __Is planning enabled?__
  - No. `planning` defaults to `false` to keep token usage low.

