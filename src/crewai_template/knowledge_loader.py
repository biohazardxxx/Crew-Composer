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
    
    name: str
    type: str
    content: Optional[str] = None
    file_path: Optional[str] = None
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
        
        if config.type == "string":
            return self._create_string_source(config)
        elif config.type == "text_file":
            return self._create_text_file_source(config)
        elif config.type == "pdf":
            return self._create_pdf_source(config)
        elif config.type == "csv":
            return self._create_csv_source(config)
        elif config.type == "excel":
            return self._create_excel_source(config)
        elif config.type == "json":
            return self._create_json_source(config)
        elif config.type == "web_content":
            return self._create_web_content_source(config)
        else:
            console.print(f"[yellow]Unsupported knowledge source type: {config.type}[/yellow]")
            return None
    
    def _create_string_source(self, config: KnowledgeSourceConfig) -> StringKnowledgeSource:
        """Create a string knowledge source."""
        if not config.content:
            raise ValueError("String knowledge source requires 'content'")
        
        return StringKnowledgeSource(
            content=config.content,
            metadata={"name": config.name, "type": "string"}
        )
    
    def _create_text_file_source(self, config: KnowledgeSourceConfig) -> TextFileKnowledgeSource:
        """Create a text file knowledge source."""
        if not config.file_path:
            raise ValueError("Text file knowledge source requires 'file_path'")
        
        file_path = self.root / config.file_path
        if not file_path.exists():
            raise FileNotFoundError(f"Text file not found: {file_path}")
        
        return TextFileKnowledgeSource(
            file_path=str(file_path),
            encoding=config.encoding or "utf-8",
            metadata={"name": config.name, "type": "text_file"}
        )
    
    def _create_pdf_source(self, config: KnowledgeSourceConfig) -> PDFKnowledgeSource:
        """Create a PDF knowledge source."""
        if not config.file_path:
            raise ValueError("PDF knowledge source requires 'file_path'")
        
        file_path = self.root / config.file_path
        if not file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")
        
        return PDFKnowledgeSource(
            file_path=str(file_path),
            chunk_size=config.chunk_size or 1000,
            chunk_overlap=config.chunk_overlap or 200,
            metadata={"name": config.name, "type": "pdf"}
        )
    
    def _create_csv_source(self, config: KnowledgeSourceConfig) -> CSVKnowledgeSource:
        """Create a CSV knowledge source."""
        if not config.file_path:
            raise ValueError("CSV knowledge source requires 'file_path'")
        
        file_path = self.root / config.file_path
        if not file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")
        
        return CSVKnowledgeSource(
            file_path=str(file_path),
            source_column=config.source_column,
            metadata_columns=config.metadata_columns or [],
            metadata={"name": config.name, "type": "csv"}
        )
    
    def _create_excel_source(self, config: KnowledgeSourceConfig) -> ExcelKnowledgeSource:
        """Create an Excel knowledge source."""
        if not config.file_path:
            raise ValueError("Excel knowledge source requires 'file_path'")
        
        file_path = self.root / config.file_path
        if not file_path.exists():
            raise FileNotFoundError(f"Excel file not found: {file_path}")
        
        return ExcelKnowledgeSource(
            file_path=str(file_path),
            source_column=config.source_column,
            metadata_columns=config.metadata_columns or [],
            sheet_name=config.sheet_name,
            metadata={"name": config.name, "type": "excel"}
        )
    
    def _create_json_source(self, config: KnowledgeSourceConfig) -> JSONKnowledgeSource:
        """Create a JSON knowledge source."""
        if not config.file_path:
            raise ValueError("JSON knowledge source requires 'file_path'")
        
        file_path = self.root / config.file_path
        if not file_path.exists():
            raise FileNotFoundError(f"JSON file not found: {file_path}")
        
        return JSONKnowledgeSource(
            file_path=str(file_path),
            content_key=config.content_key,
            metadata_keys=config.metadata_keys or [],
            metadata={"name": config.name, "type": "json"}
        )
    
    def _create_web_content_source(self, config: KnowledgeSourceConfig) -> Optional[BaseKnowledgeSource]:
        """Create a web content knowledge source."""
        try:
            from crewai.knowledge.source.crew_docling_source import CrewDoclingSource
            
            if not config.urls:
                raise ValueError("Web content knowledge source requires 'urls'")
            
            return CrewDoclingSource(
                file_paths=config.urls,
                selector=config.selector,
                max_depth=config.max_depth or 1,
                metadata={"name": config.name, "type": "web_content"}
            )
        except ImportError:
            console.print(
                "[yellow]Web content knowledge requires 'docling'. "
                "Install with: pip install docling[/yellow]"
            )
            return None


def load_knowledge_config(root: Path) -> List[BaseKnowledgeSource]:
    """Load knowledge sources from configuration."""
    loader = KnowledgeLoader(root)
    return loader.load_knowledge_sources()
