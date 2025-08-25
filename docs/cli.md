# CLI Usage

After installing (`pip install -e .`), the entry point `crewai-template` is available.

## Commands

- `crewai-template validate [--crew NAME]`
  - Validate YAML files, load tools (including MCP), and print success or errors. If `--crew` is omitted, the first crew in `config/crews.yaml` is used.
- `crewai-template list-tools [--crew NAME]`
  - Print all resolved tool names (static + MCP-discovered) for the selected crew.
- `crewai-template show-configs [--crew NAME]`
  - Print merged agents, tasks, and the selected crew config. Also lists available crews and marks the default/selected one.
- `crewai-template run [--crew NAME] [--inputs k=v ...] [--inputs-json JSON]`
  - Run the selected crew with kickoff inputs. Examples:

```powershell
# Select a crew explicitly
crewai-template validate --crew research
crewai-template list-tools --crew research
crewai-template show-configs --crew research

# Run with inputs
crewai-template run --crew research --inputs topic="Hello World"
crewai-template run --inputs-json '{"topic":"Hello World"}'
```

Notes:

- The CLI creates directories for any `output_file` paths before running.
- Set `run_async: true` in `config/crews.yaml` (under the selected crew) to use async kickoff.
- You can also run with the CrewAI CLI:

```powershell
crewai run
```
