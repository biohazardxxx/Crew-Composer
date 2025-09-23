from __future__ import annotations

import inspect
import copy
from pathlib import Path
from typing import List, Optional, Dict, Any

from crewai import Agent, Crew, Process, Task, CrewOutput
from crewai.project import CrewBase, crew, task
from rich.console import Console

from .config_loader import get_project_root, load_agents_config, load_tasks_config, load_crew_config
from .tool_registry import registry
from .knowledge_loader import load_knowledge_config
from .observability import init_observability

console = Console()


@CrewBase
class ConfigDrivenCrew:
    """Crew driven by YAML configs.

    Tasks and agents are built dynamically from YAML. No hardcoded task methods are
    required; orchestration is controlled via `config/crews.yaml` and `config/tasks.yaml`.
    Tools are attached based on `config/tools.yaml` and `config/mcp_tools.yaml`.
    """

    # CrewAI will load these YAMLs into self.agents_config and self.tasks_config automatically
    # Use absolute paths so resolution is from project root, not package directory
    _BASE_DIR = Path(__file__).resolve().parents[2]
    agents_config = str((_BASE_DIR / "config" / "agents.yaml").resolve())
    tasks_config = str((_BASE_DIR / "config" / "tasks.yaml").resolve())

    def __init__(self, crew_name: Optional[str] = None) -> None:
        self.root: Path = get_project_root()
        self._agents = load_agents_config(self.root)
        self._tasks = load_tasks_config(self.root)
        self._crew_cfg = load_crew_config(self.root, crew_name)
        # Initialize observability (best-effort) as early as possible so instrumentation wraps CrewAI
        try:
            init_observability(getattr(self._crew_cfg, "observability", {}))
        except Exception:
            # Observability is optional; proceed silently if setup fails
            pass
        # Build registry with the tools for the selected crew
        self._tool_registry = registry(self.root, self._crew_cfg.tools_files)
        # Ensure dynamic @task methods exist for YAML-defined tasks (for context resolution)
        self._ensure_dynamic_task_methods()

    # === Agents === (built dynamically in crew() from YAML; no hardcoded @agent methods)

    def _build_task_generic(self, name: str, agent_obj: Optional[Agent] = None, context_objs: Optional[List[Task]] = None, suppress_output_file: bool = False) -> Task:
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
        if suppress_output_file:
            payload.pop("output_file", None)
        # Ensure we don't pass a stale string agent from YAML; we'll attach instance
        if agent_obj is not None:
            payload.pop("agent", None)
        # Decide how to attach the agent (constructor vs config injection)
        use_ctor_agent = False
        can_pass_context = False
        try:
            sig = inspect.signature(Task.__init__)
            use_ctor_agent = (agent_obj is not None and ("agent" in sig.parameters))
            can_pass_context = ("context" in sig.parameters)
            can_pass_human = ("human_input" in sig.parameters)
        except Exception:
            use_ctor_agent = False
            can_pass_context = False
            can_pass_human = False
        if agent_obj is not None and not use_ctor_agent:
            # Compatibility: insert instance into config
            payload["agent"] = agent_obj  # type: ignore[assignment]
        # Validate required fields early to provide a clearer error
        if not isinstance(payload, dict) or "description" not in payload or "expected_output" not in payload:
            raise ValueError(
                f"Task '{name}' is incomplete or not found. Ensure it exists in config/tasks.yaml "
                f"with 'description' and 'expected_output'. If you recently renamed it, update "
                f"crews.yaml task_order for the selected crew and any 'context' references in other tasks."
            )
        # Prepare optional kwargs supported by current CrewAI version
        optional_kwargs: Dict[str, Any] = {}
        if can_pass_human:
            try:
                human_val = payload.get("human_input", None)
            except Exception:
                human_val = None
            if human_val is not None:
                optional_kwargs["human_input"] = human_val

        # Construct the Task with optional context objects and human_input when supported
        if use_ctor_agent and can_pass_context and context_objs:
            return Task(config=payload, agent=agent_obj, context=context_objs, **optional_kwargs)  # type: ignore[arg-type]
        if use_ctor_agent and agent_obj is not None:
            t = Task(config=payload, agent=agent_obj, **optional_kwargs)  # type: ignore[arg-type]
        elif can_pass_context and context_objs:
            t = Task(config=payload, context=context_objs, **optional_kwargs)
        else:
            t = Task(config=payload, **optional_kwargs)
        # As a fallback, try to set context attribute post-construction if supported
        if context_objs:
            try:
                existing = list(getattr(t, "context", []) or [])
                t.context = existing + context_objs  # type: ignore[attr-defined]
            except Exception:
                pass
        return t

    

    

    # === Tasks ===
    # Methods for YAML-defined tasks are synthesized dynamically in __init__ by
    # _ensure_dynamic_task_methods(); no static wrappers are necessary.

    def _build_agent_generic(self, name: str) -> Agent:
        """Build an Agent from YAML config by name.

        Uses values from `self._agents[name]` as runtime overrides and
        falls back to the CrewBase-populated `self.agents_config[name]`.
        """
        cfg = self._agents.get(name, {})

        # --- Helper: clone tools safely (avoid deepcopy issues with locks/RLocks) ---
        def _safe_clone_tool(obj: Any) -> Any:
            try:
                return copy.deepcopy(obj)
            except Exception:
                try:
                    # Shallow copy preserves internal locks by reference and avoids pickling
                    return copy.copy(obj)
                except Exception:
                    # As a last resort, reuse the same instance (most tools are stateless)
                    return obj

        # Build tools with support for per-agent flags (e.g., result_as_answer)
        tools: List[Any] = []
        tools_cfg = cfg.get("tools", None)
        tool_names_legacy = cfg.get("tool_names", None)
        if isinstance(tools_cfg, list) and tools_cfg:
            for item in tools_cfg:
                if isinstance(item, str):
                    # Support wildcard resolution; deep-copy to avoid shared state across agents
                    resolved = self._tool_registry.resolve([item])
                    tools.extend(_safe_clone_tool(t) for t in resolved)
                elif isinstance(item, dict) and "name" in item:
                    resolved = self._tool_registry.resolve([str(item["name"])])
                    for base_tool in resolved:
                        inst = _safe_clone_tool(base_tool)
                        # Apply supported per-tool flags
                        if "result_as_answer" in item:
                            try:
                                setattr(inst, "result_as_answer", bool(item["result_as_answer"]))
                            except Exception:
                                # Best-effort; ignore if tool doesn't support the attribute
                                pass
                        tools.append(inst)
                else:
                    # Unknown entry type; skip silently to be permissive
                    continue
        else:
            # Legacy support: simple list of names in 'tool_names' or 'tools'
            names = tool_names_legacy or cfg.get("tools", [])
            if isinstance(names, list) and names:
                resolved = self._tool_registry.resolve(names)
                tools = [_safe_clone_tool(t) for t in resolved]

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
        # Build mapping from task -> agent name(s); allow string or list values
        try:
            task_agent_map: Dict[str, Any] = dict(getattr(self._crew_cfg, "task_agent_map", {}) or {})
        except Exception:
            task_agent_map = {}

        # Precompute enabled task names from YAML for validation
        enabled_task_names = {t_name for t_name, t_cfg in self._tasks.items() if bool(t_cfg.get("enabled", True))}

        # Track built Task objects by base name for resolving YAML context to Task instances
        built_tasks_by_name: Dict[str, List[Task]] = {}

        def _resolve_context_objs(names: List[str]) -> List[Task]:
            out: List[Task] = []
            for nm in names:
                try:
                    lst = built_tasks_by_name.get(str(nm), [])
                    if lst:
                        out.append(lst[-1])
                except Exception:
                    continue
            return out

        for t_name in order:
            t_cfg = self._tasks.get(t_name)
            if t_cfg is None:
                console.print(f"[yellow]Warning: crew.task_order includes unknown task '{t_name}'[/yellow]")
                continue
            # Determine agents for this task (single or list)
            mapping_val = task_agent_map.get(t_name, None)
            agent_names: List[str]
            if isinstance(mapping_val, (list, tuple)):
                agent_names = [str(a).strip() for a in mapping_val if str(a).strip()]
            elif isinstance(mapping_val, str) and mapping_val.strip():
                agent_names = [mapping_val.strip()]
            else:
                # Default to the first crew agent to satisfy Crew validation in sequential process
                if agents_list:
                    # Try to get the first agent's declared name
                    first_cfg = getattr(agents_list[0], "config", {}) or {}
                    first_name = first_cfg.get("name") or next(iter(built_by_name.keys()), "")
                    if first_name:
                        console.print(f"[yellow]Note: no agent mapping for task '{t_name}'; defaulting to first crew agent '{first_name}'[/yellow]")
                        agent_names = [str(first_name)]
                    else:
                        agent_names = []
                else:
                    agent_names = []

            # Resolve YAML-declared context names to built Task objects (latest instances)
            declared_ctx_names: List[str] = list(t_cfg.get("context", []) or [])
            base_ctx_objs: List[Task] = _resolve_context_objs(declared_ctx_names)

            # Build one or more concrete tasks based on agent_names. If multiple,
            # chain them so each subsequent clone receives the previous clone as context.
            prev_clone: Optional[Task] = None
            if not agent_names:
                t_obj = self._build_task_generic(t_name, agent_obj=None, context_objs=base_ctx_objs)
                tasks_list.append(t_obj)
                built_tasks_by_name.setdefault(t_name, []).append(t_obj)
                continue

            for idx, agent_name in enumerate(agent_names):
                agent_obj = built_by_name.get(agent_name)
                if agent_obj is None:
                    # If agent wasn't pre-built (not in crew.agents), try to build it to avoid a hard failure
                    agent_cfg = self._agents.get(agent_name, {})
                    if agent_cfg and bool(agent_cfg.get("enabled", True)):
                        console.print(f"[yellow]Note: building agent '{agent_name}' referenced by task '{t_name}' but not listed in crew.agents[/yellow]")
                        agent_obj = self._build_agent_generic(agent_name)
                        built_by_name[agent_name] = agent_obj
                        agents_list.append(agent_obj)
                    else:
                        console.print(f"[yellow]Warning: Task '{t_name}' references agent '{agent_name}' which is missing or disabled[/yellow]")
                        continue

                ctx_objs: List[Task] = list(base_ctx_objs)
                if idx > 0 and prev_clone is not None:
                    ctx_objs.append(prev_clone)

                # Only final clone should keep any YAML-defined output_file to avoid multiple writes
                is_last = (idx == len(agent_names) - 1)
                t_obj = self._build_task_generic(
                    t_name,
                    agent_obj=agent_obj,
                    context_objs=ctx_objs,
                    suppress_output_file=(not is_last),
                )
                tasks_list.append(t_obj)
                built_tasks_by_name.setdefault(t_name, []).append(t_obj)
                prev_clone = t_obj
        if not tasks_list:
            raise ValueError(
                "No tasks configured. Ensure config/tasks.yaml has at least one enabled task "
                "or set crew.task_order in config/crews.yaml for the selected crew."
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
                # Prefer Pydantic model field introspection (Crew is a Pydantic model)
                field_names: list[str] = []
                try:
                    mf = getattr(Crew, "model_fields", None)
                    if isinstance(mf, dict):
                        field_names = list(mf.keys())
                    else:
                        legacy = getattr(Crew, "__fields__", None)
                        if isinstance(legacy, dict):
                            field_names = list(legacy.keys())
                except Exception:
                    field_names = []

                if field_names:
                    if "planning_llm" in field_names:
                        crew_kwargs["planning_llm"] = self._crew_cfg.planning_llm
                    elif "manager_llm" in field_names:
                        crew_kwargs["manager_llm"] = self._crew_cfg.planning_llm
                    else:
                        console.print(
                            "[yellow]planning_llm set in config, but Crew() model has no planning_llm/manager_llm field; ignoring[/yellow]"
                        )
                else:
                    # Fallback: try signature-based detection for non-Pydantic implementations
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
                    f"[yellow]Could not introspect Crew fields/signature ({e}); defaulting to manager_llm[/yellow]"
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

