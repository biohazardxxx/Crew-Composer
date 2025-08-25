from typing import Optional


class ConfigError(Exception):
    """Base exception for configuration-related issues."""


class ConfigNotFoundError(ConfigError):
    def __init__(self, path: str):
        super().__init__(f"Configuration file not found: {path}")


class InvalidConfigError(ConfigError):
    def __init__(self, message: str):
        super().__init__(f"Invalid configuration: {message}")


class ToolImportError(ImportError):
    def __init__(self, module: str, cls: str, extra: Optional[str] = None):
        hint = f". Hint: {extra}" if extra else ""
        super().__init__(
            f"Failed to import tool class '{cls}' from module '{module}'{hint}"
        )


class UnsupportedToolError(ConfigError):
    def __init__(self, name: str):
        super().__init__(f"Unsupported or disabled tool referenced: {name}")
