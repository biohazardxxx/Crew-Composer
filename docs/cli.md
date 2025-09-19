# CLI Usage

After installing (`pip install -e .`), the entry point `crew-composer` is available (alias: `crew-comp`).

## Commands

- `crew-composer ui [--port PORT] [--no-headless]`
  - Launch the Streamlit UI packaged in `crew_composer.ui.app` from the project root.
  - Options:
    - `--port PORT` (default: 8501)
    - `--headless / --no-headless` (default: headless)
  - Examples:

```powershell
# Start the UI on the default port in headless mode
crew-composer ui

# Start on a custom port and allow Streamlit to open a browser window
crew-composer ui --port 8502 --no-headless
```

- `crew-composer validate [--crew NAME]`
  - Validate YAML files, load tools (including MCP), and print success or errors. If `--crew` is omitted, the first crew in `config/crews.yaml` is used.
- `crew-composer list-tools [--crew NAME]`
  - Print all resolved tool names (static + MCP-discovered) for the selected crew.
- `crew-composer show-configs [--crew NAME]`
  - Print merged agents, tasks, and the selected crew config. Also lists available crews and marks the default/selected one.
- `crew-composer run [--crew NAME] [--inputs k=v ...] [--inputs-json JSON]`
  - Run the selected crew with kickoff inputs. Examples:

```powershell
# Select a crew explicitly
crew-composer validate --crew research
crew-composer list-tools --crew research
crew-composer show-configs --crew research

# Run with inputs
crew-composer run --crew research --inputs topic="Hello World"
crew-composer run --inputs-json '{"topic":"Hello World"}'
```

Notes:

- The CLI creates directories for any `output_file` paths before running.
- Set `run_async: true` in `config/crews.yaml` (under the selected crew) to use async kickoff.
- You can also run with the CrewAI CLI:

```powershell
crewai run
```
