"""Project-local runtime configuration without exposing secret values in logs."""

from __future__ import annotations

import os
import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_LINE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


def load_project_environment() -> Path:
    """Load the repository ``.env`` regardless of the process working directory.

    Explicit process environment variables retain precedence.  The parser is
    deliberately small: this project needs predictable local configuration, not
    a second configuration framework.
    """
    env_file = PROJECT_ROOT / ".env"
    if not env_file.is_file():
        return env_file
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        matched = _ENV_LINE.match(line)
        if not matched:
            continue
        key, value = matched.groups()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)
    return env_file
