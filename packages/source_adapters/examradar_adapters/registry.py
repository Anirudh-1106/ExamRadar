"""Loads config/sources.yaml and maps each organisation to its adapter class."""

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from examradar_core.settings import get_settings

from .base import Adapter


@lru_cache
def load_config(path: str | None = None) -> dict[str, Any]:
    p = Path(path or get_settings().sources_file)
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def adapter_classes() -> dict[str, type[Adapter]]:
    from .adapters import ADAPTERS

    return ADAPTERS


def build_adapter(org_cfg: dict[str, Any]) -> Adapter:
    cls = adapter_classes().get(org_cfg.get("adapter", org_cfg["key"]), Adapter)
    return cls(org_cfg)


def organisations(path: str | None = None) -> list[dict[str, Any]]:
    return load_config(path)["organisations"]


def news_feeds(path: str | None = None) -> list[dict[str, Any]]:
    return load_config(path).get("news_feeds", [])
