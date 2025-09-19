from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
import sys
from pathlib import Path
from typing import Dict, List

import streamlit as st
import yaml
from dotenv import dotenv_values

from .utils import (
    BACKUP_DIR,
    CONFIG_DIR,
    DOCS_DIR,
    ENV_FILE,
    KNOWLEDGE_DIR,
    OUTPUT_DIR,
    PROJECT_ROOT,
    RUN_LOGS_DIR,
    cfg,
    get_available_tool_names,
    list_knowledge_files,
    list_yaml_files,
    mcp_stdio_required_warning,
    read_text,
    render_scrollable_logs,
    safe_write_text,
    yaml_is_valid,
)


# ----- Builders (imported from original app) -----

def crews_yaml_builder_ui(selected_path: Path) -> None:
    try:
        existing = yaml.safe_load(read_text(selected_path) or "") or {}
    except Exception as e:  # noqa: BLE001
        st.error(f"Failed to parse existing YAML: {e}")
        existing = {}

    crews_map = {}
    if isinstance(existing, dict):
        crews_map = dict(existing.get("crews", {}) or {})

    try:
        agents_cfg = cfg.load_agents_config(PROJECT_ROOT) if cfg else {}
        agent_names = list(agents_cfg.keys()) if isinstance(agents_cfg, dict) else []
    except Exception:  # noqa: BLE001
        agent_names = []
    try:
        tasks_cfg = cfg.load_tasks_config(PROJECT_ROOT) if cfg else {}
        task_names = list(tasks_cfg.keys()) if isinstance(tasks_cfg, dict) else []
    except Exception:  # noqa: BLE001
        task_names = []

    existing_crew_names = list(crews_map.keys())
    choice = st.selectbox("Select crew to edit", ["<create new>"] + existing_crew_names, key="builder_crew_select")
    if choice == "<create new>":
        new_name = st.text_input("New crew name", key="builder_new_crew_name")
        if not new_name:
            st.info("Enter a new crew name to begin.")
            return
        crew_name = new_name
        current = {}
    else:
        crew_name = choice
        current = crews_map.get(crew_name, {}) if isinstance(crews_map, dict) else {}

    st.markdown("### Crew settings")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        process = st.selectbox(
            "process",
            ["sequential", "hierarchical"],
            index=0 if str(current.get("process", "sequential")).lower() == "sequential" else 1,
        )
        verbose = st.checkbox("verbose", value=bool(current.get("verbose", True)), key=f"crews_verbose_{crew_name}")
        memory = st.checkbox("memory", value=bool(current.get("memory", False)), key=f"crews_memory_{crew_name}")
        run_async = st.checkbox("run_async", value=bool(current.get("run_async", False)), key=f"crews_run_async_{crew_name}")
    with col_b:
        planning = st.checkbox("planning", value=bool(current.get("planning", False)), key=f"crews_planning_{crew_name}")
        planning_llm = st.text_input("planning_llm", value=str(current.get("planning_llm", "")))
        manager_llm = st.text_input("manager_llm", value=str(current.get("manager_llm", "gpt-4o-mini")))
        manager_agent = st.text_input("manager_agent (name)", value=str(current.get("manager_agent", "")))
    with col_c:
        st.caption("knowledge (YAML mapping)")
        knowledge_yaml = st.text_area(
            "knowledge",
            value=yaml.safe_dump(current.get("knowledge", {}) or {}, sort_keys=False),
            height=120,
            key="builder_knowledge",
        )
        ks_list = current.get("knowledge_sources", None)
        ks_csv_default = ", ".join(ks_list) if isinstance(ks_list, list) else ""
        knowledge_sources_csv = st.text_input("knowledge_sources (comma-separated)", value=ks_csv_default)

    st.markdown("### Agents and tasks")
    selected_agents = st.multiselect(
        "crew.agents (allowlist; empty = build all enabled agents)",
        options=agent_names,
        default=list(current.get("agents", []) or []),
    )
    ordered_tasks = st.multiselect(
        "crew.task_order (order matters)", options=task_names, default=list(current.get("task_order", []) or task_names)
    )

    with st.expander("Task to agent mapping", expanded=False):
        task_agent_map: Dict[str, List[str]] = {}
        existing_map = current.get("task_agent_map", {}) if isinstance(current, dict) else {}
        for t in ordered_tasks:
            default_for_t = existing_map.get(t, [])
            if isinstance(default_for_t, str):
                default_for_t = [default_for_t]
            sel = st.multiselect(f"Agents for task '{t}'", options=agent_names, default=list(default_for_t or []), key=f"map_{t}")
            if sel:
                task_agent_map[t] = sel

    st.markdown("### Tool files")
    default_tools_files = current.get("tools_files", ["config/tools.yaml", "config/mcp_tools.yaml"]) or []
    tools_files = st.multiselect("tools_files", options=["config/tools.yaml", "config/mcp_tools.yaml"], default=default_tools_files)

    try:
        knowledge_obj = yaml.safe_load(knowledge_yaml or "") or {}
        if not isinstance(knowledge_obj, dict):
            st.error("knowledge must be a YAML mapping (dict)")
            return
    except Exception as e:  # noqa: BLE001
        st.error(f"Invalid knowledge YAML: {e}")
        return

    ks_clean = [s.strip() for s in (knowledge_sources_csv or "").split(",") if s.strip()]
    crew_obj: Dict[str, object] = {
        "process": process,
        "verbose": verbose,
        "planning": planning,
        "planning_llm": planning_llm or None,
        "manager_llm": manager_llm or None,
        "memory": memory,
        "knowledge": knowledge_obj,
        "knowledge_sources": ks_clean if ks_clean else None,
        "run_async": run_async,
        "manager_agent": manager_agent or None,
        "agents": selected_agents,
        "task_order": ordered_tasks,
        "task_agent_map": task_agent_map,
        "tools_files": tools_files or ["config/tools.yaml", "config/mcp_tools.yaml"],
    }
    crew_obj = {k: v for k, v in crew_obj.items() if v is not None}
    updated_map = dict(crews_map)
    updated_map[crew_name] = crew_obj
    out_payload = {"crews": updated_map}

    st.markdown("### Preview")
    preview = yaml.safe_dump(out_payload, sort_keys=False, allow_unicode=True)
    st.code(preview, language="yaml")

    if st.button("Save crews.yaml (with backup)", type="primary", key="builder_save_crews"):
        ok, info = safe_write_text(selected_path, preview)
        (st.success if ok else st.error)(info)


