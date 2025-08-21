# Getting Started

This template is fully configuration-driven. Follow these steps to set it up on Windows with a venv.

## Prerequisites

- Python 3.10+
- Windows PowerShell

## Setup (Windows PowerShell)

```powershell
# 1) Create and activate a virtualenv named venv
py -3.10 -m venv venv
.\venv\Scripts\Activate.ps1

# 2) Install dependencies (recommended for development)
python -m pip install -e .
# or
python -m pip install -r requirements.txt

# 3) Copy env file and set API keys
Copy-Item .env.example .env
# Edit .env to add keys like OPENAI_API_KEY, etc.
```

## Validate and inspect configuration

```powershell
# Validate YAML and tool imports
crewai-template validate

# List all enabled tools (including MCP-discovered ones)
crewai-template list-tools

# Show merged configs
crewai-template show-configs
```

## Run the example crew

```powershell
# Provide dynamic inputs as key=value pairs
crewai-template run --inputs topic="Hello World"

# Or provide JSON
crewai-template run --inputs-json '{"topic": "Hello World"}'

# Alternatively, use the CrewAI CLI from project root
crewai run
```

Notes:

- CLI pre-creates directories for any `output_file` declared in `config/tasks.yaml`.
- `run_async: true` in `config/crew.yaml` makes the CLI run kickoff asynchronously.
