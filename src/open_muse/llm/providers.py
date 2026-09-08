"""Provider routing: model name -> base_url + api_key."""
from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import Optional


@dataclass
class ProviderConfig:
    """Configuration for a single LLM provider/group."""
    base_url: str
    api_key: str
    models: list[str] = field(default_factory=list)


def resolve_provider(model: str, providers: dict[str, ProviderConfig]) -> Optional[ProviderConfig]:
    """Find the first provider whose models pattern matches the given model name."""
    for provider in providers.values():
        for pattern in provider.models:
            if fnmatch(model, pattern):
                return provider
    return None