def mcp_tools_yaml_builder_ui(selected_path: Path) -> None:
    with st.expander("Quick add preset server", expanded=False):
        preset_choice = st.selectbox(
            "Preset",
            [
                "<select>",
                "Generic (SSE)",
                "STDIO (Python)",
                "SSE (HTTP)",
                "Streamable HTTP",
            ],
            key="mcp_preset_choice",
        )
        preset_name = st.text_input("Server name for preset", value="example_server", key="mcp_preset_name")
        if st.button(
            "Add preset server",
            key="mcp_add_preset_btn",
            disabled=(preset_choice == "<select>" or not preset_name),
        ):
            try:
                existing_all = yaml.safe_load(read_text(selected_path) or "") or {}
                if not isinstance(existing_all, dict):
                    existing_all = {}
                servers_list = list(existing_all.get("servers", []) or [])

                def preset_spec(preset: str) -> Dict[str, object]:
                    if preset == "STDIO (Python)":
                        return {
                            "name": preset_name,
                            "enabled": True,
                            "transport": "stdio",
                            "command": "python",
                            "args": ["servers/your_server.py"],
                            "env": {"UV_PYTHON": "3.12"},
                        }
                    if preset in ("SSE (HTTP)", "Generic (SSE)"):
                        return {
                            "name": preset_name,
                            "enabled": True,
                            "transport": "sse",
                            "url": "http://localhost:8000/sse",
                            "headers": {},
                        }
                    if preset == "Streamable HTTP":
                        return {
                            "name": preset_name,
                            "enabled": True,
                            "transport": "streamable-http",
                            "url": "http://localhost:8001/mcp",
                            "headers": {},
                        }
                    return {
                        "name": preset_name,
                        "enabled": True,
                        "transport": "sse",
                        "url": "http://localhost:8000/sse",
                        "headers": {},
                    }

                spec = preset_spec(preset_choice)
                replaced = False
                for i, s in enumerate(servers_list):
                    if isinstance(s, dict) and str(s.get("name", "")) == preset_name:
                        servers_list[i] = spec
                        replaced = True
                        break
                if not replaced:
                    servers_list.append(spec)
                payload = dict(existing_all)
                payload["servers"] = servers_list
                ok, info = safe_write_text(
                    selected_path, yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
                )
                (st.success if ok else st.error)(info)
            except Exception as e:  # noqa: BLE001
                st.error(f"Failed to add preset: {e}")
    try:
        existing = yaml.safe_load(read_text(selected_path) or "") or {}
    except Exception as e:  # noqa: BLE001
        st.error(f"Failed to parse existing YAML: {e}")
        existing = {}
    if not isinstance(existing, dict):
        existing = {}

    servers = list(existing.get("servers", []) or [])
    server_names = []
    for s in servers:
        if isinstance(s, dict):
            nm = str(s.get("name", "")).strip()
            if nm:
                server_names.append(nm)

    choice = st.selectbox("Select server", ["<create new>"] + server_names, key="mcp_builder_select")
    if choice == "<create new>":
        server_name = st.text_input("New server name", key="mcp_builder_new_name")
        if not server_name:
            st.info("Enter a server name to begin.")
            return
        current = {}
    else:
        server_name = choice
        current = {}
        for s in servers:
            if isinstance(s, dict) and str(s.get("name", "")) == server_name:
                current = dict(s)
                break

    st.markdown("### Server configuration")
    col1, col2, col3 = st.columns(3)
    with col1:
        enabled = st.checkbox("enabled", value=bool(current.get("enabled", True)), key=f"mcp_enabled_{server_name}")
        transport = st.selectbox(
            "transport",
            ["stdio", "sse", "streamable-http"],
            index={"stdio": 0, "sse": 1, "streamable-http": 2}.get(
                str(current.get("transport", "stdio")).lower(), 0
            ),
        )
        name_prefix = st.text_input("name_prefix (optional)", value=str(current.get("name_prefix", "")))
    with col2:
        include_tools_text = st.text_area(
            "include_tools (one per line)",
            value="\n".join(current.get("include_tools", []) or []),
            height=120,
            key=f"mcp_include_{server_name}",
        )
        exclude_tools_text = st.text_area(
            "exclude_tools (one per line)",
            value="\n".join(current.get("exclude_tools", []) or []),
            height=120,
            key=f"mcp_exclude_{server_name}",
        )
    with col3:
        connect_timeout_str = st.text_input("connect_timeout (seconds, optional)", value=str(current.get("connect_timeout", "")))

    stdio_block = transport == "stdio"
    net_block = transport in ("sse", "streamable-http")

    if stdio_block:
        st.markdown("### stdio settings")
        cmd = st.text_input("command", value=str(current.get("command", "python")))
        args_list_text = st.text_area(
            "args (one per line)",
            value="\n".join(current.get("args", []) or []),
            height=100,
            key=f"mcp_args_{server_name}",
        )
        env_yaml = st.text_area(
            "env (YAML mapping)",
            value=yaml.safe_dump(current.get("env", {}) or {}, sort_keys=False),
            height=120,
            key=f"mcp_env_{server_name}",
        )
        try:
            env_obj = yaml.safe_load(env_yaml or "") or {}
            if not isinstance(env_obj, dict):
                st.error("env must be a YAML mapping (dict)")
                return
        except Exception as e:  # noqa: BLE001
            st.error(f"Invalid env YAML: {e}")
            return
    else:
        env_obj = None
        args_list_text = ""
        cmd = ""

    if net_block:
        st.markdown("### network settings")
        url = st.text_input("url", value=str(current.get("url", "")))
        headers_yaml = st.text_area(
            "headers (YAML mapping)",
            value=yaml.safe_dump(current.get("headers", {}) or {}, sort_keys=False),
            height=120,
            key=f"mcp_headers_{server_name}",
        )
        try:
            headers_obj = yaml.safe_load(headers_yaml or "") or {}
            if not isinstance(headers_obj, dict):
                st.error("headers must be a YAML mapping (dict)")
                return
        except Exception as e:  # noqa: BLE001
            st.error(f"Invalid headers YAML: {e}")
            return
    else:
        headers_obj = None
        url = ""

    def _parse_int_optional(s: str):
        s = (s or "").strip()
        if not s:
            return None
        try:
            return int(s)
        except Exception:  # noqa: BLE001
            return None

    spec: Dict[str, object] = {
        "name": server_name,
        "enabled": enabled,
        "transport": transport,
    }
    if name_prefix.strip():
        spec["name_prefix"] = name_prefix.strip()
    inc = [ln.strip() for ln in (include_tools_text or "").splitlines() if ln.strip()]
    exc = [ln.strip() for ln in (exclude_tools_text or "").splitlines() if ln.strip()]
    if inc:
        spec["include_tools"] = inc
    if exc:
        spec["exclude_tools"] = exc
    ct = _parse_int_optional(connect_timeout_str)
    if ct is not None:
        spec["connect_timeout"] = ct

    if stdio_block:
        spec["command"] = cmd
        args_list = [ln.strip() for ln in (args_list_text or "").splitlines() if ln.strip()]
        if args_list:
            spec["args"] = args_list
        if env_obj:
            spec["env"] = env_obj

    if net_block:
        if url.strip():
            spec["url"] = url.strip()
        if headers_obj:
            spec["headers"] = headers_obj

    new_servers = list(servers)
    replaced = False
    for i, s in enumerate(new_servers):
        if isinstance(s, dict) and str(s.get("name", "")) == server_name:
            new_servers[i] = spec
            replaced = True
            break
    if not replaced:
        new_servers.append(spec)

    with st.expander("MCP wrappers (optional)", expanded=False):
        wrappers_existing = []
        try:
            wrappers_existing = list(existing.get("tools", {}).get("mcp_wrappers", []) or [])
        except Exception:  # noqa: BLE001
            wrappers_existing = []
        wrappers_text = st.text_area(
            "mcp_wrappers (one per line)",
            value="\n".join([str(x) for x in wrappers_existing]),
            height=100,
            key="mcp_wrappers_text",
        )
        wrappers_list = [ln.strip() for ln in (wrappers_text or "").splitlines() if ln.strip()]

    out_payload: Dict[str, object] = {"servers": new_servers}
    tools_block = dict(existing.get("tools", {}) or {})
    tools_block["mcp_wrappers"] = wrappers_list
    out_payload["tools"] = tools_block

    st.markdown("### Preview")
    preview = yaml.safe_dump(out_payload, sort_keys=False, allow_unicode=True)
    st.code(preview, language="yaml")

    if st.button("Save mcp_tools.yaml (with backup)", type="primary", key="mcp_builder_save"):
        ok, info = safe_write_text(selected_path, preview)
        (st.success if ok else st.error)(info)


