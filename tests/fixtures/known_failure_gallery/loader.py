from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

GALLERY_DIR = Path(__file__).parent

GALLERY_FILES = [
    "environment_errors.yaml",
    "syntax_errors.yaml",
    "runtime_errors.yaml",
    "resource_errors.yaml",
    "external_errors.yaml",
    "semantic_failures.yaml",
    "contract_failures.yaml",
]


def load_gallery_file(filename: str) -> dict[str, Any]:
    path = GALLERY_DIR / filename
    with path.open() as f:
        return yaml.safe_load(f)


def load_full_gallery() -> dict[str, dict[str, Any]]:
    gallery: dict[str, dict[str, Any]] = {}
    for filename in GALLERY_FILES:
        data = load_gallery_file(filename)
        gallery[data["category"]] = data
    return gallery


def list_all_prompts() -> list[tuple[str, str, str]]:
    entries: list[tuple[str, str, str]] = []
    for category, data in load_full_gallery().items():
        for example in data["examples"]:
            entries.append((category, example["name"], example["prompt"].strip()))
    return entries
