# CLI Usage

After installing (`pip install -e .`), the entry point `crewai-template` is available.

## Commands

- `crewai-template validate`
  - Validate YAML files, load tools (including MCP), and print success or errors.
- `crewai-template list-tools`
  - Print all resolved tool names (static + MCP-discovered).
- `crewai-template show-configs`
  - Print merged agents, tasks, and crew configs for debugging.
- `crewai-template run [--inputs k=v ...] [--inputs-json JSON]`
  - Run the crew with kickoff inputs. Examples:

```powershell
crewai-template run --inputs topic="Hello World"
crewai-template run --inputs-json '{"topic":"Hello World"}'
```

Notes:

- The CLI creates directories for any `output_file` paths before running.
- Set `run_async: true` in `config/crew.yaml` to use async kickoff.
- You can also run with the CrewAI CLI:

```powershell
crewai run
```