def tasks_yaml_builder_ui(selected_path: Path) -> None:
    try:
        existing = yaml.safe_load(read_text(selected_path) or "") or {}
    except Exception as e:  # noqa: BLE001
        st.error(f"Failed to parse existing YAML: {e}")
        existing = {}
    if not isinstance(existing, dict):
        existing = {}

    task_names = list(existing.keys())
    choice = st.selectbox("Select task to edit", ["<create new>"] + task_names, key="tasks_builder_select")
    if choice == "<create new>":
        task_name = st.text_input("New task name", key="tasks_builder_new_name")
        if not task_name:
            st.info("Enter a new task name to begin.")
            return
        current = {}
    else:
        task_name = choice
        current = dict(existing.get(task_name, {}) or {})

    st.markdown("### Task configuration")
    col1, col2 = st.columns(2)
    with col1:
        description = st.text_area("description", value=str(current.get("description", "")), height=140)
        expected_output = st.text_area("expected_output", value=str(current.get("expected_output", "")), height=140)
        output_file = st.text_input("output_file (optional)", value=str(current.get("output_file", "")))
    with col2:
        enabled = st.checkbox("enabled", value=bool(current.get("enabled", True)), key=f"tasks_enabled_{task_name}")
        available_tasks = [t for t in task_names if t != task_name]
        default_ctx = list(current.get("context", []) or [])
        context = st.multiselect("context (task dependencies)", options=available_tasks, default=default_ctx)

    task_obj: Dict[str, object] = {
        "description": description,
        "expected_output": expected_output,
        "enabled": enabled,
    }
    if (output_file or "").strip():
        task_obj["output_file"] = (output_file or "").strip()
    if context:
        task_obj["context"] = context

    updated_tasks = dict(existing)
    updated_tasks[task_name] = task_obj
    preview = yaml.safe_dump(updated_tasks, sort_keys=False, allow_unicode=True)

    st.markdown("### Preview")
    st.code(preview, language="yaml")

    if st.button("Save tasks.yaml (with backup)", type="primary", key="tasks_builder_save"):
        ok, info = safe_write_text(selected_path, preview)
        (st.success if ok else st.error)(info)


