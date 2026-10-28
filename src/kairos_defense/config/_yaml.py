"""YAML loading with YAML 1.2 booleans (``rid: off`` stays a string)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


class _Yaml12Loader(yaml.SafeLoader):
    """SafeLoader with YAML 1.2 booleans: only true/false, so ``rid: off`` stays a string."""


_Yaml12Loader.yaml_implicit_resolvers = {
    ch: [(tag, rx) for tag, rx in resolvers if tag != "tag:yaml.org,2002:bool"]
    for ch, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_Yaml12Loader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"),
)


def _string_keys(node: Any) -> Any:
    """Turn boolean mapping keys (``true: true`` in a clue) into ``"true"``/``"false"``."""
    if isinstance(node, dict):
        return {
            (str(k).lower() if isinstance(k, bool) else k): _string_keys(v) for k, v in node.items()
        }
    if isinstance(node, list):
        return [_string_keys(v) for v in node]
    return node


def load_yaml(path: Path) -> Any:
    """Parse one YAML file with YAML 1.2 boolean rules."""
    with path.open(encoding="utf-8") as fh:
        return _string_keys(yaml.load(fh, Loader=_Yaml12Loader))
