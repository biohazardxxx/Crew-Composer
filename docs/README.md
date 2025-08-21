# Documentation - CrewAI Modular Config Template

Welcome to the documentation for the CrewAI Modular Config Template. This template is fully configuration-driven and designed to be extended via YAML, dynamic tool loading, and optional MCP integration.

Use the pages below to get started and tailor the template to your needs.

- Installation: ./installation.md
- Getting Started: ./getting-started.md
- Best Practices: ./best-practices.md
- Configuration Guide: ./configuration.md
- Multi-Agent Task Mapping: ./multi-agent-mapping.md
- CLI Usage: ./cli.md
- Tools and MCP Integration: ./tools-and-mcp.md
- Knowledge Sources: ./knowledge-sources.md
- Troubleshooting: ./troubleshooting.md
- FAQ: ./faq.md

Quick facts:

- Fully config-driven tasks and orchestration using `config/tasks.yaml` and `config/crew.yaml`.
- Agents are specified at the crew level; map tasks to agents with `task_agent_map`.
- No hardcoded `@task`, `@agent` or `@tool` functions needed! Task, agent and tool wrappers are synthesized dynamically from YAML task names for context resolution.
- Windows-first setup instructions with `venv` are provided.