def tools_yaml_builder_ui(selected_path: Path) -> None:
    with st.expander("Quick add tool preset", expanded=False):
        try:
            existing_all = yaml.safe_load(read_text(selected_path) or "") or {}
        except Exception:  # noqa: BLE001
            existing_all = {}
        tools_map_all = dict(existing_all.get("tools", {}) or {})
        categories_all = list(tools_map_all.keys())
        preset_category_mode = st.radio("Category", ["Existing", "New"], horizontal=True, key="tools_preset_cat_mode")
        if preset_category_mode == "Existing" and categories_all:
            preset_category = st.selectbox("Select category", categories_all, key="tools_preset_category")
        else:
            preset_category = st.text_input("New category name", value="file_document_management", key="tools_preset_new_category")

        preset_tool_choice = st.selectbox(
            "Tool preset",
            [
                "<select>",
                "file_read",
                "file_write",
                "dir_read",
                "dir_search",
                "web_rag",
                "scrape_website",
                "scrape_element",
            ],
            key="tools_preset_choice",
        )
        preset_tool_name = st.text_input("Tool name", value="file_read", key="tools_preset_name")
        if st.button(
            "Add preset tool",
            key="tools_add_preset_btn",
            disabled=(preset_tool_choice == "<select>" or not preset_category or not preset_tool_name),
        ):
            try:
                def tool_spec(name: str) -> Dict[str, object]:
                    base = {"name": preset_tool_name, "module": "crewai_tools", "enabled": True, "args": {}}
                    mapping = {
                        "file_read": {**base, "class": "FileReadTool"},
                        "file_write": {**base, "class": "FileWriterTool", "args": {"directory": "output"}},
                        "dir_read": {**base, "class": "DirectoryReadTool", "args": {"directory": "output"}},
                        "dir_search": {**base, "class": "DirectorySearchTool", "args": {"directory": "output"}},
                        "web_rag": {**base, "class": "WebsiteSearchTool"},
                        "scrape_website": {**base, "class": "ScrapeWebsiteTool"},
                        "scrape_element": {**base, "class": "ScrapeElementFromWebsiteTool"},
                    }
                    return mapping.get(name, base)

                spec = tool_spec(preset_tool_choice)
                category_items = list(tools_map_all.get(preset_category, []) or [])
                replaced = False
                for i, it in enumerate(category_items):
                    if isinstance(it, dict) and str(it.get("name", "")) == preset_tool_name:
                        category_items[i] = spec
                        replaced = True
                        break
                if not replaced:
                    category_items.append(spec)
                tools_map_all[preset_category] = category_items
                payload = {"tools": tools_map_all}
                ok, info = safe_write_text(
                    selected_path, yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
                )
                (st.success if ok else st.error)(info)
            except Exception as e:  # noqa: BLE001
                st.error(f"Failed to add preset tool: {e}")
    try:
        existing = yaml.safe_load(read_text(selected_path) or "") or {}
    except Exception as e:  # noqa: BLE001
        st.error(f"Failed to parse existing YAML: {e}")
        existing = {}
    if not isinstance(existing, dict):
        existing = {}
    tools_map = dict(existing.get("tools", {}) or {})

    categories = list(tools_map.keys())
    cat_choice = st.selectbox("Select category", ["<create new category>"] + categories, key="tools_builder_category")
    if cat_choice == "<create new category>":
        category = st.text_input("New category name", key="tools_builder_new_category")
        if not category:
            st.info("Enter a category name to begin.")
            return
        items = []
    else:
        category = cat_choice
        items = list(tools_map.get(category, []) or [])

    existing_names = [str(i.get("name", "")) for i in items if isinstance(i, dict)]
    tool_choice = st.selectbox("Select tool", ["<create new tool>"] + existing_names, key="tools_builder_tool")
    if tool_choice == "<create new tool>":
        tool_name = st.text_input("New tool name", key="tools_builder_new_tool")
        if not tool_name:
            st.info("Enter a tool name to begin.")
            return
        current = {}
    else:
        tool_name = tool_choice
        found = {}
        for it in items:
            if isinstance(it, dict) and str(it.get("name", "")) == tool_name:
                found = it
                break
        current = dict(found or {})

    st.markdown("### Tool configuration")
    col1, col2 = st.columns(2)
    with col1:
        module = st.text_input("module", value=str(current.get("module", "")))
        class_name = st.text_input("class", value=str(current.get("class", current.get("class_name", ""))))
        enabled = st.checkbox("enabled", value=bool(current.get("enabled", True)), key=f"tools_enabled_{category}_{tool_name}")
    with col2:
        st.caption("args (YAML mapping)")
        args_yaml = st.text_area("args", value=yaml.safe_dump(current.get("args", {}) or {}, sort_keys=False), height=140, key="tools_args")
        st.caption("env (YAML mapping)")
        env_yaml = st.text_area("env", value=yaml.safe_dump(current.get("env", {}) or {}, sort_keys=False), height=140, key="tools_env")

    try:
        args_obj = yaml.safe_load(args_yaml or "") or {}
        if not isinstance(args_obj, dict):
            st.error("args must be a YAML mapping (dict)")
            return
    except Exception as e:  # noqa: BLE001
        st.error(f"Invalid args YAML: {e}")
        return
    try:
        env_obj = yaml.safe_load(env_yaml or "") or {}
        if not isinstance(env_obj, dict):
            st.error("env must be a YAML mapping (dict)")
            return
    except Exception as e:  # noqa: BLE001
        st.error(f"Invalid env YAML: {e}")
        return

    spec = {
        "name": tool_name,
        "module": module,
        "class": class_name,
        "enabled": enabled,
        "args": args_obj,
    }
    if env_obj:
        spec["env"] = env_obj

    new_tools_map = dict(tools_map)
    cat_items = list(new_tools_map.get(category, []) or [])
    replaced = False
    for idx, it in enumerate(cat_items):
        if isinstance(it, dict) and str(it.get("name", "")) == tool_name:
            cat_items[idx] = spec
            replaced = True
            break
    if not replaced:
        cat_items.append(spec)
    new_tools_map[category] = cat_items

    out_payload = {"tools": new_tools_map}
    preview = yaml.safe_dump(out_payload, sort_keys=False, allow_unicode=True)

    st.markdown("### Preview")
    st.code(preview, language="yaml")

    if st.button("Save tools.yaml (with backup)", type="primary", key="tools_builder_save"):
        ok, info = safe_write_text(selected_path, preview)
        (st.success if ok else st.error)(info)


# ----- Tabs -----

