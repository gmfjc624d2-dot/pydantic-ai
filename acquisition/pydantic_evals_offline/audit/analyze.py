"""Summarize `run_audit.sh` results: strace, probe output, local sink captures, sandbox leftovers.

Usage: python analyze.py RESULTS_DIR   -> writes RESULTS_DIR/summary.json and RESULTS_DIR/summary.md
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

CANARY_RE = re.compile(rb'CANARY-(INPUT|SECRETKEY|META|EXPECTED|OUTPUT|ERROR)-[0-9a-f]{6}')
LINE_RE = re.compile(r'^(\d+)\s+(?:<\.\.\. )?(\w+)(?: resumed>)?\(?(.*)$')
WRITE_FLAGS = ('O_WRONLY', 'O_RDWR', 'O_CREAT', 'O_TRUNC', 'O_APPEND')


def parse_strace(path: Path, sandbox: str, results_out: str) -> dict[str, Any]:
    sockets: Counter[str] = Counter()
    connects: list[dict[str, str]] = []
    sends_to: list[str] = []
    binds: list[str] = []
    execs: list[str] = []
    threads = processes = 0
    writes: Counter[str] = Counter()
    write_samples: dict[str, list[str]] = {}
    pids: set[str] = set()
    if not path.exists():
        return {'missing': True}
    for raw in path.read_text(encoding='utf-8', errors='replace').splitlines():
        m = LINE_RE.match(raw)
        if not m:
            continue
        pid, call, rest = m.groups()
        pids.add(pid)
        if call == 'socket' and 'resumed' not in raw:
            family = rest.split(',', 1)[0]
            sockets[family] += 1
        elif call == 'connect' and 'sa_family=' in rest:
            family = re.search(r'sa_family=(\w+)', rest)
            fam = family.group(1) if family else '?'
            if fam == 'AF_UNIX':
                dest = re.search(r'sun_path="([^"]*)"', rest)
                target = dest.group(1) if dest else '?'
            else:
                port = re.search(r'htons\((\d+)\)', rest)
                addr = re.search(r'inet6?_(?:addr|pton)\((?:AF_INET6, )?"([^"]+)"', rest)
                target = f'{addr.group(1) if addr else "?"}:{port.group(1) if port else "?"}'
            result = rest.rsplit('= ', 1)[-1] if '= ' in rest else 'unfinished'
            connects.append({'family': fam, 'target': target, 'result': result[:60]})
        elif call in {'sendto', 'sendmsg'} and 'sa_family=AF_INET' in rest:
            sends_to.append(rest[-160:])
        elif call == 'bind' and 'sa_family=AF_INET' in rest:
            binds.append(rest[:160])
        elif call in {'execve', 'execveat'}:
            argv = re.search(r'\[([^]]*)\]', rest)
            if argv:
                execs.append(' '.join(json.loads(f'[{argv.group(1)}]'))[:120])
        elif call in {'clone', 'clone3', 'fork', 'vfork'} and 'resumed' not in raw:
            if 'CLONE_THREAD' in rest:
                threads += 1
            else:
                processes += 1
        elif call in {
            'openat',
            'open',
            'creat',
            'mkdir',
            'mkdirat',
            'rename',
            'renameat',
            'renameat2',
            'unlink',
            'unlinkat',
        }:
            if call.startswith('open') and not any(f in rest for f in WRITE_FLAGS):
                continue
            if (
                rest.rstrip().endswith(('ENOENT (No such file or directory)', 'EEXIST (File exists)'))
                and call != 'unlinkat'
            ):
                pass
            p = re.search(r'"([^"]*)"', rest)
            target = p.group(1) if p else '?'
            if not target.startswith('/'):
                cls = 'dirfd-relative (shutil.rmtree of the worker temp dir)'
            elif target.startswith(results_out):
                cls = 'harness-output'
            elif target.startswith(f'{sandbox}/tmp/sw-'):
                cls = 'worker-db (synthetic worker)'
            elif target.startswith(f'{sandbox}/home'):
                cls = 'HOME'
            elif target.startswith(f'{sandbox}/cwd'):
                cls = 'cwd'
            elif target.startswith(f'{sandbox}/tmp'):
                cls = 'TMPDIR (other)'
            elif target.startswith('/dev/'):
                cls = 'device'
            else:
                cls = 'other'
            key = f'{cls}:{call}'
            writes[key] += 1
            write_samples.setdefault(cls, [])
            if len(write_samples[cls]) < 5 and target not in write_samples[cls]:
                write_samples[cls].append(target)
    inet_connects = [c for c in connects if c['family'] in {'AF_INET', 'AF_INET6'}]
    return {
        'pids_seen': len(pids),
        'sockets_by_family': dict(sockets),
        'inet_connect_attempts': inet_connects,
        'unix_connects': sorted({c['target'] for c in connects if c['family'] == 'AF_UNIX'}),
        'inet_sendto': sends_to[:5],
        'inet_binds': binds[:5],
        'execve': execs,
        'threads_created': threads,
        'processes_created': processes,
        'fs_mutations': dict(sorted(writes.items())),
        'fs_mutation_samples': write_samples,
    }


def analyze_run(run_dir: Path) -> dict[str, Any]:
    info = dict(line.split('=', 1) for line in (run_dir / 'run.txt').read_text().splitlines() if '=' in line)
    sandbox = info.get('sandbox', '/nonexistent')
    out: dict[str, Any] = {'id': run_dir.name, 'run': info}
    out['strace'] = parse_strace(run_dir / 'strace.txt', sandbox, str(run_dir / 'out'))
    probe = run_dir / 'out' / 'probe.json'
    if probe.exists():
        p = json.loads(probe.read_text())
        env_keys = list(p['env_keys_read'])
        out['probe'] = {
            'report': p['report'],
            'import_seconds': p['import_seconds'],
            'eval_seconds': p['eval_seconds'],
            'peak_rss_mib': p['peak_rss_mib'],
            'modules_imported_by_pydantic_evals': p['modules_imported_by_pydantic_evals'],
            'pydantic_ai_agent_imported': p['pydantic_ai_agent_imported'],
            'logfire_imported': p['logfire_imported'],
            'otel_sdk_imported': p['otel_sdk_imported'],
            'env_keys_read_count': len(env_keys),
            'env_keys_read_otel': [k for k in env_keys if k.startswith('OTEL_')],
            'env_keys_read_logfire': [k for k in env_keys if k.startswith('LOGFIRE_')],
            'env_keys_read_other': [k for k in env_keys if not k.startswith(('OTEL_', 'LOGFIRE_'))],
            'audit_events_by_origin': Counter(
                f'{e["event"]} <- {e["origin"].split("/")[0] or "?"}' for e in p['audit_events']
            ).most_common(),
            'subprocesses': [e['args'][:2] for e in p['audit_events'] if e['event'] == 'subprocess.Popen'],
            'span_count': p['span_count'],
            'spans_with_canaries': Counter(
                f'{s["span"]} :: {s.get("attribute") or "event:" + s.get("event", "?")} :: {",".join(s["canaries"])}'
                for s in p['spans_with_canaries']
            ).most_common(),
        }
    else:
        out['probe'] = None
        stderr = run_dir / 'stderr.txt'
        out['stderr_tail'] = stderr.read_text()[-1500:] if stderr.exists() else None
    sink = run_dir / 'sink'
    if sink.exists():
        bodies = sorted(p for p in sink.iterdir() if p.suffix == '.bin')
        hits: Counter[str] = Counter()
        for body in bodies:
            for m in CANARY_RE.finditer(body.read_bytes()):
                hits[m.group(1).decode()] += 1
        out['local_sink'] = {
            'requests': len(bodies),
            'paths': sorted({b.name.split('_', 1)[1] for b in bodies}),
            'bytes': sum(b.stat().st_size for b in bodies),
            'canary_hits': dict(hits),
            'git_or_host_in_payload': any(b'host.name' in b.read_bytes() for b in bodies),
        }
    left = (
        (run_dir / 'files_left_in_sandbox.txt').read_text().split()
        if (run_dir / 'files_left_in_sandbox.txt').exists()
        else []
    )
    out['files_left_in_sandbox'] = left
    canary_files = run_dir / 'canary_files_in_sandbox.txt'
    out['sandbox_files_with_canaries'] = canary_files.read_text().split() if canary_files.exists() else []
    stdout = run_dir / 'stdout.txt'
    out['stdout_bytes'] = stdout.stat().st_size if stdout.exists() else None
    return out


def markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        '| run | completed | inet connect attempts | processes spawned (execve) | fs writes outside harness/worker | env keys read (OTEL/LOGFIRE/other) | canaries in local sink | canaries in spans |',
        '|---|---|---|---|---|---|---|---|',
    ]
    for r in rows:
        if r['id'].startswith('offline-'):
            continue
        s = r['strace']
        p = r['probe'] or {}
        inet = (
            ', '.join(f'{c["target"]} ({c["result"].split(" ")[0]})' for c in s.get('inet_connect_attempts', []))
            or 'none'
        )
        execs = [e for e in s.get('execve', [])[1:]]
        fs = {
            k: v
            for k, v in s.get('fs_mutations', {}).items()
            if not k.startswith(('harness-output', 'worker-db', 'device', 'dirfd-relative'))
        }
        env = f'{len(p.get("env_keys_read_otel", []))}/{len(p.get("env_keys_read_logfire", []))}/{len(p.get("env_keys_read_other", []))}'
        sink = r.get('local_sink')
        sink_txt = f'{sink["requests"]} req, {sink["canary_hits"] or "no canaries"}' if sink else 'n/a'
        spans = p.get('spans_with_canaries') or []
        canaries_in_spans = (
            sorted({c for row, _ in spans for c in row.rsplit(' :: ', 1)[-1].split(',')}) if spans else []
        )
        rep = p.get('report') or {}
        done = f'yes ({rep.get("cases")} cases, {rep.get("failures")} failure)' if p else 'NO'
        lines.append(
            f'| {r["id"]} | {done} | {inet} | {"; ".join(execs) or "none"} | {fs or "none"} | {env} | {sink_txt} | {canaries_in_spans or "n/a" if p.get("span_count") is None else canaries_in_spans} |'
        )
    return '\n'.join(lines) + '\n'


def main() -> None:
    results = Path(sys.argv[1])
    rows = [analyze_run(d) for d in sorted(results.iterdir()) if d.is_dir() and (d / 'run.txt').exists()]
    (results / 'summary.json').write_text(json.dumps(rows, indent=2) + '\n')
    (results / 'summary.md').write_text(markdown(rows))
    print(markdown(rows))


if __name__ == '__main__':
    main()
