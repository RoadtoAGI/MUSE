# src/open_muse/config.py
"""Configuration loading from YAML."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import yaml
from dotenv import load_dotenv

load_dotenv()

from open_muse.llm.providers import ProviderConfig


@dataclass
class Config:
    """Open-MUSE runtime configuration."""
    skills_dir: Path
    output_dir: Path
    default_model: str = "claude-sonnet-4-6"
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    phase_models: dict[str, str] = field(default_factory=dict)
    retry: dict = field(default_factory=lambda: {"max_retries": 3, "retry_on": [500, 502, 503]})


def load_config(config_path: Path) -> Config:
    """Load configuration from a YAML file."""
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    providers = {}
    for name, prov in raw.get("providers", {}).items():
        providers[name] = ProviderConfig(
            base_url=prov["base_url"],
            api_key=_resolve_api_key(prov.get("api_key_ref", "")),
            models=prov.get("models", []),
        )

    return Config(
        skills_dir=Path(raw.get("skills_dir", "skills")),
        output_dir=Path(raw.get("output_dir", "output")),
        default_model=raw.get("routing", {}).get("default_model", "claude-sonnet-4-6"),
        providers=providers,
        phase_models=raw.get("phase_models", {}),
        retry=raw.get("routing", {}).get("retry", {"max_retries": 3, "retry_on": [500, 502, 503]}),
    )


def _resolve_api_key(ref: str) -> str:
    """Resolve API key from reference.

    Supported formats:
    - "env:VAR_NAME" → os.getenv(VAR_NAME)
    - "api_keys.yaml#key_name" → read from YAML file
    - plain string → return as-is
    """
    import os
    if ref.startswith("env:"):
        return os.getenv(ref[4:], "")
    if "#" not in ref:
        return ref
    file_path, key_name = ref.split("#", 1)
    path = Path(file_path)
    if not path.exists():
        return ""
    keys = yaml.safe_load(path.read_text(encoding="utf-8"))
    return keys.get(key_name, "")