def ui_configs_tab():
    st.subheader("Manage YAML configs in config/ directory")
    files = list_yaml_files(CONFIG_DIR)
    if not files:
        st.info("No known YAML files found in config/.")
        return

    title_to_path = []

    def add(title: str, filename: str):
        p = CONFIG_DIR / filename
        if p.exists():
            title_to_path.append((title, p))

    add("Crews", "crews.yaml")
    add("Agents", "agents.yaml")
    add("Tasks", "tasks.yaml")
    add("Tools", "tools.yaml")
    add("MCP Tools", "mcp_tools.yaml")

    titles = [t for t, _ in title_to_path]
    tabs = st.tabs(titles)

    for (title, path), tab in zip(title_to_path, tabs):
        with tab:
            st.caption(str(path))
            if title == "Crews":
                editor_mode = st.radio("Editor mode", ["Builder (beta)", "Advanced editor"], horizontal=True, key=f"mode_{title}")
                if editor_mode == "Builder (beta)":
                    crews_yaml_builder_ui(path)
                else:
                    content = st.text_area(
                        "Edit YAML content",
                        value=read_text(path),
                        height=480,
                        key=f"yaml_editor_{path.name}",
                    )
                    valid, msg = yaml_is_valid(content)
                    (st.success if valid else st.error)(msg)
                    if st.button("Save with backup", type="primary", disabled=not valid, key=f"save_{title}"):
                        ok, info = safe_write_text(path, content)
                        (st.success if ok else st.error)(info)
            elif title == "Agents":
                editor_mode = st.radio("Editor mode", ["Builder (beta)", "Advanced editor"], horizontal=True, key=f"mode_{title}")
                if editor_mode == "Builder (beta)":
                    agents_yaml_builder_ui(path)
                else:
                    content = st.text_area(
                        "Edit YAML content",
                        value=read_text(path),
                        height=480,
                        key=f"yaml_editor_{path.name}",
                    )
                    valid, msg = yaml_is_valid(content)
                    (st.success if valid else st.error)(msg)
                    if st.button("Save with backup", type="primary", disabled=not valid, key=f"save_{title}"):
                        ok, info = safe_write_text(path, content)
                        (st.success if ok else st.error)(info)
            elif title == "Tasks":
                editor_mode = st.radio("Editor mode", ["Builder (beta)", "Advanced editor"], horizontal=True, key=f"mode_{title}")
                if editor_mode == "Builder (beta)":
                    tasks_yaml_builder_ui(path)
                else:
                    content = st.text_area(
                        "Edit YAML content",
                        value=read_text(path),
                        height=480,
                        key=f"yaml_editor_{path.name}",
                    )
                    valid, msg = yaml_is_valid(content)
                    (st.success if valid else st.error)(msg)
                    if st.button("Save with backup", type="primary", disabled=not valid, key=f"save_{title}"):
                        ok, info = safe_write_text(path, content)
                        (st.success if ok else st.error)(info)
            elif title == "Tools":
                editor_mode = st.radio("Editor mode", ["Builder (beta)", "Advanced editor"], horizontal=True, key=f"mode_{title}")
                if editor_mode == "Builder (beta)":
                    tools_yaml_builder_ui(path)
                else:
                    content = st.text_area(
                        "Edit YAML content",
                        value=read_text(path),
                        height=480,
                        key=f"yaml_editor_{path.name}",
                    )
                    valid, msg = yaml_is_valid(content)
                    (st.success if valid else st.error)(msg)
                    if st.button("Save with backup", type="primary", disabled=not valid, key=f"save_{title}"):
                        ok, info = safe_write_text(path, content)
                        (st.success if ok else st.error)(info)

                with st.expander("Bulk enable/disable tools", expanded=False):
                    try:
                        existing = yaml.safe_load(read_text(path) or "") or {}
                    except Exception as e:  # noqa: BLE001
                        st.error(f"Failed to parse tools.yaml: {e}")
                        existing = {}
                    tools_map = dict(existing.get("tools", {}) or {})
                    any_tools = False
                    for category, items in tools_map.items():
                        if not isinstance(items, list):
                            continue
                        st.markdown(f"#### {category}")
                        cols = st.columns(2)
                        col_idx = 0
                        for it in items:
                            if not isinstance(it, dict):
                                continue
                            name = str(it.get("name", "")).strip()
                            if not name:
                                continue
                            any_tools = True
                            with cols[col_idx % 2]:
                                key = f"bulk_tool_{category}_{name}"
                                st.checkbox(
                                    f"{name}",
                                    value=bool(it.get("enabled", False)),
                                    key=key,
                                )
                            col_idx += 1
                    if not any_tools:
                        st.info("No tools found to toggle.")
                    else:
                        if st.button("Save bulk changes", key="save_bulk_tools"):
                            new_tools_map = {}
                            for category, items in tools_map.items():
                                new_items = []
                                if isinstance(items, list):
                                    for it in items:
                                        if isinstance(it, dict):
                                            nm = str(it.get("name", "")).strip()
                                            if nm:
                                                key = f"bulk_tool_{category}_{nm}"
                                                new_it = dict(it)
                                                new_it["enabled"] = bool(
                                                    st.session_state.get(key, it.get("enabled", False))
                                                )
                                                new_items.append(new_it)
                                                continue
                                        new_items.append(it)
                                new_tools_map[category] = new_items
                            payload = {"tools": new_tools_map}
                            ok, info = safe_write_text(
                                path, yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
                            )
                            (st.success if ok else st.error)(info)
            elif title == "MCP Tools":
                editor_mode = st.radio("Editor mode", ["Builder (beta)", "Advanced editor"], horizontal=True, key=f"mode_{title}")
                if editor_mode == "Builder (beta)":
                    mcp_tools_yaml_builder_ui(path)
                else:
                    content = st.text_area(
                        "Edit YAML content",
                        value=read_text(path),
                        height=480,
                        key=f"yaml_editor_{path.name}_mcp",
                    )
                    valid, msg = yaml_is_valid(content)
                    (st.success if valid else st.error)(msg)
                    if st.button("Save with backup", type="primary", disabled=not valid, key=f"save_{title}_mcp"):
                        ok, info = safe_write_text(path, content)
                        (st.success if ok else st.error)(info)
            else:
                content = st.text_area(
                    "Edit YAML content",
                    value=read_text(path),
                    height=480,
                    key=f"yaml_editor_{path.name}",
                )
                valid, msg = yaml_is_valid(content)
                (st.success if valid else st.error)(msg)
                if st.button("Save with backup", type="primary", disabled=not valid, key=f"save_{title}"):
                    ok, info = safe_write_text(path, content)
                    (st.success if ok else st.error)(info)

    st.markdown("### Validation")
    if cfg is None:
        st.error("Validation unavailable: could not import crew_composer.config_loader")
    else:
        try:
            crew_names = cfg.list_crew_names(PROJECT_ROOT)
        except Exception as e:  # noqa: BLE001
            st.warning(f"Could not list crews: {e}")
            crew_names = []
        selected_crew = st.selectbox(
            "Crew to validate (optional)", ["<auto>"] + crew_names, key="validate_selected_crew_configs_tab"
        )
        if st.button("Run validation", key="run_validation_configs_tab"):
            try:
                crew_name = None if selected_crew == "<auto>" else selected_crew
                cfg.validate_all(PROJECT_ROOT, crew_name)
                st.success("Configuration validated successfully.")
            except Exception as e:  # noqa: BLE001
                st.exception(e)

    st.markdown("---")
    st.markdown("## Run crew")
    if cfg is None:
        st.info("Running crews requires the local package import to succeed. Please fix imports first.")
        return

    try:
        all_crews = cfg.list_crew_names(PROJECT_ROOT)
    except Exception as e:  # noqa: BLE001
        all_crews = []
        st.warning(f"Could not list crews: {e}")
    col_run1, col_run2 = st.columns([1, 2])
    with col_run1:
        run_selected_crew = st.selectbox("Crew to run", ["<auto>"] + all_crews, key="run_selected_crew")
        st.caption("Select a specific crew or use <auto> (first in crews.yaml)")
    with col_run2:
        inputs_mode = st.radio("Inputs mode (optional)", ["None", "JSON", "key=value pairs"], horizontal=True)
        inputs_json = ""
        inputs_pairs_text = ""
        if inputs_mode == "JSON":
            inputs_json = st.text_area("--inputs-json", placeholder='{"topic": "Hello World"}', height=100, key="inputs_json")
        elif inputs_mode == "key=value pairs":
            inputs_pairs_text = st.text_area("--inputs (one per line)", placeholder="topic=Hello World", height=100, key="inputs_pairs")

    warn = mcp_stdio_required_warning(PROJECT_ROOT)
    need_mcp = bool(warn)
    mcp_available = False
    try:
        import importlib

        importlib.import_module("mcp")
        mcp_available = True
    except Exception:  # noqa: BLE001
        mcp_available = False
    if need_mcp and not mcp_available:
        st.warning(warn + "\nCurrently, 'mcp' does not appear to be installed. Install it with: pip install mcp")

    validate_before_run = st.checkbox("Validate before run", value=True)

    run_clicked = st.button("Run crew now", type="primary", disabled=(need_mcp and not mcp_available))
    log_area = st.empty()

    if run_clicked:
        cmd = [
            sys.executable,
            "-m",
            "crew_composer.cli",
            "run",
        ]
        if run_selected_crew != "<auto>":
            cmd += ["--crew", run_selected_crew]
        inputs_json = (inputs_json or "").strip()
        if inputs_mode == "JSON" and inputs_json:
            try:
                json.loads(inputs_json)
                cmd += ["--inputs-json", inputs_json]
            except json.JSONDecodeError as e:  # noqa: BLE001
                st.error(f"Invalid JSON: {e}")
                return
        elif inputs_mode == "key=value pairs" and inputs_pairs_text.strip():
            pairs = [line.strip() for line in inputs_pairs_text.splitlines() if line.strip()]
            for p in pairs:
                if "=" not in p:
                    st.error(f"Invalid pair '{p}'. Use key=value format.")
                    return
            for p in pairs:
                cmd += ["--inputs", p]

        if validate_before_run:
            try:
                crew_name_for_validation = None if run_selected_crew == "<auto>" else run_selected_crew
                cfg.validate_all(PROJECT_ROOT, crew_name_for_validation)
                st.success("Validation passed. Starting run...")
            except Exception as e:  # noqa: BLE001
                st.error("Validation failed. Aborting run.")
                st.exception(e)
                return

        st.info(f"Starting: {' '.join(cmd)}")
        env = dict(**os.environ)
        env["PYTHONUNBUFFERED"] = "1"
        try:
            with subprocess.Popen(
                cmd,
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                universal_newlines=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            ) as proc:
                from .utils import strip_ansi  # local import
                logs: List[str] = []
                for line in proc.stdout:  # type: ignore[union-attr]
                    clean = strip_ansi(line.rstrip("\n"))
                    logs.append(clean)
                    if len(logs) % 5 == 0:
                        render_scrollable_logs(log_area, "\n".join(logs), height=420)
                rc = proc.wait()
                final_text = "\n".join(logs)
                render_scrollable_logs(log_area, final_text, height=420)
                try:
                    st.session_state["last_run_logs"] = final_text
                    st.session_state["last_run_crew"] = run_selected_crew
                    st.session_state["last_run_time"] = datetime.now().strftime("%Y%m%d-%H%M%S")
                except Exception:  # noqa: BLE001
                    pass
                if rc == 0:
                    st.success("Crew finished successfully.")
                else:
                    st.error(f"Crew process exited with code {rc}.")
        except FileNotFoundError as e:  # noqa: BLE001
            st.error(f"Failed to start process: {e}")
        except Exception as e:  # noqa: BLE001
            st.exception(e)

    last_logs = st.session_state.get("last_run_logs") if hasattr(st, "session_state") else None
    if last_logs:
        st.markdown("### Save last run logs")
        default_ts = st.session_state.get("last_run_time", datetime.now().strftime("%Y%m%d-%H%M%S"))
        crew_tag = st.session_state.get("last_run_crew", "auto")
        suggested = f"{default_ts}_{crew_tag if crew_tag != '<auto>' else 'auto'}.log"
        log_filename = st.text_input("Filename", value=suggested, key="save_logs_filename")
        if st.button("Save logs to file", key="save_logs_button"):
            try:
                RUN_LOGS_DIR.mkdir(parents=True, exist_ok=True)
                out_path = RUN_LOGS_DIR / log_filename
                out_path.write_text(str(last_logs), encoding="utf-8")
                st.success(f"Saved logs to {out_path}")
            except Exception as e:  # noqa: BLE001
                st.error(f"Failed to save logs: {e}")


