"""Tests for provider routing logic (no API calls)."""
import pytest
from open_muse.llm.providers import resolve_provider, ProviderConfig


def test_resolve_exact_match():
    providers = {
        "compatible-default": ProviderConfig(
            base_url="https://provider.example/v1", api_key="key1", models=["claude-*", "gpt-*"]),
    }
    result = resolve_provider("claude-sonnet-4-6", providers)
    assert result.base_url == "https://provider.example/v1"


def test_resolve_wildcard():
    providers = {
        "compatible-gemini": ProviderConfig(
            base_url="https://provider.example/v1", api_key="key2", models=["gemini-*"]),
    }
    result = resolve_provider("gemini-2.5-pro", providers)
    assert result is not None


def test_resolve_no_match():
    providers = {
        "compatible": ProviderConfig(base_url="https://provider.example/v1", api_key="key1", models=["claude-*"]),
    }
    result = resolve_provider("llama-3", providers)
    assert result is None


def test_resolve_priority_first_match():
    providers = {
        "provider-a": ProviderConfig(base_url="https://a.com/v1", api_key="a", models=["deepseek-*"]),
        "provider-b": ProviderConfig(base_url="https://b.com/v1", api_key="b", models=["deepseek-*"]),
    }
    result = resolve_provider("deepseek-v3", providers)
    assert result.base_url == "https://a.com/v1"
