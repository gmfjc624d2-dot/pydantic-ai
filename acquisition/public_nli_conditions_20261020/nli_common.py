"""Shared, dependency-free helpers: load frozen fixtures (hash-verified) and expand them into trials.

A *trial* is one (premise, hypothesis) input: per item and language, a `full` trial whose premise is
the whole reference, and for items with a manually selected span, a `span` trial whose premise is
that span only. Trials carry their own gold label. Hypotheses are never merged into premises.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / 'fixtures'
LABELS = ('entailment', 'neutral', 'contradiction')
LANGUAGES = ('es', 'en')
SETS = ('dev', 'heldout')


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen_hashes() -> dict[str, str]:
    manifest = json.loads((FIXTURES / 'freeze_manifest.json').read_text(encoding='utf-8'))
    return {name: entry['sha256'] for name, entry in manifest['files'].items()}


def load_items(set_name: str) -> list[dict[str, Any]]:
    """Load one frozen set, refusing if its bytes differ from the freeze manifest."""
    path = FIXTURES / f'{set_name}.jsonl'
    expected = frozen_hashes()[path.name]
    actual = sha256_file(path)
    if actual != expected:
        raise SystemExit(f'{path.name} does not match the freeze manifest ({actual} != {expected}); refusing.')
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


def trials(set_name: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in load_items(set_name):
        for lang in LANGUAGES:
            common = {
                'item_id': item['item_id'],
                'set': item['set'],
                'phenomenon': item['phenomenon'],
                'role': item['role'],
                'language': lang,
                'hypothesis': item[lang]['hypothesis'],
                'full_reference_label': item['label'],
            }
            out.append(
                {
                    **common,
                    'trial_id': f'{item["item_id"]}/{lang}/full',
                    'trial_type': 'full',
                    'premise': item[lang]['reference'],
                    'gold': item['label'],
                    'convention_sensitive': False,
                }
            )
            span = item['single_span']
            if span:
                out.append(
                    {
                        **common,
                        'trial_id': f'{item["item_id"]}/{lang}/span',
                        'trial_type': 'span',
                        'premise': span[lang]['text'],
                        'gold': span['label'],
                        'convention_sensitive': span['convention_sensitive'],
                    }
                )
    return out


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> str:
    text = ''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise SystemExit(f'{path} already exists; prediction files are immutable. Use a new run directory.')
    path.write_text(text, encoding='utf-8')
    return hashlib.sha256(text.encode('utf-8')).hexdigest()