def ui_knowledge_tab():
    st.subheader("Manage knowledge/ files")
    with st.expander("Upload new file", expanded=False):
        uploaded = st.file_uploader("Choose a file", type=None)
        if uploaded is not None:
            target_name = st.text_input("Target file name", value=uploaded.name)
            if st.button("Save to knowledge/", disabled=not target_name):
                try:
                    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
                    target_path = KNOWLEDGE_DIR / target_name
                    data = uploaded.getvalue()
                    if target_path.exists():
                        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
                        backup = BACKUP_DIR / f"{target_path.name}.{ts}.bak"
                        backup.write_bytes(target_path.read_bytes())
                    target_path.write_bytes(data)
                    st.success(f"Saved {target_name}")
                except Exception as e:  # noqa: BLE001
                    st.error(f"Failed to save: {e}")

    files = list_knowledge_files()
    if not files:
        st.info("No files in knowledge/ yet.")
        return

    names = [f.name for f in files]
    selected_name = st.selectbox("Select a file to view/edit", names)
    path = KNOWLEDGE_DIR / selected_name

    st.caption(str(path))
    ext = path.suffix.lower()

    if ext in {".txt", ".md", ".json", ".yaml", ".yml", ".csv"}:
        content = read_text(path)
        content_new = st.text_area("File content", value=content, height=420)
        if st.button("Save changes", type="primary"):
            ok, info = safe_write_text(path, content_new)
            (st.success if ok else st.error)(info)
        if ext in {".yaml", ".yml"}:
            valid, msg = yaml_is_valid(content_new)
            (st.success if valid else st.error)(msg)
    else:
        st.info("Binary or unsupported file preview. You can download or replace it via upload.")
        st.download_button("Download", data=path.read_bytes(), file_name=path.name)

    with st.expander("Danger zone: Delete file", expanded=False):
        confirm = st.checkbox("I understand this will permanently delete the file.")
        if st.button("Delete", type="secondary", disabled=not confirm):
            try:
                ts = datetime.now().strftime("%Y%m%d-%H%M%S")
                backup = BACKUP_DIR / f"{path.name}.{ts}.deleted.bak"
                backup.write_bytes(path.read_bytes())
                path.unlink(missing_ok=False)
                st.success("File deleted (backup saved).")
                st.rerun()
            except Exception as e:  # noqa: BLE001
                st.error(f"Failed to delete: {e}")


