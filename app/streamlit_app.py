import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

import streamlit as st
import yaml
from dotenv import dotenv_values

# Ensure we can import from the local src/ package path when running with Streamlit
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

# Now imports from local package (defer any UI messaging to inside main())
try:
    from crew_composer import config_loader as cfg
    cfg_import_error = None
except Exception as e:
    cfg = None
    cfg_import_error = str(e)

CONFIG_DIR = PROJECT_ROOT / "config"
KNOWLEDGE_DIR = PROJECT_ROOT / "knowledge"
ENV_FILE = PROJECT_ROOT / ".env"
BACKUP_DIR = PROJECT_ROOT / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


# ---------- Utilities ----------

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
    except Exception as e:
        return False, f"Error saving file: {e}"


def list_knowledge_files() -> List[Path]:
    if not KNOWLEDGE_DIR.exists():
        return []
    return sorted([p for p in KNOWLEDGE_DIR.iterdir() if p.is_file()])


def yaml_is_valid(content: str) -> Tuple[bool, str]:
    try:
        yaml.safe_load(content or "")
        return True, "YAML parsed successfully."
    except Exception as e:
        return False, f"Invalid YAML: {e}"


# ---------- UI Sections ----------

def ui_configs_tab():
    st.subheader("Manage YAML configs in config/ directory")
    files = list_yaml_files(CONFIG_DIR)
    if not files:
        st.info("No known YAML files found in config/.")
        return

    file_paths = {f.name: f for f in files}
    col1, col2 = st.columns([1, 2])
    with col1:
        selected_name = st.selectbox("Select a config file", list(file_paths.keys()))
        selected_path = file_paths[selected_name]
        st.caption(str(selected_path))
        if st.button("Reload from disk"):
            st.rerun()

    with col2:
        content = st.text_area(
            "Edit YAML content",
            value=read_text(selected_path),
            height=480,
            key=f"yaml_editor_{selected_name}",
        )
        valid, msg = yaml_is_valid(content)
        if valid:
            st.success(msg)
        else:
            st.error(msg)

        save_col1, save_col2 = st.columns([1, 1])
        with save_col1:
            if st.button("Save with backup", type="primary", disabled=not valid):
                ok, info = safe_write_text(selected_path, content)
                (st.success if ok else st.error)(info)
        with save_col2:
            st.markdown("### Validation")
            if cfg is None:
                st.error("Validation unavailable: could not import crew_composer.config_loader")
            else:
                crew_names = []
                try:
                    crew_names = cfg.list_crew_names(PROJECT_ROOT)
                except Exception as e:
                    st.warning(f"Could not list crews: {e}")
                selected_crew = st.selectbox(
                    "Crew to validate (optional)", ["<auto>"] + crew_names, key="validate_selected_crew"
                )
                if st.button("Run validation", key="run_validation"):
                    try:
                        crew_name = None if selected_crew == "<auto>" else selected_crew
                        cfg.validate_all(PROJECT_ROOT, crew_name)
                        st.success("Configuration validated successfully.")
                    except Exception as e:
                        st.exception(e)


def ui_knowledge_tab():
    st.subheader("Manage knowledge/ files")

    # Upload
    with st.expander("Upload new file", expanded=False):
        uploaded = st.file_uploader("Choose a file", type=None)
        if uploaded is not None:
            target_name = st.text_input("Target file name", value=uploaded.name)
            if st.button("Save to knowledge/", disabled=not target_name):
                try:
                    (KNOWLEDGE_DIR).mkdir(parents=True, exist_ok=True)
                    target_path = KNOWLEDGE_DIR / target_name
                    data = uploaded.getvalue()
                    # backup if exists
                    if target_path.exists():
                        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
                        backup = BACKUP_DIR / f"{target_path.name}.{ts}.bak"
                        backup.write_bytes(target_path.read_bytes())
                    target_path.write_bytes(data)
                    st.success(f"Saved {target_name}")
                except Exception as e:
                    st.error(f"Failed to save: {e}")

    # List & manage
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
            if valid:
                st.success(msg)
            else:
                st.error(msg)
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
            except Exception as e:
                st.error(f"Failed to delete: {e}")


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

        # Editable key-values
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
            # Reconstruct .env content
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


# ---------- App ----------

def main():
    st.set_page_config(page_title="Crew Composer Manager", layout="wide")
    st.title("Crew Composer Manager")
    st.caption(str(PROJECT_ROOT))

    if cfg_import_error:
        st.warning(
            "Failed to import crew_composer.config_loader. Validation features will be limited.\n" + cfg_import_error
        )

    tabs = st.tabs(["Configs", "Knowledge", ".env", "About"])
    with tabs[0]:
        ui_configs_tab()
    with tabs[1]:
        ui_knowledge_tab()
    with tabs[2]:
        ui_env_tab()
    with tabs[3]:
        ui_about_tab()


if __name__ == "__main__":
    main()
