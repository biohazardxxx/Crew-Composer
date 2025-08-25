"""Knowledge source loading and management for CrewAI template."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Note: pandas is optional for CSV/Excel support - will use basic file handling
import yaml
from crewai.knowledge.source.base_knowledge_source import BaseKnowledgeSource
from crewai.knowledge.source.csv_knowledge_source import CSVKnowledgeSource
from crewai.knowledge.source.excel_knowledge_source import ExcelKnowledgeSource
from crewai.knowledge.source.json_knowledge_source import JSONKnowledgeSource
from crewai.knowledge.source.pdf_knowledge_source import PDFKnowledgeSource
from crewai.knowledge.source.string_knowledge_source import StringKnowledgeSource
from crewai.knowledge.source.text_file_knowledge_source import TextFileKnowledgeSource
from pydantic import BaseModel, Field
from rich.console import Console

console = Console()


class KnowledgeSourceConfig(BaseModel):
    """Configuration for a knowledge source."""
    
    # Optional; if omitted we fall back to the YAML key
    name: Optional[str] = None
    type: str
    content: Optional[str] = None
    file_path: Optional[str] = None
    file_paths: Optional[List[str]] = None
    urls: Optional[List[str]] = None
    encoding: Optional[str] = "utf-8"
    chunk_size: Optional[int] = 1000
    chunk_overlap: Optional[int] = 200
    source_column: Optional[str] = None
    metadata_columns: Optional[List[str]] = None
    content_key: Optional[str] = None
    metadata_keys: Optional[List[str]] = None
    selector: Optional[str] = None
    max_depth: Optional[int] = 1
    # Excel-specific optional field present in YAML
    sheet_name: Optional[str] = None


class KnowledgeSourcesConfig(BaseModel):
    """Configuration for all knowledge sources."""
    
    knowledge_sources: Dict[str, KnowledgeSourceConfig] = Field(default_factory=dict)


class KnowledgeLoader:
    """Handles loading and managing knowledge sources from YAML configuration."""
    
    def __init__(self, root_path: Path):
        self.root = root_path
        self.knowledge_dir = root_path / "knowledge"
        self.knowledge_dir.mkdir(exist_ok=True)
    
    def load_knowledge_sources(self, config_path: Optional[Path] = None, 
                               selected_sources: Optional[List[str]] = None) -> List[BaseKnowledgeSource]:
        """Load knowledge sources from configuration file with filtering."""
        if config_path is None:
            config_path = self.root / "config" / "agents.knowledge.yaml"
        
        if not config_path.exists():
            console.print(f"[yellow]Knowledge config not found: {config_path}[/yellow]")
            return []
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                raw_config = yaml.safe_load(f) or {}
            
            config = KnowledgeSourcesConfig.model_validate(raw_config)
            return self._create_knowledge_sources(config, selected_sources)
            
        except Exception as e:
            console.print(f"[red]Error loading knowledge config: {e}[/red]")
            return []
    
    def _create_knowledge_sources(self, config: KnowledgeSourcesConfig, 
                                  selected_sources: Optional[List[str]] = None) -> List[BaseKnowledgeSource]:
        """Create knowledge source instances from configuration with filtering."""
        sources = []
        
        # If no specific sources selected, use all available
        if selected_sources is None:
            selected_sources = list(config.knowledge_sources.keys())
        
        for name, source_config in config.knowledge_sources.items():
            # Skip sources not in the selection list
            if name not in selected_sources:
                console.print(f"[dim]Skipping knowledge source: {name} (not in selection)[/dim]")
                continue
                
            try:
                source = self._create_knowledge_source(name, source_config)
                if source:
                    sources.append(source)
                    console.print(f"[green]Loaded knowledge source: {name}[/green]")
            except Exception as e:
                console.print(f"[red]Error creating knowledge source '{name}': {e}[/red]")
        
        return sources
    
    def _create_knowledge_source(
        self, 
        name: str, 
        config: KnowledgeSourceConfig
    ) -> Optional[BaseKnowledgeSource]:
        """Create a specific knowledge source based on type."""
        
        source_name = config.name or name
        
        if config.type == "string":
            return self._create_string_source(source_name, config)
        elif config.type == "text_file":
            return self._create_text_file_source(source_name, config)
        elif config.type == "pdf":
            return self._create_pdf_source(source_name, config)
        elif config.type == "csv":
            return self._create_csv_source(source_name, config)
        elif config.type == "excel":
            return self._create_excel_source(source_name, config)
        elif config.type == "json":
            return self._create_json_source(source_name, config)
        elif config.type == "web_content":
            return self._create_web_content_source(source_name, config)
        else:
            console.print(f"[yellow]Unsupported knowledge source type: {config.type}[/yellow]")
            return None

    def _normalize_to_knowledge_rel(self, path_str: str) -> str:
        """Return a path relative to knowledge/ when inside it, else absolute string."""
        file_path = (self.root / path_str).resolve() if not Path(path_str).is_absolute() else Path(path_str).resolve()
        try:
            rel = file_path.relative_to(self.knowledge_dir)
            return str(rel)
        except ValueError:
            return str(file_path)

    def _prefer_file_paths(self, cls, single_kw_name: str, file_paths: List[str], **kwargs):
        """Try to instantiate source with file_paths, fallback to legacy single path kw on TypeError."""
        try:
            return cls(file_paths=file_paths, **kwargs)
        except TypeError:
            # Fallback to first path via legacy kw
            return cls(**{single_kw_name: file_paths[0]}, **kwargs)
    
    def _create_string_source(self, source_name: str, config: KnowledgeSourceConfig) -> StringKnowledgeSource:
        """Create a string knowledge source."""
        if not config.content:
            raise ValueError("String knowledge source requires 'content'")
        
        return StringKnowledgeSource(
            content=config.content,
            metadata={"name": source_name, "type": "string"}
        )
    
    def _create_text_file_source(self, source_name: str, config: KnowledgeSourceConfig) -> TextFileKnowledgeSource:
        """Create a text file knowledge source."""
        paths = config.file_paths or ([config.file_path] if config.file_path else None)
        if not paths:
            raise ValueError("Text file knowledge source requires 'file_paths' or 'file_path'")
        normalized = [self._normalize_to_knowledge_rel(p) for p in paths]
        # Existence check on first element (best-effort)
        first_abs = (self.root / normalized[0]).resolve() if not Path(normalized[0]).is_absolute() else Path(normalized[0])
        if not first_abs.exists():
            raise FileNotFoundError(f"Text file not found: {first_abs}")
        return self._prefer_file_paths(
            TextFileKnowledgeSource,
            "file_path",
            normalized,
            encoding=config.encoding or "utf-8",
            metadata={"name": source_name, "type": "text_file"},
        )
    
    def _create_pdf_source(self, source_name: str, config: KnowledgeSourceConfig) -> PDFKnowledgeSource:
        """Create a PDF knowledge source."""
        paths = config.file_paths or ([config.file_path] if config.file_path else None)
        if not paths:
            raise ValueError("PDF knowledge source requires 'file_paths' or 'file_path'")
        normalized = [self._normalize_to_knowledge_rel(p) for p in paths]
        first_abs = (self.root / normalized[0]).resolve() if not Path(normalized[0]).is_absolute() else Path(normalized[0])
        if not first_abs.exists():
            raise FileNotFoundError(f"PDF file not found: {first_abs}")
        return self._prefer_file_paths(
            PDFKnowledgeSource,
            "file_path",
            normalized,
            chunk_size=config.chunk_size or 1000,
            chunk_overlap=config.chunk_overlap or 200,
            metadata={"name": source_name, "type": "pdf"},
        )
    
    def _create_csv_source(self, source_name: str, config: KnowledgeSourceConfig) -> CSVKnowledgeSource:
        """Create a CSV knowledge source."""
        paths = config.file_paths or ([config.file_path] if config.file_path else None)
        if not paths:
            raise ValueError("CSV knowledge source requires 'file_paths' or 'file_path'")
        normalized = [self._normalize_to_knowledge_rel(p) for p in paths]
        first_abs = (self.root / normalized[0]).resolve() if not Path(normalized[0]).is_absolute() else Path(normalized[0])
        if not first_abs.exists():
            raise FileNotFoundError(f"CSV file not found: {first_abs}")
        return self._prefer_file_paths(
            CSVKnowledgeSource,
            "file_path",
            normalized,
            source_column=config.source_column,
            metadata_columns=config.metadata_columns or [],
            metadata={"name": source_name, "type": "csv"},
        )
    
    def _create_excel_source(self, source_name: str, config: KnowledgeSourceConfig) -> ExcelKnowledgeSource:
        """Create an Excel knowledge source."""
        paths = config.file_paths or ([config.file_path] if config.file_path else None)
        if not paths:
            raise ValueError("Excel knowledge source requires 'file_paths' or 'file_path'")
        normalized = [self._normalize_to_knowledge_rel(p) for p in paths]
        first_abs = (self.root / normalized[0]).resolve() if not Path(normalized[0]).is_absolute() else Path(normalized[0])
        if not first_abs.exists():
            raise FileNotFoundError(f"Excel file not found: {first_abs}")
        return self._prefer_file_paths(
            ExcelKnowledgeSource,
            "file_path",
            normalized,
            source_column=config.source_column,
            metadata_columns=config.metadata_columns or [],
            sheet_name=config.sheet_name,
            metadata={"name": source_name, "type": "excel"},
        )
    
    def _create_json_source(self, source_name: str, config: KnowledgeSourceConfig) -> JSONKnowledgeSource:
        """Create a JSON knowledge source."""
        paths = config.file_paths or ([config.file_path] if config.file_path else None)
        if not paths:
            raise ValueError("JSON knowledge source requires 'file_paths' or 'file_path'")
        normalized = [self._normalize_to_knowledge_rel(p) for p in paths]
        first_abs = (self.root / normalized[0]).resolve() if not Path(normalized[0]).is_absolute() else Path(normalized[0])
        if not first_abs.exists():
            raise FileNotFoundError(f"JSON file not found: {first_abs}")
        # JSON source historically takes single file; try new then fallback
        try:
            return JSONKnowledgeSource(file_paths=normalized, content_key=config.content_key, metadata_keys=config.metadata_keys or [], metadata={"name": source_name, "type": "json"})
        except TypeError:
            return JSONKnowledgeSource(file_path=normalized[0], content_key=config.content_key, metadata_keys=config.metadata_keys or [], metadata={"name": source_name, "type": "json"})
    
    def _create_web_content_source(self, source_name: str, config: KnowledgeSourceConfig) -> Optional[BaseKnowledgeSource]:
        """Create a web content knowledge source."""
        try:
            from crewai.knowledge.source.crew_docling_source import CrewDoclingSource
            
            if not config.urls:
                raise ValueError("Web content knowledge source requires 'urls'")
            
            return CrewDoclingSource(
                file_paths=config.urls,
                selector=config.selector,
                max_depth=config.max_depth or 1,
                metadata={"name": source_name, "type": "web_content"}
            )
        except ImportError:
            console.print(
                "[yellow]Web content knowledge requires 'docling'. "
                "Install with: pip install docling[/yellow]"
            )
            return None


def load_knowledge_config(root: Path, selected_sources: Optional[List[str]] = None) -> List[BaseKnowledgeSource]:
    """Load knowledge sources from configuration.

    If selected_sources is provided, only those sources (by key) will be loaded.
    """
    loader = KnowledgeLoader(root)
    return loader.load_knowledge_sources(selected_sources=selected_sources)
