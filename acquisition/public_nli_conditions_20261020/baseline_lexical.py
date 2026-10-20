"""Deterministic lexical baseline (no model, no training data, stdlib only).

Usage:
    python baseline_lexical.py fit OUT_CONFIG.json          # fits the single threshold on DEV only
    python baseline_lexical.py predict CONFIG.json RUN_DIR  # writes predictions for dev and heldout

Rule (documented so that every prediction can be recomputed by hand):
1. Normalize: Unicode NFKD, drop combining marks (accents), lowercase, tokens = runs of [a-z0-9].
2. Remove the fixed stopword lists below and the negation cues.
3. coverage = share of hypothesis content tokens found in the premise. A token matches if it is
   equal to a premise token, or if both are at least 5 characters long and share their first 5
   characters (crude inflection handling: fabricado/fabricados, records/recorded).
4. If coverage >= tau: predict `contradiction` when the parity of negation cues differs between
   hypothesis and premise, or the hypothesis contains a digit token absent from the premise;
   otherwise `entailment`. If coverage < tau: `neutral`.

tau is chosen from {0.50, 0.55, ..., 1.00} by macro-F1 on DEV full-context trials (both languages),
ties broken toward the larger tau. It is never fitted on held-out data.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nli_common import LABELS, frozen_hashes, sha256_file, trials, write_jsonl

SYSTEM = 'lexical-baseline/v1'
GRID = [round(0.5 + 0.05 * i, 2) for i in range(11)]
PREFIX = 5

STOPWORDS = {
    # English function words
    'a',
    'an',
    'the',
    'of',
    'in',
    'on',
    'at',
    'to',
    'for',
    'by',
    'from',
    'with',
    'and',
    'or',
    'that',
    'this',
    'it',
    'its',
    'is',
    'are',
    'was',
    'were',
    'be',
    'been',
    'has',
    'have',
    'had',
    'will',
    'may',
    'might',
    'can',
    'do',
    'does',
    'did',
    'there',
    'their',
    'all',
    'every',
    'each',
    'some',
    'any',
    'one',
    'if',
    'when',
    'even',
    'however',
    'according',
    'only',
    'which',
    'who',
    'what',
    'as',
    'than',
    'so',
    # Spanish function words
    'el',
    'la',
    'los',
    'las',
    'un',
    'una',
    'unos',
    'unas',
    'de',
    'del',
    'al',
    'en',
    'a',
    'por',
    'para',
    'con',
    'y',
    'o',
    'que',
    'se',
    'su',
    'sus',
    'es',
    'son',
    'fue',
    'era',
    'estaba',
    'esta',
    'este',
    'ha',
    'han',
    'hay',
    'todos',
    'todas',
    'cada',
    'algunos',
    'algunas',
    'alguna',
    'si',
    'cuando',
    'incluso',
    'sin',
    'embargo',
    'segun',
    'solo',
    'lo',
    'le',
    'les',
    'mas',
    'muy',
    'puede',
    'pueden',
}
NEGATION_CUES = {
    'no',
    'not',
    'never',
    'none',
    'nothing',
    'nobody',
    'neither',
    'nor',
    'without',
    'cannot',
    'nunca',
    'ninguno',
    'ninguna',
    'ningun',
    'nada',
    'nadie',
    'ni',
    'jamas',
    'tampoco',
}


def tokens(text: str) -> list[str]:
    decomposed = unicodedata.normalize('NFKD', text)
    stripped = ''.join(c for c in decomposed if not unicodedata.combining(c)).lower()
    return re.findall(r'[a-z0-9]+', stripped)


def features(premise: str, hypothesis: str) -> dict[str, Any]:
    p_tokens, h_tokens = tokens(premise), tokens(hypothesis)
    p_content = {t for t in p_tokens if t not in STOPWORDS and t not in NEGATION_CUES}
    h_content = [t for t in h_tokens if t not in STOPWORDS and t not in NEGATION_CUES]

    def matched(token: str) -> bool:
        if token in p_content:
            return True
        return len(token) >= PREFIX and any(len(p) >= PREFIX and p[:PREFIX] == token[:PREFIX] for p in p_content)

    hits = [t for t in h_content if matched(t)]
    neg_p = sum(t in NEGATION_CUES for t in p_tokens)
    neg_h = sum(t in NEGATION_CUES for t in h_tokens)
    digits_missing = sorted({t for t in h_tokens if t.isdigit()} - {t for t in p_tokens if t.isdigit()})
    return {
        'coverage': round(len(hits) / len(h_content), 6) if h_content else 1.0,
        'hypothesis_content_tokens': h_content,
        'unmatched_tokens': [t for t in h_content if not matched(t)],
        'negation_cues_premise': neg_p,
        'negation_cues_hypothesis': neg_h,
        'negation_parity_mismatch': (neg_p % 2) != (neg_h % 2),
        'digits_missing_from_premise': digits_missing,
    }


def decide(feat: dict[str, Any], tau: float) -> str:
    if feat['coverage'] < tau:
        return 'neutral'
    if feat['negation_parity_mismatch'] or feat['digits_missing_from_premise']:
        return 'contradiction'
    return 'entailment'


def macro_f1(golds: list[str], preds: list[str]) -> float:
    scores = []
    for label in LABELS:
        tp = sum(g == p == label for g, p in zip(golds, preds))
        fp = sum(p == label and g != label for g, p in zip(golds, preds))
        fn = sum(g == label and p != label for g, p in zip(golds, preds))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return sum(scores) / len(scores)


def fit(out: Path) -> None:
    dev = [t for t in trials('dev') if t['trial_type'] == 'full']
    feats = [features(t['premise'], t['hypothesis']) for t in dev]
    golds = [t['gold'] for t in dev]
    grid = []
    for tau in GRID:
        preds = [decide(f, tau) for f in feats]
        grid.append(
            {
                'tau': tau,
                'dev_macro_f1': round(macro_f1(golds, preds), 6),
                'dev_accuracy': round(sum(g == p for g, p in zip(golds, preds)) / len(golds), 6),
            }
        )
    best = max(grid, key=lambda row: (row['dev_macro_f1'], row['tau']))
    config = {
        'system': SYSTEM,
        'tau': best['tau'],
        'selection': 'max dev macro-F1 over dev full-context trials (es+en), ties -> larger tau; held-out never used',
        'grid': grid,
        'prefix_match_chars': PREFIX,
        'fixtures_sha256': frozen_hashes(),
        'code_sha256': sha256_file(Path(__file__)),
        'fitted_at': datetime.now(UTC).isoformat(),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(config, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: config[k] for k in ('tau', 'selection')}, indent=2))


def predict(config_path: Path, run_dir: Path) -> None:
    config = json.loads(config_path.read_text(encoding='utf-8'))
    if config['fixtures_sha256'] != frozen_hashes():
        raise SystemExit('config was fitted on different fixtures; refusing.')
    if config['code_sha256'] != sha256_file(Path(__file__)):
        raise SystemExit('baseline code changed since fitting; refit into a new config.')
    manifest: dict[str, Any] = {
        'system': SYSTEM,
        'config': config_path.name,
        'config_sha256': sha256_file(config_path),
        'fixtures_sha256': frozen_hashes(),
        'python': sys.version.split()[0],
        'created_at': datetime.now(UTC).isoformat(),
        'files': {},
    }
    for set_name in ('dev', 'heldout'):
        rows = []
        for trial in trials(set_name):
            feat = features(trial['premise'], trial['hypothesis'])
            rows.append(
                {
                    'schema': 'nli-prediction/v1',
                    'system': SYSTEM,
                    'trial_id': trial['trial_id'],
                    'premise': trial['premise'],
                    'hypothesis': trial['hypothesis'],
                    'predicted_label': decide(feat, config['tau']),
                    'features': feat,
                    'tau': config['tau'],
                }
            )
        name = f'predictions--{set_name}.jsonl'
        manifest['files'][name] = {
            'sha256': write_jsonl(run_dir / name, rows),
            'trials': len(rows),
            'predicted': dict(Counter(r['predicted_label'] for r in rows)),
        }
    (run_dir / 'run_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(manifest['files'], indent=2))


if __name__ == '__main__':
    if sys.argv[1] == 'fit':
        fit(Path(sys.argv[2]))
    elif sys.argv[1] == 'predict':
        predict(Path(sys.argv[2]), Path(sys.argv[3]))
    else:
        raise SystemExit(__doc__)
