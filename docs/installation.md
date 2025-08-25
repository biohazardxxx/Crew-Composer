# Installation (Windows)

This project targets Windows first. Use a Python virtual environment named `venv` for all commands.

## Requirements

- Windows 10/11
- Python 3.10+ (3.10 or 3.11 recommended)
- PowerShell

## Steps

1. Create and activate a virtual environment

```powershell
py -3.10 -m venv venv
.\venv\Scripts\Activate.ps1
```

1. Upgrade pip (recommended)

```powershell
python -m pip install -U pip
```

1. Install the package and dependencies (pick one)

- Editable install (best for development):

```powershell
python -m pip install -e .
```

- From requirements.txt:

```powershell
python -m pip install -r requirements.txt
```

1. Configure environment variables

```powershell
Copy-Item .env.example .env
# Edit .env and set your API keys, e.g. OPENAI_API_KEY
```

1. Optional extras

- STDIO MCP servers require the `mcp` package:

```powershell
python -m pip install mcp
```

- Web content knowledge source uses Docling (optional):

```powershell
python -m pip install docling
```

## Verification

- Validate configuration and tool imports:

```powershell
crew-composer validate
```

- List resolved tools (including MCP tools if enabled):

```powershell
crew-composer list-tools
```

- Run example crew:

```powershell
crew-composer run --inputs topic="Hello World"
```

- You can also run via CrewAI CLI (auto-detects the crew):

```powershell
crewai run
```

## Common issues

- Execution policy prevents activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

- Missing API keys or environment variables: check `.env` and use `${VAR}` or `${VAR:default}` in YAML.
- If using STDIO MCP servers and you skipped `mcp`, the project will continue but those servers will be skipped.
