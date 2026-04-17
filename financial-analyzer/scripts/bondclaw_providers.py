#!/usr/bin/env python3
"""
BondClaw provider adapter skeleton.

This module reads the fixed coding-plan registry and exposes a small querying
surface for future UI and automation layers.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from bondclaw_assets import load_provider_registry


@dataclass(frozen=True)
class ProviderAdapterProfile:
    provider_id: str
    display_name: str
    plan_kind: str
    protocol: str
    default_base_url: str
    fallback_base_urls: List[str]
    models: List[str]
    source: str


def _normalize_base_urls(base_urls: Any) -> Dict[str, str]:
    if not isinstance(base_urls, dict):
        return {}
    return {str(key): str(value) for key, value in base_urls.items() if str(value).strip()}


def _normalize_models(models: Any) -> List[str]:
    if not isinstance(models, list):
        return []
    return [str(model) for model in models if str(model).strip()]


def list_provider_ids() -> List[str]:
    return [str(provider.get("id", "")) for provider in load_provider_registry().get("providers", [])]


def list_provider_profiles() -> List[ProviderAdapterProfile]:
    profiles: List[ProviderAdapterProfile] = []
    for provider in load_provider_registry().get("providers", []):
        base_urls = _normalize_base_urls(provider.get("base_urls"))
        ordered_base_urls = list(base_urls.values())
        profiles.append(
            ProviderAdapterProfile(
                provider_id=str(provider.get("id", "")),
                display_name=str(provider.get("display_name", provider.get("id", ""))),
                plan_kind=str(provider.get("plan_kind", "")),
                protocol=str(provider.get("protocol", "")),
                default_base_url=ordered_base_urls[0] if ordered_base_urls else "",
                fallback_base_urls=ordered_base_urls[1:],
                models=_normalize_models(provider.get("models")),
                source=str(provider.get("source", "")),
            )
        )
    return profiles


def get_provider_profile(provider_id: str) -> ProviderAdapterProfile:
    provider_key = str(provider_id).strip()
    for profile in list_provider_profiles():
        if profile.provider_id == provider_key:
            return profile
    raise KeyError(f"Unknown provider: {provider_key}")


def get_default_model(provider_id: str) -> str:
    profile = get_provider_profile(provider_id)
    if profile.models:
        return profile.models[0]
    return ""


def get_default_base_url(provider_id: str) -> str:
    return get_provider_profile(provider_id).default_base_url


def build_provider_matrix() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for profile in list_provider_profiles():
        rows.append(
            {
                "provider_id": profile.provider_id,
                "display_name": profile.display_name,
                "plan_kind": profile.plan_kind,
                "protocol": profile.protocol,
                "default_base_url": profile.default_base_url,
                "fallback_base_urls": profile.fallback_base_urls,
                "model_count": len(profile.models),
                "source": profile.source,
            }
        )
    return rows


def key_only_provider_wizard(provider_id: str) -> Dict[str, Any]:
    profile = get_provider_profile(provider_id)
    return {
        "provider_id": profile.provider_id,
        "display_name": profile.display_name,
        "instruction": "Paste API key only. Base URL and model are prefilled from the BondClaw registry.",
        "default_base_url": profile.default_base_url,
        "default_model": get_default_model(provider_id),
        "fallback_base_urls": profile.fallback_base_urls,
        "model_options": profile.models,
        "source": profile.source,
    }

