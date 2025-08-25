from __future__ import annotations

"""
Glue tool to expose LlamaIndex query engines to CrewAI via constructor-only YAML.

Why: crewai_tools.LlamaIndexTool is typically created via classmethods like
`from_query_engine` or `from_tool`. Our ToolRegistry constructs classes using
regular constructors from YAML, so this adapter builds the underlying
LlamaIndexTool lazily at runtime.

This module avoids importing `llama_index` at import time so that simply having
an entry in tools.yaml won't crash when the optional dependency is missing.
"""

import importlib
from typing import Any, Callable, Dict, Optional

from pydantic import Field, PrivateAttr

try:
    # BaseTool is provided by crewai-tools (present in requirements)
    from crewai_tools import BaseTool  # type: ignore
except Exception as e:  # pragma: no cover - environment issue
    raise RuntimeError(
        "crewai_tools.BaseTool is required for LlamaIndexQueryTool to operate."
    ) from e


class LlamaIndexQueryTool(BaseTool):
    """Constructor-friendly wrapper for LlamaIndexTool.

    Configuration options (pass via YAML `args`):
    - data_dir: Optional[str]
        If provided, builds a simple VectorStoreIndex from all files in this directory.
    - factory_path: Optional[str]
        Dotted import path in the form "package.module:callable" that returns a
        LlamaIndex Query Engine when called. Useful when your app has a custom
        builder function.
    - factory_kwargs: dict
        Keyword arguments passed to the callable referenced by `factory_path`.
    - tool_name: Optional[str]
        Name to expose for the tool (defaults to class name).
    - tool_description: Optional[str]
        Human-friendly description of the tool.
    - return_direct: bool
        Whether to return the response directly to the agent output.
    - lazy_build: bool
        If true (default), build the underlying tool only on first use.
    """

    name: str = "LlamaIndex Query Tool"
    description: str = (
        "Query over documents using a LlamaIndex query engine (RAG wrapper)."
    )

    # Constructor-configurable fields
    data_dir: Optional[str] = None
    factory_path: Optional[str] = None
    factory_kwargs: Dict[str, Any] = Field(default_factory=dict)
    tool_name: Optional[str] = None
    tool_description: Optional[str] = None
    return_direct: bool = False
    lazy_build: bool = True

    # Private delegate to the real LlamaIndexTool instance
    _delegate: Any = PrivateAttr(default=None)

    def model_post_init(self, __context: Any) -> None:  # pydantic v2 hook
        # Allow overriding name/description via args
        if self.tool_name:
            self.name = self.tool_name
        if self.tool_description:
            self.description = self.tool_description
        # Optionally build immediately
        if not self.lazy_build:
            self._ensure_delegate()

    # --- Public API ---
    def _run(self, query: str, **kwargs) -> str:
        """Run a query against the underlying LlamaIndex query engine.

        Parameters
        ----------
        query : str
            The natural language query to execute.
        """
        delegate = self._ensure_delegate()
        # Delegate the call; forward extra kwargs for advanced engines
        return delegate._run(query=query, **kwargs)  # type: ignore[attr-defined]

    # --- Internal helpers ---
    def _ensure_delegate(self):
        if self._delegate is not None:
            return self._delegate

        try:
            # Import here to avoid mandatory dependency at import time
            from crewai_tools import LlamaIndexTool  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "crewai_tools.LlamaIndexTool is required but not available."
            ) from e

        if self.factory_path:
            query_engine = self._build_from_factory()
            self._delegate = LlamaIndexTool.from_query_engine(
                query_engine,
                name=self.name,
                description=self.description,
                return_direct=self.return_direct,
            )
            return self._delegate

        if self.data_dir:
            self._delegate = self._build_from_directory(LlamaIndexTool)
            return self._delegate

        # Nothing to build from: guide the user
        raise RuntimeError(
            "LlamaIndexQueryTool requires either 'factory_path' or 'data_dir' in args."
        )

    def _build_from_factory(self):
        """Load a callable from `factory_path` and invoke it with `factory_kwargs`.

        The callable must return a LlamaIndex Query Engine instance.
        """
        assert self.factory_path, "factory_path not set"
        if ":" not in self.factory_path:
            raise ValueError(
                "factory_path must be in the format 'package.module:callable'"
            )
        module_path, callable_name = self.factory_path.split(":", 1)
        try:
            module = importlib.import_module(module_path)
        except Exception as e:
            raise ImportError(f"Unable to import module '{module_path}': {e}") from e
        try:
            fn = getattr(module, callable_name)
        except AttributeError as e:
            raise ImportError(
                f"Module '{module_path}' does not define '{callable_name}'"
            ) from e
        if not callable(fn):
            raise TypeError(
                f"Resolved object '{self.factory_path}' is not callable; got {type(fn)}"
            )
        return fn(**(self.factory_kwargs or {}))

    def _build_from_directory(self, LlamaIndexToolClass):
        """Build a simple query engine from a directory of documents.

        Requires `llama-index` to be installed. Raises a clear error if missing.
        """
        assert self.data_dir, "data_dir not set"
        try:
            from llama_index.core import VectorStoreIndex
            from llama_index.core.readers import SimpleDirectoryReader
        except Exception as e:  # pragma: no cover
            raise ImportError(
                "llama-index is not installed. Install it to enable LlamaIndexQueryTool.\n"
                "Run: pip install llama-index"
            ) from e

        docs = SimpleDirectoryReader(self.data_dir).load_data()
        index = VectorStoreIndex.from_documents(docs)
        query_engine = index.as_query_engine()
        return LlamaIndexToolClass.from_query_engine(
            query_engine,
            name=self.name,
            description=self.description,
            return_direct=self.return_direct,
        )
