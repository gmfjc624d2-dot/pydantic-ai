"""Shared fixture builder: locate annotated spans by context, validate, write JSONL with hashes.

Each annotation is given as (span, context, ...): `context` must occur exactly once in the text and
`span` exactly once inside `context`. Offsets are computed here (half-open, Python code points), never
typed by hand.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

HERE = Path(__file__).resolve().parent
TOPICS = ('condition', 'exception', 'negation', 'uncertainty', 'attribution', 'obligation')


def locate(text: str, span: str, context: str) -> Dict[str, Any]:
    assert text.count(context) == 1, f'context {context!r} must occur exactly once in {text!r}'
    assert context.count(span) == 1, f'span {span!r} must occur exactly once in context {context!r}'
    start = text.index(context) + context.index(span)
    end = start + len(span)
    assert text[start:end] == span
    return {'span': span, 'start': start, 'end': end}


def build_item(raw: Dict[str, Any], set_name: str, author: str, phase: str) -> Dict[str, Any]:
    text = raw['text']
    text.encode('utf-8')  # strict: fixtures must be UTF-8 encodable
    gold = []
    for span, context, topics, note in raw['gold']:
        assert topics and all(t in TOPICS for t in topics), topics
        gold.append({**locate(text, span, context), 'topics': list(topics), 'note': note})
    distractors = []
    for span, context, note in raw.get('distractors', []):
        distractors.append({**locate(text, span, context), 'note': note})
    return {
        'id': raw['id'],
        'set': set_name,
        'lang': raw['lang'],
        'text': text,
        'text_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
        'gold': gold,
        'distractors': distractors,
        'format_features': raw.get('format_features', []),
        'author': author,
        'phase': phase,
    }


def write_set(name: str, items: List[Dict[str, Any]]) -> str:
    assert len({i['id'] for i in items}) == len(items)
    body = ''.join(json.dumps(i, ensure_ascii=False, sort_keys=True) + '\n' for i in items)
    path = HERE / f'{name}.jsonl'
    with open(path, 'w', encoding='utf-8', newline='\n') as f:  # Path.write_text(newline=) needs 3.10
        f.write(body)
    digest = hashlib.sha256(body.encode('utf-8')).hexdigest()
    (HERE / f'{name}.sha256').write_text(f'{digest}  {name}.jsonl\n', encoding='utf-8')
    return digest
