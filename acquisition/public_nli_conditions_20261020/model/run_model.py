"""CPU inference over the frozen trials with a locally verified model. Never downloads anything.

Usage:
    unshare -n python model/run_model.py --model-dir DIR --manifest model_manifest.json --run-dir RUN_DIR \
        [--threads 4]

Guarantees (each enforced in code, not by convention):
- offline: HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE are set before transformers is imported and every
  `from_pretrained` uses `local_files_only=True`; run it inside `unshare -n` (Linux) for a hard guarantee;
- `trust_remote_code=False`; refuses a config with `auto_map`; weights load with `use_safetensors=True`
  as float32 on CPU (the config's float16 is overridden and checked);
- every model/tokenizer file is re-hashed and must match the fetch manifest before loading;
- label names come from the model's own `config.id2label` (never hard-coded) and must be exactly
  {entailment, neutral, contradiction};
- inputs are encoded with `truncation=False`; a trial longer than the model limit is refused and recorded
  as `refused_overlength`, never silently truncated;
- per trial: exact premise/hypothesis, token ids, token count, raw logits (decimal and float.hex),
  softmax probabilities, duration (ns) and process peak RSS (MiB, unit converted per OS);
- one deterministic re-run of every trial; any logit difference is recorded, not hidden.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import resource
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nli_common import LABELS, frozen_hashes, sha256_file, trials, write_jsonl

OFFLINE_ENV = {
    'HF_HUB_OFFLINE': '1',
    'TRANSFORMERS_OFFLINE': '1',
    'HF_HUB_DISABLE_TELEMETRY': '1',
    'HF_DATASETS_OFFLINE': '1',
    'TOKENIZERS_PARALLELISM': 'false',
}


def peak_rss_mib() -> float:
    """Process peak resident set size in MiB (`ru_maxrss` is KiB on Linux, bytes on macOS)."""
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(raw / (1024 * 1024) if sys.platform == 'darwin' else raw / 1024, 1)


def label_order(id2label: dict[Any, str]) -> list[str]:
    """Map the model's own id2label to the three fixture labels, refusing anything else."""
    order = [str(id2label[k]).strip().lower() for k in sorted(id2label, key=int)]
    if sorted(order) != sorted(LABELS):
        raise SystemExit(f'model labels {order} are not exactly {list(LABELS)}; refusing to map them.')
    return order


def length_limit(tokenizer_max: int | None, max_positions: int | None) -> int:
    candidates = [v for v in (tokenizer_max, max_positions) if isinstance(v, int) and 0 < v < 1_000_000]
    if not candidates:
        raise SystemExit('no usable maximum input length in tokenizer or config; refusing.')
    return min(candidates)


def verify_files(model_dir: Path, manifest: dict[str, Any]) -> None:
    for entry in manifest['verified_files']:
        path = model_dir / entry['file']
        if not path.exists() or sha256_file(path) != entry['sha256']:
            raise SystemExit(f'{entry["file"]} is missing or differs from the fetch manifest; refusing.')


