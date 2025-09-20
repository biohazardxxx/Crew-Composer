# Scheduling Runs

This project includes a built‑in scheduler for running crews on a schedule and a self‑service tool that allows agents to create, update, and delete schedules at runtime.

- Storage: `db/schedules.json` (git‑ignored)
- Engine: APScheduler (in‑process background service)
- UI: A Schedules tab is available in the Streamlit app
- CLI: `schedule-*` commands to manage schedules and run the service
- Tool: `schedule_manager` for crews to manage schedules themselves

## Quick Start

1. Create a schedule via CLI

```powershell
# Run once at specific time
crew-composer schedule-upsert --name ReportOnce --trigger date --run_at 2025-09-20T09:00:00 --inputs topic="Daily Report"

# Run hourly
crew-composer schedule-upsert --name Hourly --trigger interval --interval_seconds 3600 --inputs topic="AI"

# Run daily at 08:00 (cron)
crew-composer schedule-upsert --name MorningJob --trigger cron --cron-json '{"minute":"0","hour":"8"}'
```

1. Start the scheduler service

```powershell
crew-composer schedule-service --poll 5
```

1. List or delete schedules

```powershell
crew-composer schedule-list
crew-composer schedule-delete <ID>
```

## Using the Schedules Tab (Streamlit)

- Manage schedules visually: list, create/update, delete.
- Start/stop the background scheduler service from the UI.
- Inputs can be provided as JSON or key=value lines.

Launch the UI:

```powershell
python -m crew_composer.cli ui
```

## Self‑Service Tool (for agents)

A tool is provided so a crew can create, update, delete, or list schedules during execution.

- Tool name: `schedule_manager`
- Module: `crew_composer.tools.schedule_tool`
- Class: `ScheduleManagerTool`

Add to `config/tools.yaml` (already present under the `scheduling` category, disabled by default). Enable it and attach to an agent via `config/agents.yaml`:

```yaml
# config/agents.yaml
scheduler_agent:
  role: Scheduler
  goal: Manage scheduled runs
  backstory: Manages automation schedules for crews
  enabled: true
  tool_names: ["schedule_manager"]
  llm: gpt-4o-mini
```

Usage from an agent prompt (the model will call the tool with JSON input):

```json
{
  "action": "upsert",
  "name": "HourlyResearch",
  "crew": "research",
  "trigger": "interval",
  "interval_seconds": 3600,
  "enabled": true,
  "inputs": {"topic": "AI"}
}
```

Tool actions:

- `list` — returns an array of schedules
- `upsert` — creates or updates an entry
- `delete` — deletes an entry by `id`

Input fields for `upsert`:

- `id` (optional): supply to update an existing entry; omit to create new
- `name` (string): human‑friendly name
- `crew` (string | optional): crew name defined in `config/crews.yaml`; omitted = first crew
- `trigger` ("date" | "interval" | "cron")
- `run_at` (ISO datetime) for `date`
- `interval_seconds` (int) for `interval`
- `cron` (object) for `cron`, e.g. `{ "minute": "0", "hour": "*" }`
- `timezone` (optional; string)
- `enabled` (bool)
- `inputs` (object) kickoff inputs for the crew

## Notes and Best Practices

- The scheduler writes run logs to `output/run-logs/schedule_<id>_<timestamp>.log`.
- The CLI and UI pre‑create directories for any configured task `output_file`s before running.
- Schedules are evaluated by the background service. Make sure it is running to execute jobs.
- For Windows, the UI Start button launches the service as a child process and tracks its PID in the current session only.
- The tool is safe to enable for trusted agents. Consider limiting which agents can access it.
