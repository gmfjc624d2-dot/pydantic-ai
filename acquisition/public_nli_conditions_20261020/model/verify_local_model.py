"""Verify an existing local model directory against expected public metadata; write a run manifest.

Usage:
    python model/verify_local_model.py --model-dir DIR --expected model/expected/requester_metadata_8adb042d.json \
        --manifest OUT.json --attempt-log ATTEMPTS.jsonl

For a model directory obtained outside this harness (e.g. recovered by the requester). Nothing is
downloaded and no model code is imported or executed. Checks, each refusing on failure:
- every file with an expected hash exists with the expected size and SHA-256 (`model.safetensors`,
  `spm.model`, `tokenizer.json` in the requester metadata);
- `config.json` exists, declares no `auto_map`, and its `architectures`, `id2label` and
  `max_position_embeddings` equal the expected values;
- no file is loaded from pickle formats: their presence is recorded, and `run_model.py` loads with
  `use_safetensors=True` only.
Files without an expected hash (small JSON tokenizer/config files) are hashed and recorded as
"observed locally, no external reference". The output manifest has the same `verified_files` shape that
`run_model.py` re-checks before loading.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PICKLE_SUFFIXES = ('.bin', '.pt', '.pth', '.ckpt', '.pkl', '.pickle')
OPTIONAL = ('tokenizer_config.json', 'special_tokens_map.json', 'added_tokens.json')


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def verify(model_dir: Path, expected: dict[str, Any]) -> dict[str, Any]:
    if not model_dir.is_dir():
        raise SystemExit(f'{model_dir} is not a directory; nothing to verify.')
    records = []
    for name, want in expected['files'].items():
        path = model_dir / name
        if not path.is_file():
            raise SystemExit(f'{name} is missing from {model_dir}; refusing.')
        size = path.stat().st_size
        digest = sha256(path)
        if size != want['size_bytes'] or digest != want['sha256']:
            raise SystemExit(f'{name}: size/SHA-256 {size}/{digest} differs from expected; refusing.')
        records.append(
            {'file': name, 'size_bytes': size, 'sha256': digest, 'verification': 'matches requester-provided metadata'}
        )
    config_path = model_dir / 'config.json'
    if not config_path.is_file():
        raise SystemExit('config.json is missing; refusing.')
    config = json.loads(config_path.read_text(encoding='utf-8'))
    if 'auto_map' in config:
        raise SystemExit('config.json declares auto_map (custom code); refusing.')
    for key in ('architectures', 'id2label', 'max_position_embeddings'):
        if config.get(key) != expected['config'][key]:
            raise SystemExit(f'config.json {key}={config.get(key)!r} differs from expected; refusing.')
    for name in ('config.json', *OPTIONAL):
        path = model_dir / name
        if path.is_file():
            records.append(
                {
                    'file': name,
                    'size_bytes': path.stat().st_size,
                    'sha256': sha256(path),
                    'verification': 'observed locally, no external reference',
                }
            )
    return {
        'repo': expected['repo'],
        'requested_revision': expected['revision'],
        'resolved_revision': expected['revision'],
        'revision_provenance': expected['provenance'],
        'license_from_card': expected['license_from_card'],
        'verified_files': records,
        'pickle_files_present_not_loaded': sorted(p.name for p in model_dir.iterdir() if p.suffix in PICKLE_SUFFIXES),
        'config_checked': {
            k: config.get(k) for k in ('architectures', 'id2label', 'max_position_embeddings', 'torch_dtype')
        },
        'verified_at': datetime.now(UTC).isoformat(),
        'host': {'system': platform.system(), 'machine': platform.machine()},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-dir', type=Path, required=True)
    parser.add_argument('--expected', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--attempt-log', type=Path, required=True)
    args = parser.parse_args()
    expected = json.loads(args.expected.read_text(encoding='utf-8'))
    record: dict[str, Any] = {
        'at': datetime.now(UTC).isoformat(),
        'step': 'verify_local_model',
        'model_dir': str(args.model_dir),
    }
    try:
        manifest = verify(args.model_dir, expected)
    except SystemExit as e:
        record |= {'outcome': 'refused', 'error': str(e)}
        args.attempt_log.parent.mkdir(parents=True, exist_ok=True)
        with args.attempt_log.open('a', encoding='utf-8') as f:
            f.write(json.dumps(record) + '\n')
        raise
    args.manifest.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    record |= {'outcome': 'ok', 'revision': expected['revision']}
    with args.attempt_log.open('a', encoding='utf-8') as f:
        f.write(json.dumps(record) + '\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    sys.exit(main())
