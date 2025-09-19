# Streamlit UI

The project includes a Streamlit-based UI to manage configurations, run crews, and review outputs without editing YAML by hand.

## Launch

1. Activate your virtual environment

```powershell
# Windows PowerShell
.\venv\Scripts\Activate.ps1
```

1. Run Streamlit

```powershell
python -m streamlit run app/streamlit_app.py
```

The app title is "Crew Composer Manager".

## Tabs Overview

- Configs
- Knowledge
- Docs
- Outputs
- .env
- About

## Configs

The Configs page provides sub-tabs for the primary YAML files under `config/`:

- Crews
- Agents
- Tasks
- Tools
- MCP Tools

Each sub-tab has two modes:

- Builder (beta): Form-based editor that guides you through valid fields and merges the result back into the YAML file (with a timestamped backup).
- Advanced editor: Raw YAML editing with on-the-fly YAML validation.

### Crews Builder

- Configure `process` (sequential/hierarchical), `verbose`, `memory`, `planning`, `planning_llm`, `manager_llm`, `manager_agent`.
- Define `knowledge` (YAML snippet) and `knowledge_sources`.
- Choose `agents` (allowlist), `task_order`, and `task_agent_map` (including multi-agent lists).
- Select `tools_files` used to load the tool catalog (e.g., `config/tools.yaml`, `config/mcp_tools.yaml`).
- Saves to `config/crews.yaml` and preserves other crews.

### Agents Builder

- Edit role, goal, backstory, `verbose`, `enabled`, `allow_delegation`.
- Configure LLM (`llm`, `llm_temperature`) and limits (`max_rpm`, `max_iter`).
- Optional flags: `cache`, `human_input`, `allow_code_execution`, `multimodal`.
- Select `tool_names` from available tools (discovered from enabled tool specs).
- Saves to `config/agents.yaml` and preserves other agents.

### Tasks Builder

- Edit `description`, `expected_output`.
- Optional: `output_file`, `context` (dependencies on other tasks).
- Saves to `config/tasks.yaml` and preserves other tasks.

### Tools Builder

- Choose or create a category.
- Create or edit tool specs with fields: `name`, `module`, `class`, `enabled`, `args` (YAML mapping), and optional `env` (YAML mapping).
- Quick presets available under "Quick add tool preset" (e.g., `file_read`, `file_write`, `dir_read`, `dir_search`, `web_rag`, `scrape_website`, `scrape_element`).
- Bulk enable/disable: quickly toggle many tools across categories and save changes.
- Saves to `config/tools.yaml` and preserves other categories/items.

### MCP Tools Builder

- Create or edit MCP servers with transports: `stdio`, `sse`, `streamable-http`.
- For `stdio`: configure `command`, `args` (one per line), and `env` (YAML).
- For network transports (`sse`, `streamable-http`): configure `url` and optional `headers` (YAML).
- Control `name_prefix`, `include_tools`, `exclude_tools`, `connect_timeout`.
- Manage optional `tools.mcp_wrappers`.
- Quick presets under "Quick add preset server": Generic (SSE), STDIO (Python), SSE (HTTP), Streamable HTTP.
- Saves to `config/mcp_tools.yaml` and preserves other servers.

Note on stdio transport: requires the `mcp` package installed in the active venv. The UI warns if stdio servers are enabled but `mcp` is missing.

## Validation

At the bottom of the Configs page, use the Validation section to run `crew_composer.config_loader.validate_all()` for the entire project or a selected crew. This catches YAML errors, invalid tool imports, and general config issues before running.

## Run Crew & Live Logs

- Select a crew (or `<auto>`), optionally provide kickoff inputs as JSON or key=value pairs.
- Toggle "Validate before run" to verify configs before starting.
- Output is streamed live into a scrollable log panel.
- After the run finishes, use "Save last run logs" to write a `.log` file to `output/run-logs/` with a default `<timestamp>_<crew>.log` filename.

## Knowledge

- Upload files into `knowledge/` and edit supported text formats directly in the UI.
- YAML files get real-time YAML validation.
- Includes a safe delete with an automatic backup into `backups/`.

## Outputs

- Browse all files under `output/` recursively.
- For Markdown files (`.md`), switch between Rendered and Raw views.
- For `.txt`, `.log`, `.yaml`, `.yml`, and `.csv` files, view raw text (YAML validated).
- For `.json` files, view parsed JSON with fallback to raw on error.
- Download any file.

## Docs

- Browse Markdown files under `docs/` recursively.
- Parsed view only (renders Markdown). Use the download button to save locally.

## .env

- Simple editor mode for the raw `.env`.
- Key-Value editor mode to edit individual keys, add new keys, and save.

## Tips

- Every save creates a timestamped backup in `backups/` to keep your history safe.
- `output/` contents are git-ignored by default.
- Prefer the Builders when possible; they guide you through the expected structure and help avoid typos.
