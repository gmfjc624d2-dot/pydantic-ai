"""Environment provenance for evidence records (what ran, where, with which packages)."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any

PACKAGES = (
    'pydantic-evals',
    'pydantic-ai-slim',
    'pydantic-graph',
    'pydantic',
    'logfire',
    'logfire-api',
    'opentelemetry-api',
    'opentelemetry-sdk',
    'hypothesis',
    'pytest',
)


def package_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name in PACKAGES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def git_commit(repo: Path) -> str | None:
    try:
        out = subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD'], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def environment(repo: Path | None = None) -> dict[str, Any]:
    return {
        'os': platform.system(),
        'os_release': platform.release(),
        'machine': platform.machine(),
        'python': platform.python_version(),
        'python_implementation': platform.python_implementation(),
        'executable_is_venv': sys.prefix != sys.base_prefix,
        'packages': package_versions(),
        'source_commit': git_commit(repo) if repo else None,
        'qualification': 'linux-cloud-only; NOT a macOS result' if platform.system() != 'Darwin' else 'darwin',
        'cpu_count': os.cpu_count(),
    }


def content_hash(value: Any) -> str:
    return 'sha256:' + hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()
