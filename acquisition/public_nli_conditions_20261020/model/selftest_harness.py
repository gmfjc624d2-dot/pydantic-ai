"""Torch-free self-test of the inference harness's safety logic (stdlib only).

Usage: python model/selftest_harness.py

Exercises what can be checked without model weights: label mapping from `id2label`, length-limit
selection and overlength refusal, manifest hash verification, the safetensors-only file selection,
and trial construction from the frozen fixtures. It does not load or imitate any model.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fetch_model import WEIGHTS, select_files
from nli_common import sha256_file, trials
from run_model import label_order, length_limit, verify_files
from verify_local_model import verify


def expect_exit(fn, *args) -> str:  # type: ignore[no-untyped-def]
    try:
        fn(*args)
    except SystemExit as e:
        return str(e)
    raise AssertionError(f'{fn.__name__}{args} did not refuse')


def main() -> None:
    checks = []
    assert label_order({'0': 'entailment', '1': 'neutral', '2': 'contradiction'}) == [
        'entailment',
        'neutral',
        'contradiction',
    ]
    assert label_order({0: 'CONTRADICTION', 1: 'NEUTRAL', 2: 'ENTAILMENT'}) == [
        'contradiction',
        'neutral',
        'entailment',
    ]
    expect_exit(label_order, {'0': 'LABEL_0', '1': 'LABEL_1', '2': 'LABEL_2'})
    expect_exit(label_order, {'0': 'entailment', '1': 'not_entailment'})
    checks.append('label order is read from id2label; generic or 2-way labels are refused')

    assert length_limit(512, 512) == 512 and length_limit(1_000_000_000_000_000_019_884_624_838_656, 512) == 512
    expect_exit(length_limit, None, None)
    checks.append('length limit = min(tokenizer limit, max positions); sentinel tokenizer limits ignored')

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / 'config.json').write_text('{}')
        manifest = {'verified_files': [{'file': 'config.json', 'sha256': sha256_file(d / 'config.json')}]}
        verify_files(d, manifest)
        (d / 'config.json').write_text('{"tampered": true}')
        expect_exit(verify_files, d, manifest)
    checks.append('files whose SHA-256 differs from the fetch manifest are refused')

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / 'model.safetensors').write_bytes(b'placeholder bytes, not a model')
        config = {
            'architectures': ['DebertaV2ForSequenceClassification'],
            'id2label': {'0': 'entailment', '1': 'neutral', '2': 'contradiction'},
            'max_position_embeddings': 512,
        }
        (d / 'config.json').write_text(json.dumps(config))
        expected = {
            'repo': 'example/repo',
            'revision': '0' * 40,
            'provenance': 'self-test',
            'license_from_card': 'mit',
            'config': config,
            'files': {
                'model.safetensors': {
                    'size_bytes': (d / 'model.safetensors').stat().st_size,
                    'sha256': sha256_file(d / 'model.safetensors'),
                }
            },
        }
        manifest = verify(d, expected)
        assert [f['file'] for f in manifest['verified_files']] == ['model.safetensors', 'config.json']
        verify_files(d, manifest)
        (d / 'pytorch_model.bin').write_bytes(b'x')
        assert verify(d, expected)['pickle_files_present_not_loaded'] == ['pytorch_model.bin']
        (d / 'config.json').write_text(json.dumps({**config, 'auto_map': {'x': 'y'}}))
        expect_exit(verify, d, expected)
        (d / 'config.json').write_text(
            json.dumps({**config, 'id2label': {'0': 'contradiction', '1': 'neutral', '2': 'entailment'}})
        )
        expect_exit(verify, d, expected)
        (d / 'config.json').write_text(json.dumps(config))
        (d / 'model.safetensors').write_bytes(b'tampered')
        expect_exit(verify, d, expected)
        expect_exit(verify, d / 'missing', expected)
    checks.append(
        'local-directory verifier: accepts matching files; refuses missing dir, size/hash mismatch, auto_map, reordered id2label; records (never loads) pickle files'
    )

    sib = [SimpleNamespace(rfilename=n) for n in ('config.json', 'pytorch_model.bin', 'spm.model')]
    expect_exit(select_files, sib)
    sib.append(SimpleNamespace(rfilename=WEIGHTS))
    assert sorted(s.rfilename for s in select_files(sib)) == ['config.json', 'model.safetensors', 'spm.model']
    checks.append('no safetensors -> refuse; pickle weights are never selected')

    for set_name in ('dev', 'heldout'):
        ts = trials(set_name)
        assert len(ts) == 64 and len({t['trial_id'] for t in ts}) == 64
        assert all(t['hypothesis'] not in t['premise'] for t in ts)
        assert sum(t['trial_type'] == 'span' for t in ts) == 16
    checks.append('64 trials per set (48 full + 16 span); hypothesis never embedded in premise')

    longest = max(len(t['premise']) + len(t['hypothesis']) for s in ('dev', 'heldout') for t in trials(s))
    checks.append(
        f'longest premise+hypothesis is {longest} characters (far below a 512-token limit, but the token check still runs per trial)'
    )
    print('\n'.join(f'ok: {c}' for c in checks))


if __name__ == '__main__':
    main()
