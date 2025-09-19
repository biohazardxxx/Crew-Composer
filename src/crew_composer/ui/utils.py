from __future__ import annotations

import html
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import streamlit as st
import yaml

from .. import config_loader as cfg
from ..config_loader import get_project_root

# Paths resolved from project root for package context
PROJECT_ROOT: Path = get_project_root()
CONFIG_DIR: Path = PROJECT_ROOT / "config"
KNOWLEDGE_DIR: Path = PROJECT_ROOT / "knowledge"
ENV_FILE: Path = PROJECT_ROOT / ".env"
BACKUP_DIR: Path = PROJECT_ROOT / "backups"
RUN_LOGS_DIR: Path = PROJECT_ROOT / "output" / "run-logs"
OUTPUT_DIR: Path = PROJECT_ROOT / "output"
DOCS_DIR: Path = PROJECT_ROOT / "docs"

# Ensure directories exist where appropriate
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
RUN_LOGS_DIR.mkdir(parents=True, exist_ok=True)


def list_yaml_files(config_dir: Path) -> List[Path]:
    known = [
        config_dir / "agents.yaml",
        config_dir / "agents.knowledge.yaml",
        config_dir / "crews.yaml",
        config_dir / "tasks.yaml",
        config_dir / "tools.yaml",
        config_dir / "mcp_tools.yaml",
    ]
    return [p for p in known if p.exists()]


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def safe_write_text(path: Path, content: str) -> Tuple[bool, str]:
    try:
        if path.exists():
            ts = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = BACKUP_DIR / f"{path.name}.{ts}.bak"
            backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return True, "Saved successfully. Backup created if file existed."
    except Exception as e:  # noqa: BLE001
        return False, f"Error saving file: {e}"


def list_knowledge_files() -> List[Path]:
    if not KNOWLEDGE_DIR.exists():
        return []
    return sorted([p for p in KNOWLEDGE_DIR.iterdir() if p.is_file()])


def yaml_is_valid(content: str) -> Tuple[bool, str]:
    try:
        yaml.safe_load(content or "")
        return True, "YAML parsed successfully."
    except Exception as e:  # noqa: BLE001
        return False, f"Invalid YAML: {e}"


ANSI_PATTERN = re.compile(r"\x1B\[[0-9;]*[mK]")


def strip_ansi(s: str) -> str:
    try:
        return ANSI_PATTERN.sub("", s)
    except Exception:  # noqa: BLE001
        return s


def mcp_stdio_required_warning(root: Path) -> str:
    """Return a warning string if any configured MCP server uses stdio transport."""
    try:
        crew_cfg = cfg.load_crew_config(root)
        servers = cfg.load_mcp_servers_config(root, crew_cfg.tools_files)
        for spec in servers:
            transport = (getattr(spec, "transport", "") or "").lower()
            if transport == "stdio" or (not transport and getattr(spec, "command", None)):
                return (
                    "Detected MCP server(s) using stdio. Ensure the 'mcp' package is installed in your venv "
                    "before running crews or disable those servers in config/mcp_tools.yaml."
                )
        return ""
    except Exception:  # noqa: BLE001
        return ""


def render_scrollable_logs(placeholder: st.delta_generator.DeltaGenerator, text: str, height: int = 420) -> None:
    """Render text with a fixed height and scrollbars using HTML in a placeholder."""
    try:
        safe = html.escape(text or "")
        # We preserve the user's intent: if they were at the bottom before the update,
        # we auto-scroll to bottom after rendering. Otherwise, we keep their scroll position.
        # We approximate this across rerenders using sessionStorage.
        html_block = f"""
        <div id="run-log-box" style="max-height:{height}px; overflow:auto; padding:8px; background:#0e1117; color:#eaeaea; border:1px solid #30363d; border-radius:6px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, Liberation Mono, monospace; font-size: 12px; white-space: pre;">
        {safe}
        </div>
        <script>
        (function() {{
            try {{
                const key = 'runLogAtBottom';
                const box = document.getElementById('run-log-box');
                if (!box) return;
                // If previously at bottom, scroll to bottom on this render
                const wasAtBottom = window.sessionStorage.getItem(key) === '1';
                if (wasAtBottom) {{
                    box.scrollTop = box.scrollHeight;
                }}
                // Attach listener to record whether the user is at bottom
                const updateFlag = () => {{
                    const threshold = 8; // px tolerance
                    const atBottom = (box.scrollHeight - box.clientHeight - box.scrollTop) <= threshold;
                    window.sessionStorage.setItem(key, atBottom ? '1' : '0');
                }};
                box.removeEventListener('scroll', updateFlag);
                box.addEventListener('scroll', updateFlag, {{ passive: true }});
                // Initialize flag based on current position
                updateFlag();
            }} catch (e) {{
                // ignore
            }}
        }})();
        </script>
        """
        placeholder.markdown(html_block, unsafe_allow_html=True)
    except Exception:  # noqa: BLE001
        placeholder.code(text or "", language="bash")


def get_available_tool_names() -> List[str]:
    names: List[str] = []
    try:
        try:
            crew_cfg = cfg.load_crew_config(PROJECT_ROOT)
            tc = cfg.load_tools_config(PROJECT_ROOT, crew_cfg.tools_files)
        except Exception:  # noqa: BLE001
            tc = cfg.load_tools_config(PROJECT_ROOT)
        for specs in (tc.tools or {}).values():
            for spec in specs:
                try:
                    names.append(str(spec.name))
                except Exception:  # noqa: BLE001
                    continue
        names = sorted(list({n for n in names if n}))
    except Exception:  # noqa: BLE001
        names = []
    return names