def softmax(logits: list[float]) -> list[float]:
    m = max(logits)
    exps = [math.exp(x - m) for x in logits]
    total = sum(exps)
    return [e / total for e in exps]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-dir', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--threads', type=int, default=4)
    args = parser.parse_args()

    os.environ.update(OFFLINE_ENV)
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    verify_files(args.model_dir, manifest)

    t_import = time.perf_counter()
    import torch
    import transformers
    from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer

    import_seconds = time.perf_counter() - t_import
    torch.manual_seed(0)
    torch.set_num_threads(args.threads)
    torch.use_deterministic_algorithms(True)

    common = {'local_files_only': True, 'trust_remote_code': False}
    t_load = time.perf_counter()
    config = AutoConfig.from_pretrained(args.model_dir, **common)
    if getattr(config, 'auto_map', None):
        raise SystemExit('config declares auto_map (custom code); refusing.')
    order = label_order(config.id2label)
    # transformers >= 5 always uses the tokenizers-backed class (it ignores `use_fast`); the class is recorded.
    tokenizer = AutoTokenizer.from_pretrained(args.model_dir, **common)
    # The published config declares float16, but FP16 is unsupported for this model (requester-reported card
    # warning): load float32 explicitly. `dtype` replaced `torch_dtype` in newer transformers releases.
    try:
        model = AutoModelForSequenceClassification.from_pretrained(
            args.model_dir, use_safetensors=True, dtype=torch.float32, **common
        )
    except TypeError:
        model = AutoModelForSequenceClassification.from_pretrained(
            args.model_dir, use_safetensors=True, torch_dtype=torch.float32, **common
        )
    model = model.float().eval()
    param_dtypes = sorted({str(p.dtype) for p in model.parameters()})
    if param_dtypes != ['torch.float32']:
        raise SystemExit(f'parameters are {param_dtypes}, expected float32 only; refusing.')
    load_seconds = time.perf_counter() - t_load
    rss_after_load = peak_rss_mib()
    limit = length_limit(getattr(tokenizer, 'model_max_length', None), getattr(config, 'max_position_embeddings', None))

    def infer(premise: str, hypothesis: str) -> dict[str, Any]:
        enc = tokenizer(premise, hypothesis, truncation=False, return_tensors='pt')
        ids = enc['input_ids'][0].tolist()
        record: dict[str, Any] = {
            'token_count': len(ids),
            'input_ids': ids,
            'input_ids_sha256': hashlib.sha256(json.dumps(ids).encode()).hexdigest(),
            'max_tokens': limit,
        }
        if len(ids) > limit:
            return {**record, 'status': 'refused_overlength'}
        t0 = time.perf_counter_ns()
        with torch.inference_mode():
            logits = model(**enc).logits[0].tolist()
        record['duration_ns'] = time.perf_counter_ns() - t0
        probs = softmax(logits)
        return {
            **record,
            'status': 'ok',
            'label_order': order,
            'logits': logits,
            'logits_hex': [float(x).hex() for x in logits],
            'probabilities': probs,
            'predicted_label': order[max(range(len(order)), key=lambda i: logits[i])],
            'peak_rss_mib_after_trial': peak_rss_mib(),
        }

    system = f'{manifest["repo"]}@{manifest["resolved_revision"][:12]}'
    run_manifest: dict[str, Any] = {
        'system': system,
        'model_manifest_sha256': sha256_file(args.manifest),
        'resolved_revision': manifest['resolved_revision'],
        'fixtures_sha256': frozen_hashes(),
        'code_sha256': sha256_file(Path(__file__)),
        'tokenizer_class': type(tokenizer).__name__,
        'config_torch_dtype': str(getattr(config, 'torch_dtype', None)),
        'loaded_parameter_dtypes': param_dtypes,
        'device': 'cpu',
        'label_order': order,
        'max_tokens': limit,
        'versions': {
            'python': platform.python_version(),
            'torch': torch.__version__,
            'transformers': transformers.__version__,
        },
        'torch_threads': torch.get_num_threads(),
        'platform': {'system': platform.system(), 'machine': platform.machine(), 'release': platform.release()},
        'offline_env': OFFLINE_ENV,
        'import_seconds': round(import_seconds, 3),
        'load_seconds': round(load_seconds, 3),
        'peak_rss_mib_after_load': rss_after_load,
        'started_at': datetime.now(UTC).isoformat(),
        'files': {},
        'determinism_recheck': {},
    }
    for set_name in ('dev', 'heldout'):
        rows, mismatches = [], []
        for trial in trials(set_name):
            first = infer(trial['premise'], trial['hypothesis'])
            if first['status'] == 'ok':
                second = infer(trial['premise'], trial['hypothesis'])
                if second.get('logits_hex') != first['logits_hex']:
                    mismatches.append(trial['trial_id'])
            rows.append(
                {
                    'schema': 'nli-prediction/v1',
                    'system': system,
                    'trial_id': trial['trial_id'],
                    'premise': trial['premise'],
                    'hypothesis': trial['hypothesis'],
                    **first,
                }
            )
        name = f'predictions--{set_name}.jsonl'
        run_manifest['files'][name] = {'sha256': write_jsonl(args.run_dir / name, rows), 'trials': len(rows)}
        run_manifest['determinism_recheck'][set_name] = {'logit_mismatches': mismatches}
    run_manifest['peak_rss_mib_end'] = peak_rss_mib()
    run_manifest['finished_at'] = datetime.now(UTC).isoformat()
    (args.run_dir / 'run_manifest.json').write_text(json.dumps(run_manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in run_manifest.items() if k != 'files'}, indent=2))


if __name__ == '__main__':
    main()