def ui_outputs_tab():
    st.subheader("View output/ files")
    if not OUTPUT_DIR.exists():
        st.info("The output/ directory does not exist yet.")
        return
    files = sorted([p for p in OUTPUT_DIR.rglob("*") if p.is_file()])
    if not files:
        st.info("No files in output/ yet.")
        return

    rel_names = [str(p.relative_to(OUTPUT_DIR)) for p in files]
    selected = st.selectbox("Select a file", rel_names, key="outputs_select_file")
    path = OUTPUT_DIR / selected
    st.caption(str(path))

    ext = path.suffix.lower()
    try:
        if ext == ".md":
            mode = st.radio("View mode", ["Rendered", "Raw"], horizontal=True, key="outputs_md_mode")
            content = read_text(path)
            if mode == "Rendered":
                st.markdown(content)
            else:
                st.text_area("Raw markdown", value=content, height=480, key="outputs_md_raw")
        elif ext in {".txt", ".log", ".yaml", ".yml", ".csv"}:
            content = read_text(path)
            st.text_area("File content", value=content, height=480, key="outputs_text_raw")
            if ext in {".yaml", ".yml"}:
                valid, msg = yaml_is_valid(content)
                (st.success if valid else st.error)(msg)
        elif ext == ".json":
            content = read_text(path)
            try:
                parsed = json.loads(content or "null")
                st.json(parsed)
            except Exception as e:  # noqa: BLE001
                st.error(f"Invalid JSON: {e}")
                st.text_area("Raw JSON", value=content, height=480, key="outputs_json_raw")
        else:
            st.info("Binary or unsupported file preview.")
    except Exception as e:  # noqa: BLE001
        st.error(f"Failed to read file: {e}")

    st.download_button("Download", data=path.read_bytes(), file_name=path.name)
    if st.button("Refresh list"):
        st.rerun()


def ui_docs_tab():
    st.subheader("View docs/ Markdown files")
    if not DOCS_DIR.exists():
        st.info("The docs/ directory does not exist yet.")
        return
    files = sorted([p for p in DOCS_DIR.rglob("*.md") if p.is_file()])
    if not files:
        st.info("No Markdown files in docs/ yet.")
        return

    rel_names = [str(p.relative_to(DOCS_DIR)) for p in files]
    filter_text = st.text_input("Filter files", value="", placeholder="Type to filter by path/name", key="docs_filter")
    if filter_text:
        lowered = filter_text.lower()
        rel_names = [n for n in rel_names if lowered in n.lower()]
        if not rel_names:
            st.info("No files match this filter.")
            return
    default_idx = 0
    for i, name in enumerate(rel_names):
        if name.endswith("main.md") or name == "main.md":
            default_idx = i
            break
    selected = st.selectbox("Select a document", rel_names, index=default_idx, key="docs_select_file")
    path = DOCS_DIR / selected
    st.caption(str(path))

    try:
        content = read_text(path)
        st.markdown(content)
    except Exception as e:  # noqa: BLE001
        st.error(f"Failed to read document: {e}")
        return

    st.download_button("Download", data=path.read_bytes(), file_name=path.name)
    if st.button("Refresh list", key="docs_refresh"):
        st.rerun()


