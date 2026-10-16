"""In-process privacy probe: run a small synthetic evaluation and record what the process did.

Usage: python probe_run.py OUT_DIR [--configure-logfire] [--memory-exporter]

Recorded (Python level; the OS-level view comes from `strace` in `run_audit.sh`):
- audit-hook events: sockets, subprocesses, exec/fork, file opens for writing, mkdir/rename/remove,
  sqlite3.connect, urllib/http.client, each attributed to the first non-probe frame's module;
- environment variable reads (keys only) through `os.environ` / `os.getenv`;
- import time, module counts and peak RSS;
- with `--memory-exporter`: every span attribute that carries a canary string.

Canary strings are planted in case inputs, metadata, expected output, task output and an exception
message, so that any copy of test content (in files, spans or network payloads) can be found.
"""

from __future__ import annotations

import json
import os
import resource
import sys
import time
from pathlib import Path
from typing import Any

PROBE_FILE = __file__
WORKER_DIR = Path(__file__).resolve().parent.parent / 'worker'

CANARIES = {
    'input': 'CANARY-INPUT-5f1c9a',
    'input_under_secret_key': 'CANARY-SECRETKEY-81e0d4',
    'metadata': 'CANARY-META-3a8b0c',
    'expected': 'CANARY-EXPECTED-2b7f61',
    'output': 'CANARY-OUTPUT-7d2e4b',
    'error': 'CANARY-ERROR-9c4d1e',
}

events: list[dict[str, Any]] = []
env_reads: dict[str, int] = {}
_recording = True

_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC
_INTERESTING_PREFIXES = (
    'socket.',
    'subprocess.',
    'os.system',
    'os.exec',
    'os.posix_spawn',
    'os.spawn',
    'os.fork',
    'os.forkpty',
    'os.mkdir',
    'os.rename',
    'os.remove',
    'os.rmdir',
    'os.putenv',
    'os.unsetenv',
    'shutil.',
    'sqlite3.connect',
    'urllib.Request',
    'http.client.',
    'webbrowser.open',
    'ctypes.dlopen',
)


def _origin() -> str:
    """Module of the innermost frame that is neither this probe nor the stdlib."""
    frame = sys._getframe(1)
    stdlib = os.path.dirname(os.__file__)
    first_non_probe = None
    while frame is not None:
        filename = frame.f_code.co_filename
        if filename != PROBE_FILE and not filename.startswith('<'):
            if first_non_probe is None:
                first_non_probe = filename
            if not filename.startswith(stdlib) or 'site-packages' in filename:
                return filename.split('site-packages/')[-1]
        frame = frame.f_back
    return (first_non_probe or '?').split('site-packages/')[-1]


def _hook(event: str, args: tuple[Any, ...]) -> None:
    if not _recording:
        return
    if event == 'open':
        path, mode, flags = args
        writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
            mode is None and isinstance(flags, int) and flags & _WRITE_FLAGS
        )
        if not writing:
            return
        events.append({'event': 'open-write', 'path': str(path), 'mode': mode, 'origin': _origin()})
        return
    if event.startswith(_INTERESTING_PREFIXES):
        safe_args = [repr(a)[:200] for a in args]
        events.append({'event': event, 'args': safe_args, 'origin': _origin()})


def _track_environ() -> None:
    environ_type = type(os.environ)
    original_getitem = environ_type.__getitem__

    def getitem(self: Any, key: str) -> Any:
        if _recording:
            name = key.decode(errors='replace') if isinstance(key, bytes) else str(key)
            env_reads[name] = env_reads.get(name, 0) + 1
        return original_getitem(self, key)

    environ_type.__getitem__ = getitem  # type: ignore[method-assign]


