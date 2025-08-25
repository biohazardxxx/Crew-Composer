# Multi-Agent Task Mapping

Map tasks to one agent or a list of agents in `config/crews.yaml -> <crew> -> task_agent_map`.

## Single agent per task (default)

```yaml
task_agent_map:
  web_content_research_task: researcher
  reporting_task: report_writer
```

## List mapping (clone-and-chain)

Map a task to multiple agents to create a small pipeline. The task is cloned per agent in order; each subsequent clone receives the previous clone as additional context. Only the final clone writes to any `output_file`.

```yaml
task_agent_map:
  reporting_task: [researcher, report_writer]
```

Recommended pattern: keep tasks focused and connect them via `context` in `config/tasks.yaml`.

```yaml
# config/tasks.yaml
reporting_task:
  description: >
    Use ONLY the context from web_content_research_task to produce a short report.
  expected_output: >
    Markdown report.
  context:
    - web_content_research_task
  output_file: output/report.md
```

## Execution behavior

- The crew runs tasks according to `task_order`.
- For list-mapped tasks, clones run in sequence across the listed agents.
- The previous clone is appended to context for the next clone automatically.
- Only the final clone retains `output_file` to avoid duplicate writes.
- If a task is unmapped, it defaults to the first agent in `config/crews.yaml -> <crew> -> agents`.

## Tips

- Prefer small tasks + `context` over a single giant task.
- Agent names must exist in `config/agents.yaml` (enabled). If a listed agent isn’t in `crew.agents`, the runtime attempts to build it automatically and will warn.
