from __future__ import annotations

import inspect
from pathlib import Path
from typing import List, Optional, Dict

from crewai import Agent, Crew, Process, Task, CrewOutput
from crewai.project import CrewBase, crew, task
from rich.console import Console

from .config_loader import get_project_root, load_agents_config, load_tasks_config, load_crew_config
from .tool_registry import registry
from .knowledge_loader import load_knowledge_config

console = Console()


@CrewBase
class ConfigDrivenCrew:
    """Crew driven by YAML configs.

    Tasks and agents are built dynamically from YAML. No hardcoded task methods are
    required; orchestration is controlled via `config/crew.yaml` and `config/tasks.yaml`.
    Tools are attached based on `config/tools.yaml` and `config/mcp_tools.yaml`.
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
        # Ensure dynamic @task methods exist for YAML-defined tasks (for context resolution)
        self._ensure_dynamic_task_methods()

    # === Agents === (built dynamically in crew() from YAML; no hardcoded @agent methods)

    def _build_task_generic(self, name: str, agent_obj: Optional[Agent] = None) -> Task:
        """Build a Task from YAML config by name and optionally attach an Agent.

        Uses CrewBase-populated `self.tasks_config` when available as the base
        config. Removes YAML-only keys not supported by Task(), like 'enabled'.
        If an `agent_obj` is provided, we attach it either via the Task() argument
        (preferred) or by inserting into the config payload for compatibility
        across CrewAI versions.
        """
        try:
            base_src = dict(self.tasks_config.get(name, {}))  # type: ignore[attr-defined]
        except Exception:
            base_src = {}
        payload = dict(base_src) if isinstance(base_src, dict) else {}
        # Fallback to loader-parsed YAML if CrewBase didn't populate this task (e.g., renamed)
        if not payload:
            try:
                fallback_src = dict(self._tasks.get(name, {}))
            except Exception:
                fallback_src = {}
            if isinstance(fallback_src, dict) and fallback_src:
                payload = dict(fallback_src)
        # Strip keys that are not part of Task config API or that we'll control
        payload.pop("enabled", None)
        payload.pop("tools", None)  # keep task-level tools disabled (agent-level only)
        # Ensure we don't pass a stale string agent from YAML; we'll attach instance
        if agent_obj is not None:
            payload.pop("agent", None)
        # Decide how to attach the agent (constructor vs config injection)
        use_ctor_agent = False
        if agent_obj is not None:
            try:
                sig = inspect.signature(Task.__init__)
                use_ctor_agent = ("agent" in sig.parameters)
            except Exception:
                use_ctor_agent = False
            if not use_ctor_agent:
                # Compatibility: insert instance into config
                payload["agent"] = agent_obj  # type: ignore[assignment]
        # Validate required fields early to provide a clearer error
        if not isinstance(payload, dict) or "description" not in payload or "expected_output" not in payload:
            raise ValueError(
                f"Task '{name}' is incomplete or not found. Ensure it exists in config/tasks.yaml "
                f"with 'description' and 'expected_output'. If you recently renamed it, update "
                f"crew.yaml task_order and any 'context' references in other tasks."
            )
        # Construct the Task
        if use_ctor_agent and agent_obj is not None:
            return Task(config=payload, agent=agent_obj)  # type: ignore[arg-type]
        return Task(config=payload)

    

    

    # === Tasks ===
    # Methods for YAML-defined tasks are synthesized dynamically in __init__ by
    # _ensure_dynamic_task_methods(); no static wrappers are necessary.

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
        llm_temperature_val = cfg.get("llm_temperature", base_cfg.pop("llm_temperature", None))

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
        if llm_temperature_val is not None:
            agent_kwargs["llm_temperature"] = llm_temperature_val
        return Agent(**agent_kwargs)

    @crew
    def crew(self) -> Crew:
        # Build agents, preferring an explicit crew-level allowlist when provided
        agents_list: List[Agent] = []
        built_by_name: Dict[str, Agent] = {}
        crew_agent_names: List[str] = []
        try:
            crew_agent_names = list(getattr(self._crew_cfg, "agents", []) or [])
        except Exception:
            crew_agent_names = []
        if crew_agent_names:
            # Only build the explicitly selected agents
            for name in crew_agent_names:
                if name not in self._agents:
                    console.print(f"[yellow]Warning: crew.agents includes unknown agent '{name}'[/yellow]")
                    continue
                cfg = self._agents.get(name, {})
                # Respect per-agent enabled flag too
                if not bool(cfg.get("enabled", True)):
                    console.print(f"[yellow]Warning: agent '{name}' is disabled but referenced by crew.agents[/yellow]")
                    continue
                agent_obj = self._build_agent_generic(name)
                built_by_name[name] = agent_obj
                agents_list.append(agent_obj)
        else:
            # Default behavior: build all enabled agents from YAML
            for name, cfg in self._agents.items():
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
        # Build enabled agents names for validation without relying on Agent attributes
        enabled_agent_names = set(built_by_name.keys())
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

        # Build tasks dynamically from YAML using crew-level order and mapping
        tasks_list: List[Task] = []
        # Determine task order preference
        try:
            preferred_order: List[str] = list(getattr(self._crew_cfg, "task_order", []) or [])
        except Exception:
            preferred_order = []
        # Build a working list of (name, cfg) preserving YAML order
        yaml_order: List[str] = [t_name for t_name, _ in self._tasks.items()]
        order = preferred_order if preferred_order else yaml_order
        # Build mapping from task -> agent name
        try:
            task_agent_map: Dict[str, str] = dict(getattr(self._crew_cfg, "task_agent_map", {}) or {})
        except Exception:
            task_agent_map = {}

        # Precompute enabled task names from YAML for validation
        enabled_task_names = {t_name for t_name, t_cfg in self._tasks.items() if bool(t_cfg.get("enabled", True))}

        for t_name in order:
            t_cfg = self._tasks.get(t_name)
            if t_cfg is None:
                console.print(f"[yellow]Warning: crew.task_order includes unknown task '{t_name}'[/yellow]")
                continue
            # If a preferred order is provided, we consider it authoritative and run even if task YAML has enabled: false
            if not preferred_order:
                # Only enforce enabled flag when using default YAML order
                if not bool(t_cfg.get("enabled", True)):
                    continue
            # Resolve agent to attach: prefer crew-level map, else fallback to task YAML 'agent'
            agent_name = task_agent_map.get(t_name) or str(t_cfg.get("agent", ""))
            agent_obj: Optional[Agent] = None
            if agent_name:
                agent_obj = built_by_name.get(agent_name)
                if agent_obj is None:
                    # If agent wasn't pre-built (not in crew.agents), try to build it to avoid a hard failure
                    if agent_name in self._agents and bool(self._agents[agent_name].get("enabled", True)):
                        console.print(f"[yellow]Note: building agent '{agent_name}' referenced by task '{t_name}' but not listed in crew.agents[/yellow]")
                        agent_obj = self._build_agent_generic(agent_name)
                        built_by_name[agent_name] = agent_obj
                        agents_list.append(agent_obj)
                    else:
                        console.print(f"[yellow]Warning: Task '{t_name}' references agent '{agent_name}' which is missing or disabled[/yellow]")
                        agent_obj = None

            # Validate context task references
            context_tasks = t_cfg.get("context", [])
            for ctx_task in context_tasks:
                if str(ctx_task) not in enabled_task_names and (preferred_order and str(ctx_task) not in order):
                    console.print(f"[yellow]Warning: Task '{t_name}' references context task '{ctx_task}' which is missing or disabled[/yellow]")

            tasks_list.append(self._build_task_generic(t_name, agent_obj=agent_obj))

        # Fallbacks: if nothing constructed, try enabled YAML tasks; else final hardcoded defaults
        if not tasks_list:
            for t_name, t_cfg in self._tasks.items():
                if bool(t_cfg.get("enabled", True)):
                    agent_name = str(t_cfg.get("agent", ""))
                    agent_obj = built_by_name.get(agent_name)
                    tasks_list.append(self._build_task_generic(t_name, agent_obj=agent_obj))
        if not tasks_list:
            raise ValueError(
                "No tasks configured. Ensure config/tasks.yaml has at least one enabled task "
                "or set crew.task_order in config/crew.yaml."
            )

        # Load knowledge sources from configuration with filtering
        # Semantics:
        # - None (key omitted) => use all available
        # - [] (empty list)    => use none
        # - ["ALL"]            => use all available (explicit)
        # - [list of names]    => use only those
        selected_sources = getattr(self._crew_cfg, 'knowledge_sources', None)
        if isinstance(selected_sources, list) and any(str(s).upper() == "ALL" for s in selected_sources):
            selected_sources = None
        knowledge_sources = load_knowledge_config(self.root, selected_sources=selected_sources)
        
        crew_kwargs = {
            "agents": agents_list,
            "tasks": tasks_list,
            "process": Process.sequential if str(self._crew_cfg.process).lower() == "sequential" else Process.hierarchical,
            "verbose": self._crew_cfg.verbose,
            "planning": self._crew_cfg.planning,
            "memory": self._crew_cfg.memory,
            "knowledge": self._crew_cfg.knowledge or None,
            "knowledge_sources": knowledge_sources,
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

    # ---------- Internal Utilities ----------
    def _ensure_dynamic_task_methods(self) -> None:
        """Dynamically attach minimal @task methods for all YAML-defined tasks.

        CrewAI's CrewBase maps task context names to same-named @task methods.
        To keep the template fully configuration-driven while preserving `context`
        behavior, we synthesize thin wrappers that delegate to `_build_task_generic`.
        """
        for t_name in list(self._tasks.keys()):
            if hasattr(self.__class__, t_name):
                continue
            # Create a new method bound to the class; default arg captures current name
            def _factory(name: str = t_name):  # noqa: ANN001
                def _dyn(self) -> Task:  # type: ignore[override]
                    return self._build_task_generic(name)
                # Ensure function name matches the task name for maximum compatibility
                try:
                    _dyn.__name__ = name  # type: ignore[attr-defined]
                except Exception:
                    pass
                decorated = task(_dyn)
                return decorated
            setattr(self.__class__, t_name, _factory())

