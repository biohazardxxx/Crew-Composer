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

## Scheduling Commands

These commands manage scheduled runs and the scheduler service. Schedules are stored in `db/schedules.json` (git-ignored by default).

- `crew-composer schedule-service [--poll SECONDS]`
  - Start the background scheduler service that watches the schedules file and executes jobs.
  - Options:
    - `--poll` (default: 5) seconds between schedule file checks.

- `crew-composer schedule-list`
  - Print all schedules as JSON.

- `crew-composer schedule-upsert [options]`
  - Create or update a schedule. Options:
    - `--id` Optional ID (omit to create a new schedule)
    - `--name` Human-friendly name
    - `--crew` Crew name (defaults to first crew when omitted)
    - `--trigger` `date` | `interval` | `cron` (default: `date`)
    - `--run_at` ISO datetime for `date` trigger (e.g., `2025-09-19T10:00:00`)
    - `--interval_seconds` Integer seconds for `interval` trigger
    - `--cron-json` JSON object for cron fields, e.g. `{ "minute": "0", "hour": "*" }`
    - `--timezone` Optional timezone name (not required; default system)
    - `--enabled / --no-enabled` Enable the schedule (default: enabled)
    - `--inputs-json` JSON object for kickoff inputs
    - `--inputs` one or more `key=value` pairs for inputs

  - Examples:

```powershell
# Run once at a given time using the default crew
crew-composer schedule-upsert --name ReportOnce --trigger date --run_at 2025-09-20T09:00:00 --inputs topic="Daily Report"

# Run every hour for the 'research' crew
crew-composer schedule-upsert --name HourlyResearch --crew research --trigger interval --interval_seconds 3600 --inputs topic="AI"

# Run daily at 08:00 using cron
crew-composer schedule-upsert --name MorningJob --trigger cron --cron-json '{"minute":"0","hour":"8"}'
```

- `crew-composer schedule-delete ID`
  - Delete a schedule by its `id`.
