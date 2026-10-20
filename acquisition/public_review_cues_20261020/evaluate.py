"""Run the highlighter on a fixture set and list every hit, omission and distracting highlight.

Usage:
    python3 evaluate.py dev OUT_DIR
    python3 evaluate.py reserved OUT_DIR --rules-are-frozen   (run once, after the rules freeze commit)

Each item is evaluated with its own language ("es" or "en"). A highlight is a true positive only if its
span equals a gold span exactly and shares at least one topic. Every other highlight is classified:
redundant_nested (inside a gold span that is also hit exactly), partial_shorter / partial_longer /
partial_overlap, topic_mismatch, on_distractor, or unexpected. Every gold span without a true positive
is an omission. Counts only: items are few, hand-written and not independent.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'review_cues'))

from review_cues import TOOL_VERSION, default_ruleset, find_cues  # noqa: E402

TOPICS = ('condition', 'exception', 'negation', 'uncertainty', 'attribution', 'obligation')


def cue_key(s: str) -> str:
    """Comparison key for cue *types* (provenance analysis only, never for matching)."""
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFC', s)).lower()


def spec_examples() -> set:
    """Example words from the topic table of the frozen ANNOTATION.md."""
    out = set()
    for line in (HERE / 'fixtures' / 'ANNOTATION.md').read_text(encoding='utf-8').splitlines():
        m = re.match(r'^\| `(\w+)` \| [^|]+\| ([^|]+)\|$', line)
        if m and m.group(1) in TOPICS:
            out |= {cue_key(w.strip()) for w in m.group(2).split(',')}
    return out


def lexicon_phrases() -> set:
    return {cue_key(p) for r in default_ruleset().data['rules'] for p in r['phrases']}


def load(set_name: str) -> List[Dict[str, Any]]:
    path = HERE / 'fixtures' / f'{set_name}.jsonl'
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    recorded = (HERE / 'fixtures' / f'{set_name}.sha256').read_text(encoding='utf-8').split()[0]
    if digest != recorded:
        raise SystemExit(f'{path.name} differs from its recorded hash; refusing.')
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


def classify(item: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    gold = item['gold']
    hits: List[Dict[str, Any]] = []
    gold_hit = [False] * len(gold)
    preds = result['matches']
    exact_tp = set()
    for pi, p in enumerate(preds):
        for gi, g in enumerate(gold):
            if (p['start'], p['end']) == (g['start'], g['end']) and set(p['review_topics']) & set(g['topics']):
                if not gold_hit[gi]:
                    gold_hit[gi] = True
                    exact_tp.add(pi)
                    break
    for pi, p in enumerate(preds):
        record = {k: p[k] for k in ('text', 'start', 'end', 'byte_start', 'byte_end', 'rule_id', 'review_topics')}
        if pi in exact_tp:
            hits.append({**record, 'class': 'true_positive'})
            continue
        cls = 'unexpected'
        for gi, g in enumerate(gold):
            if (p['start'], p['end']) == (g['start'], g['end']):
                cls = 'duplicate_of_true_positive' if gold_hit[gi] else 'topic_mismatch'
                break
            if g['start'] <= p['start'] and p['end'] <= g['end']:
                cls = 'redundant_nested' if gold_hit[gi] else 'partial_shorter_than_gold'
                break
            if p['start'] <= g['start'] and g['end'] <= p['end']:
                cls = 'partial_longer_than_gold'
                break
            if p['start'] < g['end'] and g['start'] < p['end']:
                cls = 'partial_overlap'
                break
        if cls == 'unexpected':
            for d in item['distractors']:
                if p['start'] < d['end'] and d['start'] < p['end']:
                    cls = 'on_distractor'
                    record['distractor_note'] = d['note']
                    break
        hits.append({**record, 'class': cls})
    omissions = []
    for gi, g in enumerate(gold):
        if gold_hit[gi]:
            continue
        overlapping = [p for p in preds if p['start'] < g['end'] and g['start'] < p['end']]
        omissions.append(
            {
                'span': g['span'],
                'start': g['start'],
                'end': g['end'],
                'topics': g['topics'],
                'reason': 'partially or wrongly highlighted' if overlapping else 'no highlight',
            }
        )
    return {
        'item_id': item['id'],
        'lang': item['lang'],
        'highlights': hits,
        'omissions': omissions,
        'gold_hit': gold_hit,
    }


def main() -> None:
    set_name, out = sys.argv[1], Path(sys.argv[2])
    if set_name == 'reserved' and '--rules-are-frozen' not in sys.argv:
        raise SystemExit('the reserved set is run once, after the rules freeze commit: pass --rules-are-frozen')
    items = load(set_name)
    out.mkdir(parents=True, exist_ok=True)
    spec, lexicon = spec_examples(), lexicon_phrases()
    dev_gold = {cue_key(g['span']) for i in load('dev') for g in i['gold']}
    per_item, raw_lines = [], []
    gold_rows = []
    for item in items:
        result = find_cues(item['text'], item['lang'])
        raw_lines.append(json.dumps({'item_id': item['id'], 'result': result}, ensure_ascii=False, sort_keys=True))
        c = classify(item, result)
        per_item.append(c)
        for g, hit in zip(item['gold'], c['gold_hit']):
            key = cue_key(g['span'])
            origin = (
                'in_dev_gold'
                if key in dev_gold
                else 'in_annotation_spec'
                if key in spec
                else 'closed_class_lexicon_only'
                if key in lexicon
                else 'not_in_lexicon'
            )
            gold_rows.append({'item': item, 'gold': g, 'hit': hit, 'origin': origin})
    highlight_classes = Counter(h['class'] for c in per_item for h in c['highlights'])
    summary: Dict[str, Any] = {
        'set': set_name,
        'tool_version': TOOL_VERSION,
        'ruleset_canonical_sha256': default_ruleset().canonical_sha256,
        'fixtures_sha256': hashlib.sha256((HERE / 'fixtures' / f'{set_name}.jsonl').read_bytes()).hexdigest(),
        'items': len(items),
        'gold_spans': len(gold_rows),
        'gold_hit': sum(r['hit'] for r in gold_rows),
        'highlights': sum(highlight_classes.values()),
        'highlight_classes': dict(sorted(highlight_classes.items())),
        'by_language': {
            lang: {
                'gold': sum(r['item']['lang'] == lang for r in gold_rows),
                'gold_hit': sum(r['hit'] for r in gold_rows if r['item']['lang'] == lang),
                'highlights': sum(len(c['highlights']) for c in per_item if c['lang'] == lang),
                'true_positive_highlights': sum(
                    h['class'] == 'true_positive' for c in per_item if c['lang'] == lang for h in c['highlights']
                ),
            }
            for lang in ('en', 'es')
        },
        'by_topic_gold_recall': {
            t: {
                'gold': sum(t in r['gold']['topics'] for r in gold_rows),
                'hit': sum(r['hit'] for r in gold_rows if t in r['gold']['topics']),
            }
            for t in TOPICS
        },
        'by_cue_origin': {
            o: {
                'gold': sum(r['origin'] == o for r in gold_rows),
                'hit': sum(r['hit'] for r in gold_rows if r['origin'] == o),
            }
            for o in ('in_dev_gold', 'in_annotation_spec', 'closed_class_lexicon_only', 'not_in_lexicon')
        },
        'format_feature_items': {
            i['id']: {'features': i['format_features'], 'all_gold_hit': all(c['gold_hit'])}
            for i, c in zip(items, per_item)
            if i['format_features']
        },
        'empty_gold_items': {i['id']: len(c['highlights']) for i, c in zip(items, per_item) if not i['gold']},
    }
    failures = {
        'omissions': [{'item_id': c['item_id'], **o} for c in per_item for o in c['omissions']],
        'distracting_or_partial_highlights': [
            {'item_id': c['item_id'], **h} for c in per_item for h in c['highlights'] if h['class'] != 'true_positive'
        ],
        'gold_origin': [
            {'item_id': r['item']['id'], 'span': r['gold']['span'], 'origin': r['origin'], 'hit': r['hit']}
            for r in gold_rows
        ],
    }
    (out / 'raw_results.jsonl').write_text('\n'.join(raw_lines) + '\n', encoding='utf-8')
    (out / 'evaluation.json').write_text(
        json.dumps({'summary': summary, 'failures': failures, 'per_item': per_item}, ensure_ascii=False, indent=2)
        + '\n',
        encoding='utf-8',
    )
    md = [
        f'# Evaluation: {set_name} (Linux run; counts only)',
        '',
        '```json',
        json.dumps(summary, ensure_ascii=False, indent=2),
        '```',
        '',
    ]
    md += [
        '## Omissions (gold spans without an exact, topic-compatible highlight)',
        '',
        '| item | span | topics | reason |',
        '|---|---|---|---|',
    ]
    md += [
        f'| {o["item_id"]} | `{o["span"]!r}` | {", ".join(o["topics"])} | {o["reason"]} |'
        for o in failures['omissions']
    ]
    md += [
        '',
        '## Highlights that are not true positives',
        '',
        '| item | highlight | rule | class | note |',
        '|---|---|---|---|---|',
    ]
    md += [
        f'| {h["item_id"]} | `{h["text"]!r}` [{h["start"]},{h["end"]}) | {h["rule_id"]} | {h["class"]} | {h.get("distractor_note", "")} |'
        for h in failures['distracting_or_partial_highlights']
    ]
    (out / 'evaluation.md').write_text('\n'.join(md) + '\n', encoding='utf-8')
    print('\n'.join(md))


if __name__ == '__main__':
    main()
