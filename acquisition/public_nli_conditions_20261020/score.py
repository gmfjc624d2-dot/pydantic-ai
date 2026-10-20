"""Re-score retained predictions against the frozen fixtures. Never runs a model (stdlib only).

Usage: python score.py OUT_DIR RUN_DIR [RUN_DIR ...]

Each RUN_DIR holds `run_manifest.json` and `predictions--{dev,heldout}.jsonl` (schema nli-prediction/v1).
Refuses a run whose prediction files differ from the SHA-256 in its manifest, whose recorded fixture
hashes differ from the freeze manifest, or whose recorded inputs differ from the frozen text.

Errata (`fixtures/errata.json`) only add flags. The original full-set score is always reported first;
subsets (excluding the disputed item, each convention group, the assumption-light core) are extra rows.

No independence-based confidence interval is computed: each set's 24 items come from 6 scenario groups
of 4 related variants, and Spanish/English are paired variants of the same item. Results are counts,
broken down by scenario group, with every error listed.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from nli_common import FIXTURES, LABELS, LANGUAGES, SETS, frozen_hashes, load_items, sha256_file, trials

ERRATA = FIXTURES / 'errata.json'
CORE_EXCLUDED_FLAGS = ('disputed', 'convention_standing_rule', 'convention_coherent_source')
ROLES = ('base', 'paraphrase', 'meaning_change', 'missing_qualifier')


def load_errata() -> tuple[dict[str, set[str]], dict[str, Any]]:
    errata = json.loads(ERRATA.read_text(encoding='utf-8'))
    known = {item['item_id'] for s in SETS for item in load_items(s)}
    flags: dict[str, set[str]] = defaultdict(set)
    for entry in errata['entries']:
        if 'label' in entry or 'new_label' in entry:
            raise SystemExit('errata may add flags only, never labels; refusing.')
        for item_id in entry['item_ids']:
            if item_id not in known:
                raise SystemExit(f'errata refer to unknown item {item_id!r}; refusing.')
            flags[item_id].add(entry['flag'])
    return flags, errata


def count(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {'correct': sum(bool(r['correct']) for r in rows), 'n': len(rows)}


def per_class(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for label in LABELS:
        tp = sum(r['gold'] == r['pred'] == label for r in rows)
        fp = sum(r['pred'] == label != r['gold'] for r in rows)
        fn = sum(r['gold'] == label != r['pred'] for r in rows)
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn) if tp + fn else None
        f1 = 2 * precision * recall / (precision + recall) if precision and recall else 0.0
        out[label] = {
            'support': tp + fn,
            'predicted': tp + fp,
            'correct': tp,
            'precision': None if precision is None else round(precision, 4),
            'recall': None if recall is None else round(recall, 4),
            'f1': round(f1, 4),
        }
    out['macro_f1_descriptive'] = round(sum(out[label]['f1'] for label in LABELS) / len(LABELS), 4)
    return out


def confusion(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    return {g: {p: sum(r['gold'] == g and r['pred'] == p for r in rows) for p in LABELS} for g in LABELS}


def load_run(run_dir: Path) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    manifest = json.loads((run_dir / 'run_manifest.json').read_text(encoding='utf-8'))
    if manifest['fixtures_sha256'] != frozen_hashes():
        raise SystemExit(f'{run_dir}: predictions were made against different fixtures; refusing.')
    predictions: dict[str, list[dict[str, Any]]] = {}
    for set_name in SETS:
        path = run_dir / f'predictions--{set_name}.jsonl'
        if not path.exists():
            continue
        if sha256_file(path) != manifest['files'][path.name]['sha256']:
            raise SystemExit(f'{path} does not match its run manifest; refusing.')
        predictions[set_name] = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]
    return manifest, predictions


def subset_summary(full: list[dict[str, Any]], keep: set[str]) -> dict[str, Any]:
    rows = [r for r in full if r['item_id'] in keep]
    items = sorted({r['item_id'] for r in rows})
    return {
        'items': len(items),
        'by_language': {lang: count([r for r in rows if r['language'] == lang]) for lang in LANGUAGES},
        'items_correct_in_both_languages': count(
            [{'correct': all(r['correct'] for r in rows if r['item_id'] == i)} for i in items]
        ),
        'item_ids': items,
    }


def score_set(set_name: str, preds: list[dict[str, Any]], flags: dict[str, set[str]]) -> dict[str, Any]:
    by_id = {p['trial_id']: p for p in preds}
    expected = trials(set_name)
    rows = []
    for t in expected:
        p = by_id.get(t['trial_id'])
        if p is None:
            continue
        if p['premise'] != t['premise'] or p['hypothesis'] != t['hypothesis']:
            raise SystemExit(f'{t["trial_id"]}: recorded input differs from the frozen fixture; refusing.')
        status = p.get('status', 'ok')
        pred = p['predicted_label'] if status == 'ok' else f'<{status}>'
        rows.append(
            {
                **t,
                'group_id': t['item_id'].rsplit('-', 1)[0],
                'pred': pred,
                'correct': pred == t['gold'],
                'status': status,
                'flags': sorted(flags.get(t['item_id'], set())),
                'record': p,
            }
        )
    full = [r for r in rows if r['trial_type'] == 'full']
    span = [r for r in rows if r['trial_type'] == 'span']
    items = sorted({r['item_id'] for r in full})
    report: dict[str, Any] = {
        'trials_expected': len(expected),
        'trials_scored': len(rows),
        'trials_missing': [t['trial_id'] for t in expected if t['trial_id'] not in by_id],
        'non_ok_status': dict(Counter(r['status'] for r in rows if r['status'] != 'ok')),
    }
    all_flags = sorted({f for i in items for f in flags.get(i, set())})
    subsets = {'original_full_set': subset_summary(full, set(items))}
    subsets['excluding_disputed'] = subset_summary(full, {i for i in items if 'disputed' not in flags.get(i, set())})
    for flag in all_flags:
        subsets[f'only:{flag}'] = subset_summary(full, {i for i in items if flag in flags.get(i, set())})
    subsets['assumption_light_core'] = subset_summary(
        full, {i for i in items if not flags.get(i, set()) & set(CORE_EXCLUDED_FLAGS)}
    )
    groups: dict[str, Any] = {}
    for g in sorted({r['group_id'] for r in full}):
        g_rows = [r for r in full if r['group_id'] == g]
        groups[g] = {
            'by_language': {lang: count([r for r in g_rows if r['language'] == lang]) for lang in LANGUAGES},
            'items': [
                {
                    'item_id': i,
                    'role': next(r['role'] for r in g_rows if r['item_id'] == i),
                    'gold': next(r['gold'] for r in g_rows if r['item_id'] == i),
                    **{
                        f'pred_{lang}': next(r['pred'] for r in g_rows if r['item_id'] == i and r['language'] == lang)
                        for lang in LANGUAGES
                    },
                    'flags': sorted(flags.get(i, set())),
                }
                for i in sorted({r['item_id'] for r in g_rows})
            ],
        }
    lookup = {(r['group_id'], r['role'], r['language']): r for r in full}
    pairs = [(g, lang) for g in groups for lang in LANGUAGES]
    by_item: dict[str, dict[str, str]] = defaultdict(dict)
    for r in full:
        by_item[r['item_id']][r['language']] = r['pred']
    report['full'] = {
        'subsets': subsets,
        'by_group': groups,
        'confusion_gold_by_pred': confusion(full),
        'per_class': per_class(full),
        'by_role': {role: count([r for r in full if r['role'] == role]) for role in ROLES},
        'paraphrase_consistency': count(
            [
                {'correct': lookup[(g, 'base', lang)]['pred'] == lookup[(g, 'paraphrase', lang)]['pred']}
                for g, lang in pairs
            ]
        ),
        'minimal_pair_sensitivity': count(
            [
                {'correct': lookup[(g, 'base', lang)]['pred'] != lookup[(g, 'meaning_change', lang)]['pred']}
                for g, lang in pairs
            ]
        ),
        'cross_lingual_agreement': count([{'correct': v['es'] == v['en']} for v in by_item.values()]),
    }
    if span:
        report['span'] = {
            'by_language': {lang: count([r for r in span if r['language'] == lang]) for lang in LANGUAGES},
            'excluding_convention_sensitive': count([r for r in span if not r['convention_sensitive']]),
            'convention_sensitive_only': count([r for r in span if r['convention_sensitive']]),
            'span_prediction_equals_full_reference_label': count(
                [{'correct': r['pred'] == r['full_reference_label']} for r in span]
            ),
            'trials': [
                {
                    'trial_id': r['trial_id'],
                    'span_gold': r['gold'],
                    'full_reference_label': r['full_reference_label'],
                    'pred': r['pred'],
                    'convention_sensitive': r['convention_sensitive'],
                }
                for r in span
            ],
        }
    probs = [r for r in rows if r['status'] == 'ok' and 'probabilities' in r['record']]
    if probs:
        nll, brier, max_correct, max_wrong = [], [], [], []
        for r in probs:
            pr = dict(zip(r['record']['label_order'], r['record']['probabilities']))
            nll.append(-math.log(max(pr[r['gold']], 1e-12)))
            brier.append(sum((pr[label] - (label == r['gold'])) ** 2 for label in LABELS))
            (max_correct if r['correct'] else max_wrong).append(max(pr.values()))
        report['probabilities_descriptive_only'] = {
            'n_trials': len(probs),
            'mean_nll': round(sum(nll) / len(nll), 4),
            'mean_brier': round(sum(brier) / len(brier), 4),
            'mean_max_prob_when_correct': round(sum(max_correct) / len(max_correct), 4) if max_correct else None,
            'mean_max_prob_when_wrong': round(sum(max_wrong) / len(max_wrong), 4) if max_wrong else None,
            'note': 'Synthetic, tiny, paired, non-random sample: no calibration claim is supported.',
        }
    report['errors'] = [
        {
            'trial_id': r['trial_id'],
            'group_id': r['group_id'],
            'role': r['role'],
            'gold': r['gold'],
            'pred': r['pred'],
            'flags': r['flags'],
            'convention_sensitive_span': r['convention_sensitive'],
            'premise': r['premise'],
            'hypothesis': r['hypothesis'],
            'evidence': {
                k: r['record'][k] for k in ('features', 'probabilities', 'logits', 'error') if k in r['record']
            },
        }
        for r in rows
        if not r['correct']
    ]
    return report


def c(x: dict[str, int]) -> str:
    return f'{x["correct"]}/{x["n"]}'


def markdown(system: str, set_name: str, r: dict[str, Any]) -> str:
    f = r['full']
    lines = [f'## {system} — {set_name}', '']
    lines.append(f'Trials scored {r["trials_scored"]}/{r["trials_expected"]}; non-ok: {r["non_ok_status"] or "none"}.')
    lines.append('Counts only; trials are paired and grouped, so no independence-based interval is given.')
    lines += ['', '| Full-context subset | items | es | en | items correct in both |', '|---|---|---|---|---|']
    for name, s in f['subsets'].items():
        lines.append(
            f'| {name} | {s["items"]} | {c(s["by_language"]["es"])} | {c(s["by_language"]["en"])} | {c(s["items_correct_in_both_languages"])} |'
        )
    lines += ['', '| Scenario group | es | en | items: gold → pred es / en |', '|---|---|---|---|']
    for g, v in f['by_group'].items():
        detail = '; '.join(
            f'{i["item_id"].rsplit("-", 1)[1]}:{i["gold"][:3]}→{i["pred_es"][:3]}/{i["pred_en"][:3]}{"*" if i["flags"] else ""}'
            for i in v['items']
        )
        lines.append(f'| {g} | {c(v["by_language"]["es"])} | {c(v["by_language"]["en"])} | {detail} |')
    lines.append('')
    lines.append('`*` = item carries an errata flag. Abbreviations: ent/neu/con.')
    lines += ['', '| Paired diagnostic | count |', '|---|---|']
    lines.append(
        f'| paraphrase consistency (base vs paraphrase, per group × language) | {c(f["paraphrase_consistency"])} |'
    )
    lines.append(f'| minimal-pair sensitivity (base vs meaning change differ) | {c(f["minimal_pair_sensitivity"])} |')
    lines.append(f'| cross-lingual agreement (es vs en, per item) | {c(f["cross_lingual_agreement"])} |')
    for role, v in f['by_role'].items():
        lines.append(f'| role {role} (es+en trials) | {c(v)} |')
    lines += [
        '',
        '| Class (es+en trials) | support | predicted | correct | precision | recall |',
        '|---|---|---|---|---|---|',
    ]
    for label in LABELS:
        k = f['per_class'][label]
        lines.append(
            f'| {label} | {k["support"]} | {k["predicted"]} | {k["correct"]} | {k["precision"]} | {k["recall"]} |'
        )
    lines += ['', 'Confusion (rows gold, columns predicted): ' + json.dumps(f['confusion_gold_by_pred'])]
    if 'span' in r:
        s = r['span']
        lines += ['', '| Single-span trials | count |', '|---|---|']
        for lang in LANGUAGES:
            lines.append(f'| correct vs span label, {lang} | {c(s["by_language"][lang])} |')
        lines.append(f'| excluding convention-sensitive spans | {c(s["excluding_convention_sensitive"])} |')
        lines.append(f'| convention-sensitive spans only | {c(s["convention_sensitive_only"])} |')
        lines.append(
            f'| span prediction equals full-reference label | {c(s["span_prediction_equals_full_reference_label"])} |'
        )
    if 'probabilities_descriptive_only' in r:
        lines += ['', 'Probabilities (descriptive only): ' + json.dumps(r['probabilities_descriptive_only'])]
    lines += [
        '',
        f'Errors ({len(r["errors"])}):',
        '',
        '| trial | role | gold | pred | flags |',
        '|---|---|---|---|---|',
    ]
    for e in r['errors']:
        flag_text = ', '.join(e['flags'] + (['convention-sensitive span'] if e['convention_sensitive_span'] else []))
        lines.append(f'| `{e["trial_id"]}` | {e["role"]} | {e["gold"]} | {e["pred"]} | {flag_text} |')
    return '\n'.join(lines) + '\n'


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    flags, errata = load_errata()
    report: dict[str, Any] = {
        'fixtures_sha256': frozen_hashes(),
        'errata_sha256': sha256_file(ERRATA),
        'independence_caveat': errata['independence_caveat'],
        'systems': {},
    }
    md = [
        '# Re-scored results (replayed from retained predictions; no inference)',
        '',
        f'Fixtures: freeze manifest hashes {json.dumps(frozen_hashes())}. Errata: `fixtures/errata.json` '
        f'(sha256 {report["errata_sha256"][:16]}…), flags only.',
        '',
    ]
    for run in map(Path, sys.argv[2:]):
        manifest, predictions = load_run(run)
        system = manifest['system']
        report['systems'][system] = {'run_dir': run.name, 'run_manifest': manifest, 'sets': {}}
        for set_name, preds in predictions.items():
            r = score_set(set_name, preds, flags)
            report['systems'][system]['sets'][set_name] = r
            md.append(markdown(system, set_name, r))
    (out / 'score_report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (out / 'score_report.md').write_text('\n'.join(md), encoding='utf-8')
    print('\n'.join(md))


if __name__ == '__main__':
    main()
