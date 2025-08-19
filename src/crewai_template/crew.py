from __future__ import annotations

import inspect
from pathlib import Path
from typing import List

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from rich.console import Console

from .config_loader import get_project_root, load_agents_config, load_tasks_config, load_crew_config
from .tool_registry import registry

console = Console()


@CrewBase
class ConfigDrivenCrew:
    """Crew driven by YAML configs.

    This class defines two example agents and tasks (Hello World style) to be compatible
    with the CrewAI CLI (`crewai run`). It still loads their definitions dynamically
    from YAML and attaches tools declared in `config/tools.yaml`.
    """

    # CrewAI will load these YAMLs into self.agents_config and self.tasks_config automatically
    # Use absolute paths so resolution is from project root, not package directory
    _BASE_DIR = Path(__file__).resolve().parents[2]
    agents_config = str((_BASE_DIR / "config" / "agents.yaml").resolve())
    tasks_config = str((_BASE_DIR / "config" / "tasks.yaml").resolve())

    def __init__(self) -> None:
        self.root: Path = get_project_root()
        self._tool_registry = registry(self.root)
        self._agents = load_agents_config(self.root)
        self._tasks = load_tasks_config(self.root)
        self._crew_cfg = load_crew_config(self.root)

    # === Agents ===
    @agent
    def researcher(self) -> Agent:
        cfg = self._agents.get("researcher", {})
        tool_names = cfg.get("tool_names", cfg.get("tools", []))
        tools = self._tool_registry.resolve(tool_names) if tool_names else []
        base_cfg = dict(self.agents_config["researcher"])  # type: ignore[index]
        base_cfg.pop("tools", None)
        base_cfg.pop("tool_names", None)
        return Agent(
            config=base_cfg,  # pass agent config without 'tools' key
            verbose=bool(cfg.get("verbose", True)),
            tools=tools,
        )

    @agent
    def reporting_analyst(self) -> Agent:
        cfg = self._agents.get("reporting_analyst", {})
        tool_names = cfg.get("tool_names", cfg.get("tools", []))
        tools = self._tool_registry.resolve(tool_names) if tool_names else []
        base_cfg = dict(self.agents_config["reporting_analyst"])  # type: ignore[index]
        base_cfg.pop("tools", None)
        base_cfg.pop("tool_names", None)
        return Agent(
            config=base_cfg,  # pass agent config without 'tools' key
            verbose=bool(cfg.get("verbose", True)),
            tools=tools,
        )

    # === Tasks ===
    @task
    def research_task(self) -> Task:
        # Use the YAML-driven config only; agent tools apply as defined
        return Task(config=self.tasks_config["research_task"])  # type: ignore[index]

    @task
    def reporting_task(self) -> Task:
        return Task(config=self.tasks_config["reporting_task"])  # type: ignore[index]

    @crew
    def crew(self) -> Crew:
        crew_kwargs = {
            "agents": [self.researcher(), self.reporting_analyst()],
            "tasks": [self.research_task(), self.reporting_task()],
            "process": Process.sequential if str(self._crew_cfg.process).lower() == "sequential" else Process.hierarchical,
            "verbose": self._crew_cfg.verbose,
            "planning": self._crew_cfg.planning,
            "memory": self._crew_cfg.memory,
            "knowledge": self._crew_cfg.knowledge or None,
        }

        # Optional planning LLM support (alias string), compatible with different Crew versions
        if getattr(self._crew_cfg, "planning_llm", None):
            try:
                sig = inspect.signature(Crew.__init__)
                if "planning_llm" in sig.parameters:
                    crew_kwargs["planning_llm"] = self._crew_cfg.planning_llm
                elif "manager_llm" in sig.parameters:
                    crew_kwargs["manager_llm"] = self._crew_cfg.planning_llm
                else:
                    console.print(
                        "[yellow]planning_llm set in config, but Crew() does not accept planning_llm/manager_llm in this version; ignoring[/yellow]"
                    )
            except Exception as e:  # noqa: BLE001
                console.print(
                    f"[yellow]Could not introspect Crew signature ({e}); defaulting to manager_llm[/yellow]"
                )
                crew_kwargs["manager_llm"] = self._crew_cfg.planning_llm

        return Crew(**crew_kwargs)
