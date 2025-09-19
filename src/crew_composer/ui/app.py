from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Support running as a package (relative imports) and as a script via `streamlit run`
try:
    from .utils import PROJECT_ROOT
    from .tabs import (
        ui_about_tab,
        ui_configs_tab,
        ui_docs_tab,
        ui_env_tab,
        ui_knowledge_tab,
        ui_outputs_tab,
    )
except Exception:  # noqa: BLE001
    # Fall back to absolute imports by adding the project's src/ to sys.path
    project_root = Path(__file__).resolve().parents[2]
    src_path = project_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    from crew_composer.ui.utils import PROJECT_ROOT  # type: ignore
    from crew_composer.ui.tabs import (  # type: ignore
        ui_about_tab,
        ui_configs_tab,
        ui_docs_tab,
        ui_env_tab,
        ui_knowledge_tab,
        ui_outputs_tab,
    )


def main() -> None:
    st.set_page_config(page_title="Crew Composer Manager", layout="wide")
    st.title("Crew Composer Manager")
    st.caption(str(PROJECT_ROOT))

    tabs = st.tabs(["Configs", "Knowledge", "Outputs", ".env", "Docs", "About"])
    with tabs[0]:
        ui_configs_tab()
    with tabs[1]:
        ui_knowledge_tab()
    with tabs[2]:
        ui_outputs_tab()
    with tabs[3]:
        ui_env_tab()
    with tabs[4]:
        ui_docs_tab()
    with tabs[5]:
        ui_about_tab()


if __name__ == "__main__":
    main()