def main() -> None:
    global _recording
    out = Path(sys.argv[1])
    configure_logfire = '--configure-logfire' in sys.argv
    memory_exporter = '--memory-exporter' in sys.argv
    out.mkdir(parents=True, exist_ok=True)
    _recording = False
    sys.addaudithook(_hook)
    _track_environ()
    sys.path.insert(0, str(WORKER_DIR))
    from scenarios import SCENARIOS_BY_ID, run_scenario

    _recording = True
    modules_before = set(sys.modules)
    t0 = time.perf_counter()
    from pydantic_evals import Case, Dataset
    from pydantic_evals.evaluators import EvaluationReason, Evaluator, EvaluatorContext
    from pydantic_evals.reporting import EvaluationReportAdapter

    import_seconds = time.perf_counter() - t0
    imported = sorted(set(sys.modules) - modules_before)
    top_level = sorted({m.split('.')[0] for m in imported})

    memory = None
    if configure_logfire:
        import logfire

        processors = []
        if memory_exporter:
            from opentelemetry.sdk.trace.export import SimpleSpanProcessor
            from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

            memory = InMemorySpanExporter()
            processors.append(SimpleSpanProcessor(memory))
        logfire.configure(send_to_logfire=False, console=False, additional_span_processors=processors)

    from dataclasses import dataclass

    @dataclass
    class LedgerAgrees(Evaluator):
        def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
            effects = len(ctx.output['observation']['ledger']['effects'])
            return EvaluationReason(value=effects <= 1, reason=f'{effects} effect(s) in ledger')

    def task(inputs: dict[str, Any]) -> dict[str, Any]:
        if inputs['scenario'] == 'worker-raises':
            raise RuntimeError(f'worker exploded {CANARIES["error"]}')
        observation = run_scenario('v1-correct', SCENARIOS_BY_ID[inputs['scenario']].as_inputs())
        return {'observation': observation, 'note': CANARIES['output']}

    scenario_ids = ['lookup-hit', 'lost-response-then-retry', 'balance-truncated', 'raise-before-effect-then-retry']
    dataset = Dataset(
        name='privacy-probe',
        cases=[
            Case(
                name=sid,
                inputs={
                    'scenario': sid,
                    'customer_note': CANARIES['input'],
                    'secret': CANARIES['input_under_secret_key'],
                },
                metadata={'tag': CANARIES['metadata']},
                expected_output={'expected': CANARIES['expected']},
            )
            for sid in [*scenario_ids, 'worker-raises']
        ],
        evaluators=[LedgerAgrees()],
    )
    t1 = time.perf_counter()
    report = dataset.evaluate_sync(task, progress=False, max_concurrency=2)
    eval_seconds = time.perf_counter() - t1
    _recording = False

    report_json = EvaluationReportAdapter.dump_json(report, indent=2)
    (out / 'report.json').write_bytes(report_json)

    span_findings: list[dict[str, Any]] = []
    if memory is not None:
        for span in memory.get_finished_spans():
            for key, value in (span.attributes or {}).items():
                text = str(value)
                hits = [name for name, canary in CANARIES.items() if canary in text]
                if hits:
                    span_findings.append({'span': span.name, 'attribute': key, 'canaries': hits})
            for event in span.events:
                text = json.dumps(dict(event.attributes or {}), default=str)
                hits = [name for name, canary in CANARIES.items() if canary in text]
                if hits:
                    span_findings.append({'span': span.name, 'event': event.name, 'canaries': hits})

    result = {
        'argv': sys.argv[2:],
        'python': sys.version.split()[0],
        'import_seconds': round(import_seconds, 3),
        'eval_seconds': round(eval_seconds, 3),
        # `ru_maxrss` is KiB on Linux but bytes on macOS.
        'peak_rss_mib': round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024 if sys.platform == 'darwin' else 1024), 1
        ),
        'modules_imported_by_pydantic_evals': len(imported),
        'top_level_packages_imported': top_level,
        'pydantic_ai_agent_imported': 'pydantic_ai.agent' in sys.modules,
        'logfire_imported': 'logfire' in sys.modules,
        'otel_sdk_imported': 'opentelemetry.sdk' in sys.modules,
        'report': {
            'cases': len(report.cases),
            'failures': len(report.failures),
            'trace_id_present': report.trace_id is not None,
        },
        'audit_events': events,
        'env_keys_read': dict(sorted(env_reads.items())),
        'spans_with_canaries': span_findings,
        'span_count': len(memory.get_finished_spans()) if memory is not None else None,
    }
    (out / 'probe.json').write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
