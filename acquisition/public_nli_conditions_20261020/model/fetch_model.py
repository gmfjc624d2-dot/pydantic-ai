"""Download the public NLI model at an immutable revision, safetensors only, and write a hash manifest.

Usage:
    python model/fetch_model.py --revision REV --dest DIR --manifest OUT.json --attempt-log ATTEMPTS.jsonl
        [--repo MoritzLaurer/mDeBERTa-v3-base-mnli-xnli]

- REV may be a branch name; it is resolved once to a 40-hex commit SHA, and every file is downloaded at
  that SHA. Both the requested and the resolved revision are recorded.
- Only an allow-list is downloaded: `config.json`, `model.safetensors` and tokenizer files. Pickle-based
  weights (`*.bin`, `*.pt`, `*.ckpt`, `*.pkl`) are never downloaded. No safetensors file -> refuse.
- Every downloaded file is hashed (SHA-256) and checked against the Hub's metadata: LFS SHA-256 for LFS
  files, git blob SHA-1 for small files. Any mismatch -> refuse.
- Every attempt, successful or not, is appended to the attempt log with its exact error.
Weights and caches go to DEST, which must be outside the repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_REPO = 'MoritzLaurer/mDeBERTa-v3-base-mnli-xnli'
WEIGHTS = 'model.safetensors'
ALLOWED = (
    'config.json',
    WEIGHTS,
    'spm.model',
    'tokenizer.json',
    'tokenizer_config.json',
    'special_tokens_map.json',
    'added_tokens.json',
)
FORBIDDEN_SUFFIXES = ('.bin', '.pt', '.pth', '.ckpt', '.pkl', '.pickle', '.h5', '.msgpack')
SHA_RE = re.compile(r'^[0-9a-f]{40}$')


def git_blob_sha1(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def log_attempt(log: Path, record: dict[str, Any]) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    record = {
        'at': datetime.now(UTC).isoformat(),
        'host_os': platform.system(),
        'machine': platform.machine(),
        **record,
    }
    with log.open('a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')


def select_files(siblings: list[Any]) -> list[Any]:
    names = {s.rfilename for s in siblings}
    if WEIGHTS not in names:
        raise SystemExit(f'{WEIGHTS} is not published at this revision; refusing (no pickle fallback).')
    return [s for s in siblings if s.rfilename in ALLOWED and not s.rfilename.endswith(FORBIDDEN_SUFFIXES)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', default=DEFAULT_REPO)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--dest', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--attempt-log', type=Path, required=True)
    args = parser.parse_args()
    step = 'import huggingface_hub'
    try:
        import huggingface_hub
        from huggingface_hub import HfApi, hf_hub_download

        step = 'resolve revision (model_info)'
        info = HfApi().model_info(args.repo, revision=args.revision, files_metadata=True)
        resolved = info.sha
        if not resolved or not SHA_RE.match(resolved):
            raise SystemExit(f'could not resolve {args.revision!r} to a commit SHA (got {resolved!r})')
        if getattr(info, 'gated', False):
            raise SystemExit('model is gated; refusing (no account changes in this experiment)')
        card = info.card_data.to_dict() if info.card_data else {}
        files = select_files(info.siblings or [])
        args.dest.mkdir(parents=True, exist_ok=True)
        records = []
        for sibling in files:
            step = f'download {sibling.rfilename}'
            local = Path(hf_hub_download(args.repo, sibling.rfilename, revision=resolved, local_dir=args.dest))
            digest = sha256(local)
            lfs_sha = sibling.lfs.sha256 if sibling.lfs else None
            blob = sibling.blob_id
            verified = (digest == lfs_sha) if lfs_sha else (blob is not None and git_blob_sha1(local) == blob)
            if not verified:
                raise SystemExit(f'{sibling.rfilename}: hash does not match Hub metadata; refusing.')
            records.append(
                {
                    'file': sibling.rfilename,
                    'size_bytes': local.stat().st_size,
                    'sha256': digest,
                    'hub_lfs_sha256': lfs_sha,
                    'hub_git_blob_sha1': blob,
                    'verified_against_hub_metadata': verified,
                }
            )
        step = 'inspect config.json'
        config = json.loads((args.dest / 'config.json').read_text(encoding='utf-8'))
        if 'auto_map' in config:
            raise SystemExit('config.json declares auto_map (custom code); refusing (trust_remote_code=False).')
        manifest = {
            'repo': args.repo,
            'requested_revision': args.revision,
            'resolved_revision': resolved,
            'last_modified': str(getattr(info, 'last_modified', None)),
            'license_from_card': card.get('license'),
            'card_metadata_keys': sorted(card),
            'all_published_files': sorted(s.rfilename for s in info.siblings or []),
            'verified_files': records,
            'id2label': config.get('id2label'),
            'architectures': config.get('architectures'),
            'model_type': config.get('model_type'),
            'max_position_embeddings': config.get('max_position_embeddings'),
            'huggingface_hub_version': huggingface_hub.__version__,
            'fetched_at': datetime.now(UTC).isoformat(),
        }
        args.manifest.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        log_attempt(args.attempt_log, {'step': 'fetch', 'outcome': 'ok', 'resolved_revision': resolved})
        print(json.dumps(manifest, indent=2))
    except BaseException as e:
        log_attempt(
            args.attempt_log,
            {
                'step': step,
                'outcome': 'failed',
                'repo': args.repo,
                'requested_revision': args.revision,
                'error_type': type(e).__name__,
                'error': str(e)[:2000],
                'traceback_tail': traceback.format_exc()[-3000:],
            },
        )
        raise


if __name__ == '__main__':
    sys.exit(main())