def ui_env_tab():
    st.subheader("Manage .env file")
    if not ENV_FILE.exists():
        st.info(".env does not exist yet. Create it below.")

    mode = st.radio("Editor mode", ["Simple editor", "Key-Value editor"], horizontal=True)

    if mode == "Simple editor":
        content = read_text(ENV_FILE)
        content_new = st.text_area(".env content", value=content, height=420)
        if st.button("Save .env", type="primary"):
            ok, info = safe_write_text(ENV_FILE, content_new)
            (st.success if ok else st.error)(info)
    else:
        values = dotenv_values(str(ENV_FILE)) if ENV_FILE.exists() else {}
        st.caption("Leave value blank to unset on save.")

        new_entries: Dict[str, str] = {}
        for k, v in sorted(values.items()):
            new_entries[k] = st.text_input(k, value=v or "", key=f"env_{k}")

        st.markdown("---")
        st.write("Add new key")
        new_key = st.text_input("Key", key="new_env_key")
        new_val = st.text_input("Value", key="new_env_val")
        if new_key:
            new_entries[new_key] = new_val

        if st.button("Save .env", type="primary"):
            lines = []
            for k, v in new_entries.items():
                if k and v:
                    lines.append(f"{k}={v}")
            content_new = "\n".join(lines) + ("\n" if lines else "")
            ok, info = safe_write_text(ENV_FILE, content_new)
            (st.success if ok else st.error)(info)


def ui_about_tab():
    st.subheader("About this UI")
    st.markdown(
        """
        This Streamlit app helps you manage the project's configuration:
        - YAML files in `config/`
        - Knowledge files in `knowledge/`
        - The `.env` file in the project root

        It creates timestamped backups on every save or delete in the `backups/` directory.
        Use the validation button in the Configs tab to run `crew_composer.config_loader.validate_all`.
        """
    )


# Export agents builder used in Configs tab

def agents_yaml_builder_ui(selected_path: Path) -> None:
    from .utils import get_available_tool_names  # avoid circular import at module import time

    try:
        existing = yaml.safe_load(read_text(selected_path) or "") or {}
    except Exception as e:  # noqa: BLE001
        st.error(f"Failed to parse existing YAML: {e}")
        existing = {}
    if not isinstance(existing, dict):
        existing = {}

    agent_names_existing = list(existing.keys())
    choice = st.selectbox("Select agent to edit", ["<create new>"] + agent_names_existing, key="agents_builder_select")
    if choice == "<create new>":
        agent_name = st.text_input("New agent name", key="agents_builder_new_name")
        if not agent_name:
            st.info("Enter a new agent name to begin.")
            return
        current = {}
    else:
        agent_name = choice
        current = dict(existing.get(agent_name, {}) or {})

    st.markdown("### Agent configuration")
    col1, col2, col3 = st.columns(3)
    with col1:
        role = st.text_input("role", value=str(current.get("role", "")))
        goal = st.text_input("goal", value=str(current.get("goal", "")))
        backstory = st.text_area("backstory", value=str(current.get("backstory", "")), height=120)
        verbose = st.checkbox("verbose", value=bool(current.get("verbose", True)), key=f"agents_verbose_{agent_name}")
        enabled = st.checkbox("enabled", value=bool(current.get("enabled", True)), key=f"agents_enabled_{agent_name}")
    with col2:
        allow_delegation = st.checkbox("allow_delegation", value=bool(current.get("allow_delegation", False)), key=f"agents_allow_delegation_{agent_name}")
        llm = st.text_input("llm", value=str(current.get("llm", "gpt-4o-mini")))
        llm_temperature_str = st.text_input("llm_temperature (optional)", value=str(current.get("llm_temperature", "")))
        max_rpm_str = st.text_input("max_rpm (optional)", value=str(current.get("max_rpm", "")))
        max_iter_str = st.text_input(
            "max_iter (optional)", value=str(current.get("max_iter", current.get("max_iterations", "")))
        )
    with col3:
        cache = st.checkbox("cache (optional)", value=bool(current.get("cache", False)), key=f"agents_cache_{agent_name}")
        human_input = st.checkbox(
            "human_input (optional)", value=bool(current.get("human_input", False)), key=f"agents_human_input_{agent_name}"
        )
        allow_code_execution = st.checkbox(
            "allow_code_execution (optional)", value=bool(current.get("allow_code_execution", False)), key=f"agents_allow_code_{agent_name}"
        )
        multimodal = st.checkbox(
            "multimodal (optional)", value=bool(current.get("multimodal", False)), key=f"agents_multimodal_{agent_name}"
        )

    st.markdown("### Tools")
    available_tools = get_available_tool_names()
    default_tool_names = list(current.get("tool_names", current.get("tools", [])) or [])
    tool_names = st.multiselect("tool_names", options=available_tools or default_tool_names, default=default_tool_names)

    agent_obj: Dict[str, object] = {
        "role": role,
        "goal": goal,
        "backstory": backstory,
        "verbose": verbose,
        "allow_delegation": allow_delegation,
        "enabled": enabled,
        "tool_names": tool_names,
        "llm": llm,
    }

    def _parse_int(s: str):
        s = (s or "").strip()
        if not s:
            return None
        try:
            return int(s)
        except Exception:  # noqa: BLE001
            return None

    def _parse_float(s: str):
        s = (s or "").strip()
        if not s:
            return None
        try:
            return float(s)
        except Exception:  # noqa: BLE001
            return None

    llm_temp_val = _parse_float(llm_temperature_str)
    if llm_temp_val is not None:
        agent_obj["llm_temperature"] = llm_temp_val
    max_rpm_val = _parse_int(max_rpm_str)
    if max_rpm_val is not None:
        agent_obj["max_rpm"] = max_rpm_val
    max_iter_val = _parse_int(max_iter_str)
    if max_iter_val is not None:
        agent_obj["max_iter"] = max_iter_val

    if cache:
        agent_obj["cache"] = True
    if human_input:
        agent_obj["human_input"] = True
    if allow_code_execution:
        agent_obj["allow_code_execution"] = True
    if multimodal:
        agent_obj["multimodal"] = True

    updated_agents = dict(existing)
    updated_agents[agent_name] = agent_obj
    preview = yaml.safe_dump(updated_agents, sort_keys=False, allow_unicode=True)

    st.markdown("### Preview")
    st.code(preview, language="yaml")

    if st.button("Save agents.yaml (with backup)", type="primary", key="agents_builder_save"):
        ok, info = safe_write_text(selected_path, preview)
        (st.success if ok else st.error)(info)
