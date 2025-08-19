from __future__ import annotations

import inspect
from pathlib import Path
from typing import List

from crewai import Agent, Crew, Process, Task, CrewOutput
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
        # Support optional per-agent cache setting; remove from base_cfg to avoid duplication
        cache_val = cfg.get("cache", base_cfg.pop("cache", None))
        # Support optional per-agent human_input; remove from base_cfg to avoid duplication
        human_input_val = cfg.get("human_input", base_cfg.pop("human_input", None))
        # Support optional code execution allowance
        allow_code_execution_val = cfg.get("allow_code_execution", base_cfg.pop("allow_code_execution", None))
        # Additional optional fields
        multimodal_val = cfg.get("multimodal", base_cfg.pop("multimodal", None))
        max_rpm_val = cfg.get("max_rpm", base_cfg.pop("max_rpm", None))
        max_iter_val = cfg.get("max_iter", base_cfg.pop("max_iter", None))
        agent_kwargs = {
            "config": base_cfg,  # pass agent config without 'tools' key
            "verbose": bool(cfg.get("verbose", True)),
            "tools": tools,
        }
        # Pass through optional fields (project pins CrewAI minimum version)
        if cache_val is not None:
            agent_kwargs["cache"] = cache_val
        if human_input_val is not None:
            agent_kwargs["human_input"] = human_input_val
        if allow_code_execution_val is not None:
            agent_kwargs["allow_code_execution"] = allow_code_execution_val
        if multimodal_val is not None:
            agent_kwargs["multimodal"] = multimodal_val
        if max_rpm_val is not None:
            agent_kwargs["max_rpm"] = max_rpm_val
        if max_iter_val is not None:
            agent_kwargs["max_iter"] = max_iter_val
        return Agent(**agent_kwargs)

    def _build_task_generic(self, name: str) -> Task:
        """Build a Task from YAML config by name.

        Uses CrewBase-populated `self.tasks_config` when available as the base
        config. Removes YAML-only keys not supported by Task(), like 'enabled'.
        """
        try:
            base_src = dict(self.tasks_config.get(name, {}))  # type: ignore[attr-defined]
        except Exception:
            base_src = {}
        payload = dict(base_src) if isinstance(base_src, dict) else {}
        # Strip keys that are not part of Task config API
        payload.pop("enabled", None)
        payload.pop("tools", None)  # keep task-level tools disabled (agent-level only)
        return Task(config=payload)

    @agent
    def reporting_analyst(self) -> Agent:
        cfg = self._agents.get("reporting_analyst", {})
        tool_names = cfg.get("tool_names", cfg.get("tools", []))
        tools = self._tool_registry.resolve(tool_names) if tool_names else []
        base_cfg = dict(self.agents_config["reporting_analyst"])  # type: ignore[index]
        base_cfg.pop("tools", None)
        base_cfg.pop("tool_names", None)
        # Support optional per-agent cache setting; remove from base_cfg to avoid duplication
        cache_val = cfg.get("cache", base_cfg.pop("cache", None))
        # Support optional per-agent human_input; remove from base_cfg to avoid duplication
        human_input_val = cfg.get("human_input", base_cfg.pop("human_input", None))
        # Support optional code execution allowance
        allow_code_execution_val = cfg.get("allow_code_execution", base_cfg.pop("allow_code_execution", None))
        # Additional optional fields
        multimodal_val = cfg.get("multimodal", base_cfg.pop("multimodal", None))
        max_rpm_val = cfg.get("max_rpm", base_cfg.pop("max_rpm", None))
        max_iter_val = cfg.get("max_iter", base_cfg.pop("max_iter", None))
        agent_kwargs = {
            "config": base_cfg,  # pass agent config without 'tools' key
            "verbose": bool(cfg.get("verbose", True)),
            "tools": tools,
        }
        # Pass through optional fields (project pins CrewAI minimum version)
        if cache_val is not None:
            agent_kwargs["cache"] = cache_val
        if human_input_val is not None:
            agent_kwargs["human_input"] = human_input_val
        if allow_code_execution_val is not None:
            agent_kwargs["allow_code_execution"] = allow_code_execution_val
        if multimodal_val is not None:
            agent_kwargs["multimodal"] = multimodal_val
        if max_rpm_val is not None:
            agent_kwargs["max_rpm"] = max_rpm_val
        if max_iter_val is not None:
            agent_kwargs["max_iter"] = max_iter_val
        return Agent(**agent_kwargs)

    @agent
    def summary_analyst(self) -> Agent:
        cfg = self._agents.get("summary_analyst", {})
        tool_names = cfg.get("tool_names", cfg.get("tools", []))
        tools = self._tool_registry.resolve(tool_names) if tool_names else []
        base_cfg = dict(self.agents_config["summary_analyst"])  # type: ignore[index]
        base_cfg.pop("tools", None)
        base_cfg.pop("tool_names", None)
        cache_val = cfg.get("cache", base_cfg.pop("cache", None))
        human_input_val = cfg.get("human_input", base_cfg.pop("human_input", None))
        allow_code_execution_val = cfg.get("allow_code_execution", base_cfg.pop("allow_code_execution", None))
        multimodal_val = cfg.get("multimodal", base_cfg.pop("multimodal", None))
        max_rpm_val = cfg.get("max_rpm", base_cfg.pop("max_rpm", None))
        max_iter_val = cfg.get("max_iter", base_cfg.pop("max_iter", None))
        agent_kwargs = {
            "config": base_cfg,
            "verbose": bool(cfg.get("verbose", True)),
            "tools": tools,
        }
        if cache_val is not None:
            agent_kwargs["cache"] = cache_val
        if human_input_val is not None:
            agent_kwargs["human_input"] = human_input_val
        if allow_code_execution_val is not None:
            agent_kwargs["allow_code_execution"] = allow_code_execution_val
        if multimodal_val is not None:
            agent_kwargs["multimodal"] = multimodal_val
        if max_rpm_val is not None:
            agent_kwargs["max_rpm"] = max_rpm_val
        if max_iter_val is not None:
            agent_kwargs["max_iter"] = max_iter_val
        return Agent(**agent_kwargs)

    # === Tasks ===
    @task
    def research_task(self) -> Task:
        # Use the YAML-driven config only; agent tools apply as defined
        return Task(config=self.tasks_config["research_task"])  # type: ignore[index]

    @task
    def reporting_task(self) -> Task:
        return Task(config=self.tasks_config["reporting_task"])  # type: ignore[index]

    def _build_agent_generic(self, name: str) -> Agent:
        """Build an Agent from YAML config by name.

        Uses values from `self._agents[name]` as runtime overrides and
        falls back to the CrewBase-populated `self.agents_config[name]`.
        """
        cfg = self._agents.get(name, {})
        tool_names = cfg.get("tool_names", cfg.get("tools", []))
        tools = self._tool_registry.resolve(tool_names) if tool_names else []
        # Base agent configuration from CrewBase-loaded YAML if available
        try:
            base_src = dict(self.agents_config.get(name, {}))  # type: ignore[attr-defined]
        except Exception:
            base_src = {}
        base_cfg = dict(base_src) if isinstance(base_src, dict) else {}
        base_cfg.pop("tools", None)
        base_cfg.pop("tool_names", None)
        base_cfg.pop("enabled", None)
        # Build config payload, falling back to cleaned per-run cfg when base is absent
        if base_cfg:
            config_payload = base_cfg
        else:
            cfg_clean = dict(cfg) if isinstance(cfg, dict) else {}
            for k in ("tools", "tool_names", "enabled"):
                cfg_clean.pop(k, None)
            config_payload = cfg_clean
        # Ensure a stable name for mapping tasks->agents
        if isinstance(config_payload, dict) and "name" not in config_payload:
            config_payload["name"] = name

        # Optional fields
        cache_val = cfg.get("cache", base_cfg.pop("cache", None))
        human_input_val = cfg.get("human_input", base_cfg.pop("human_input", None))
        allow_code_execution_val = cfg.get("allow_code_execution", base_cfg.pop("allow_code_execution", None))
        multimodal_val = cfg.get("multimodal", base_cfg.pop("multimodal", None))
        max_rpm_val = cfg.get("max_rpm", base_cfg.pop("max_rpm", None))
        max_iter_val = cfg.get("max_iter", base_cfg.pop("max_iter", None))

        agent_kwargs = {
            "config": config_payload,
            "verbose": bool(cfg.get("verbose", True)),
            "tools": tools,
        }
        if cache_val is not None:
            agent_kwargs["cache"] = cache_val
        if human_input_val is not None:
            agent_kwargs["human_input"] = human_input_val
        if allow_code_execution_val is not None:
            agent_kwargs["allow_code_execution"] = allow_code_execution_val
        if multimodal_val is not None:
            agent_kwargs["multimodal"] = multimodal_val
        if max_rpm_val is not None:
            agent_kwargs["max_rpm"] = max_rpm_val
        if max_iter_val is not None:
            agent_kwargs["max_iter"] = max_iter_val
        return Agent(**agent_kwargs)

    @crew
    def crew(self) -> Crew:
        # Build agents dynamically from YAML config (supports any custom agent)
        agents_list: List[Agent] = []
        built_by_name = {}
        for name, cfg in self._agents.items():
            # Skip agents explicitly disabled in YAML
            try:
                enabled = bool(cfg.get("enabled", True)) if isinstance(cfg, dict) else True
            except Exception:
                enabled = True
            if not enabled:
                continue
            agent_obj = self._build_agent_generic(name)
            built_by_name[name] = agent_obj
            agents_list.append(agent_obj)

        # Optional manager agent by name from config; ensure present even if disabled
        manager_agent_name = getattr(self._crew_cfg, "manager_agent", None)
        manager_agent_obj = None
        # Build enabled agents list and map for validation
        enabled_agent_names = {a.name for a in agents_list}  # type: ignore[attr-defined]
        enabled_task_names = {t_name for t_name, t_cfg in self._tasks.items() if bool(t_cfg.get("enabled", True))}
        for t_name, t_cfg in self._tasks.items():
            if not bool(t_cfg.get("enabled", True)):
                continue
            agent_ref = str(t_cfg.get("agent", ""))
            if agent_ref and agent_ref not in enabled_agent_names:
                console.print(f"[yellow]Warning: Task '{t_name}' references agent '{agent_ref}' which is missing or disabled[/yellow]")
            # Validate context task references
            context_tasks = t_cfg.get("context", [])
            for ctx_task in context_tasks:
                if str(ctx_task) not in enabled_task_names:
                    console.print(f"[yellow]Warning: Task '{t_name}' references context task '{ctx_task}' which is missing or disabled[/yellow]")

        if manager_agent_name:
            manager_agent_obj = built_by_name.get(str(manager_agent_name))
            if manager_agent_obj is None:
                manager_agent_obj = self._build_agent_generic(str(manager_agent_name))
                if all(a is not manager_agent_obj for a in agents_list):
                    agents_list.append(manager_agent_obj)

        # Build tasks dynamically from YAML (preserve YAML order)
        tasks_list: List[Task] = []
        for t_name, t_cfg in self._tasks.items():
            try:
                t_enabled = bool(t_cfg.get("enabled", True)) if isinstance(t_cfg, dict) else True
            except Exception:
                t_enabled = True
            if not t_enabled:
                continue
            tasks_list.append(self._build_task_generic(t_name))
        # Fallback: if no tasks constructed (e.g., empty YAML), use defaults
        if not tasks_list:
            tasks_list = [self.research_task(), self.reporting_task()]

        crew_kwargs = {
            "agents": agents_list,
            "tasks": tasks_list,
            "process": Process.sequential if str(self._crew_cfg.process).lower() == "sequential" else Process.hierarchical,
            "verbose": self._crew_cfg.verbose,
            "planning": self._crew_cfg.planning,
            "memory": self._crew_cfg.memory,
            "knowledge": self._crew_cfg.knowledge or None,
        }
        if manager_agent_obj is not None:
            crew_kwargs["manager_agent"] = manager_agent_obj
        # Always pass manager_llm (default set in config model)
        if getattr(self._crew_cfg, "manager_llm", None):
            crew_kwargs["manager_llm"] = self._crew_cfg.manager_llm

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

        # Enforce hierarchical requirement: either manager_agent or manager_llm must be provided
        if str(self._crew_cfg.process).lower() == "hierarchical":
            if manager_agent_obj is None and not getattr(self._crew_cfg, "manager_llm", None):
                raise ValueError("Either manager_agent or manager_llm must be set when using the hierarchical process.")

        return Crew(**crew_kwargs)

    async def kickoff_async(self, inputs: dict) -> CrewOutput:
        """Kick off the configured crew asynchronously."""
        c = self.crew()
        return await c.kickoff_async(inputs=inputs)
