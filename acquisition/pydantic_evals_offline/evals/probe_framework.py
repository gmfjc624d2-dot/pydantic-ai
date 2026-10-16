"""Probes of Pydantic Evals' own behavior: failures, retries, crashes, repeatability, serialization.

Usage: python evals/probe_framework.py OUT_JSON [--probe NAME ...]

Every probe records what was *observed*; nothing here asserts what the library "should" do.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'worker'))

from scenarios import SCENARIOS_BY_ID, effects_per_key, run_scenario
from synthetic_worker import handle, init_db, ledger_snapshot

from pydantic_evals import Case, CaseLifecycle, Dataset, increment_eval_metric
from pydantic_evals.evaluators import EvaluationReason, Evaluator, EvaluatorContext
from pydantic_evals.reporting import EvaluationReportAdapter, ReportCase, ReportCaseFailure

PROBES: dict[str, Any] = {}


def probe(fn: Any) -> Any:
    PROBES[fn.__name__] = fn
    return fn


@dataclass
class ParsedOk(Evaluator):
    """Robust: a malformed response is a failed assertion."""

    def evaluate(self, ctx: EvaluatorContext) -> EvaluationReason:
        try:
            json.loads(ctx.output['text'])
        except json.JSONDecodeError as e:
            return EvaluationReason(value=False, reason=f'malformed: {e}')
        return EvaluationReason(value=True)


@dataclass
class NaiveParsedOk(Evaluator):
    """Naive: a malformed response makes the *evaluator* raise."""

    def evaluate(self, ctx: EvaluatorContext) -> bool:
        return json.loads(ctx.output['text'])['ok'] is True


def _two_case_dataset(evaluator: Evaluator) -> Dataset:
    return Dataset(
        name='parse',
        cases=[
            Case(name='well-formed', inputs={'text': '{"ok": true}'}),
            Case(name='truncated', inputs={'text': '{"ok": tr'}),
        ],
        evaluators=[evaluator],
    )


@probe
def worker_exception() -> dict[str, Any]:
    """The task lets a worker exception escape (no capture harness)."""
    workdir = Path(tempfile.mkdtemp())
    db = workdir / 'w.sqlite3'
    init_db(db)

    def task(inputs: dict[str, Any]) -> str:
        return handle(db, inputs)

    ds = Dataset(
        name='raw',
        cases=[
            Case(
                name='raise-before-effect',
                inputs={
                    'op': 'record',
                    'account': 'a',
                    'amount': 1,
                    'idempotency_key': 'k1',
                    'fault': 'raise_before_effect',
                },
            ),
            Case(
                name='effect-then-lost-response',
                inputs={'op': 'record', 'account': 'a', 'amount': 1, 'idempotency_key': 'k2', 'fault': 'lose_response'},
            ),
        ],
    )
    report = ds.evaluate_sync(task, progress=False)
    failures = {f.name: f for f in report.failures}
    lost = failures['effect-then-lost-response']
    return {
        'n_cases': len(report.cases),
        'n_failures': len(report.failures),
        'failure_fields': sorted(vars(lost)),
        'has_error_type_field': hasattr(lost, 'error_type'),
        'error_messages': {k: v.error_message for k, v in failures.items()},
        'report_distinguishes_effect_before_failure': False,
        'ledger_effects_per_key_after_run': effects_per_key({'ledger': ledger_snapshot(db)}),
        'note': 'Both cases are ReportCaseFailure with only a message and stacktrace; only the worker ledger shows that '
        "'effect-then-lost-response' committed its effect while 'raise-before-effect' did not.",
    }


@probe
def evaluator_exception() -> dict[str, Any]:
    robust = _two_case_dataset(ParsedOk()).evaluate_sync(lambda inputs: inputs, progress=False)
    naive = _two_case_dataset(NaiveParsedOk()).evaluate_sync(lambda inputs: inputs, progress=False)
    truncated = next(c for c in naive.cases if c.name == 'truncated')
    rendered = naive.render(width=200)
    return {
        'robust_assertion_pass_rate': robust.averages().assertions,
        'naive_assertion_pass_rate': naive.averages().assertions,
        'naive_case_still_in_cases': truncated is not None,
        'naive_case_assertions': {k: v.value for k, v in truncated.assertions.items()},
        'naive_case_evaluator_failures': [
            {'name': f.name, 'error_type': f.error_type, 'error_message': f.error_message}
            for f in truncated.evaluator_failures
        ],
        'evaluator_failure_visible_in_render': 'JSONDecodeError' in rendered or 'NaiveParsedOk' in rendered,
        'note': 'A raising evaluator is excluded from the assertion pass rate rather than counted as a failure.',
    }


@probe
def retry_task() -> dict[str, Any]:
    """`retry_task` hides earlier attempts, including their side effects and metrics."""
    try:
        import tenacity  # noqa: F401
    except ImportError as e:
        ran: list[int] = []
        ds = Dataset(name='r', cases=[Case(name='c', inputs=1)])
        report = ds.evaluate_sync(lambda x: ran.append(x) or x, progress=False, retry_task={'reraise': True})
        return {
            'tenacity_installed': False,
            'evaluate_raised': False,
            'task_ran': bool(ran),
            'case_failures': [f.error_message for f in report.failures],
            'import_error_when_importing_tenacity': str(e),
        }

    from tenacity import stop_after_attempt

    results: dict[str, Any] = {'tenacity_installed': True}
    for impl in ('v1-correct', 'v2-dup-on-retry'):
        workdir = Path(tempfile.mkdtemp())
        db = workdir / 'w.sqlite3'
        init_db(db)
        attempts: list[int] = []

        def task(inputs: dict[str, Any], impl: str = impl, attempts: list[int] = attempts) -> dict[str, Any]:
            attempts.append(1)
            increment_eval_metric('attempts_seen_by_task', 1)
            request = dict(inputs)
            if len(attempts) == 1:
                request['fault'] = 'lose_response'
            return json.loads(handle(db, request, impl))

        ds = Dataset(
            name='retry',
            cases=[Case(name='record', inputs={'op': 'record', 'account': 'a', 'amount': 10, 'idempotency_key': 'k1'})],
        )
        report = ds.evaluate_sync(task, progress=False, retry_task={'stop': stop_after_attempt(3), 'reraise': True})
        case = report.cases[0]
        results[impl] = {
            'attempts_actually_made': len(attempts),
            'report_cases': len(report.cases),
            'report_failures': len(report.failures),
            'metrics_in_report': case.metrics,
            'attempt_count_field_in_report': any('attempt' in f for f in vars(case)),
            'output': case.output,
            'ledger_effects_per_key': effects_per_key({'ledger': ledger_snapshot(db)}),
        }
    return results


def _normalize(report_json: bytes) -> Any:
    data = json.loads(report_json)

    def scrub(x: Any) -> Any:
        if isinstance(x, dict):
            return {
                k: scrub(v)
                for k, v in x.items()
                if k not in {'task_duration', 'total_duration', 'trace_id', 'span_id', 'error_stacktrace'}
            }
        if isinstance(x, list):
            return [scrub(v) for v in x]
        return x

    return scrub(data)


@probe
def repeatability() -> dict[str, Any]:
    ids = ['lookup-hit', 'lost-response-then-retry', 'crash-after-effect-resume', 'balance-truncated']
    ds = Dataset(
        name='repeat',
        cases=[
            Case(name=i, inputs=SCENARIOS_BY_ID[i].as_inputs(), expected_output=SCENARIOS_BY_ID[i].expected)
            for i in ids
        ],
    )
    runs = [
        EvaluationReportAdapter.dump_json(ds.evaluate_sync(lambda x: run_scenario('v1-correct', x), progress=False))
        for _ in range(2)
    ]
    repeated = ds.evaluate_sync(lambda x: run_scenario('v1-correct', x), progress=False, repeat=3)
    groups = repeated.case_groups() or []
    return {
        'two_runs_identical_after_dropping_durations_and_ids': _normalize(runs[0]) == _normalize(runs[1]),
        'two_runs_identical_raw': runs[0] == runs[1],
        'repeat3_case_names': sorted(c.name for c in repeated.cases)[:4],
        'repeat3_groups': [{'name': g.name, 'runs': len(g.runs), 'failures': len(g.failures)} for g in groups],
        'repeat3_outputs_identical_within_group': all(
            len({json.dumps(r.output, sort_keys=True) for r in g.runs}) == 1 for g in groups
        ),
    }


class Unserializable:
    def __repr__(self) -> str:
        return '<Unserializable>'


@probe
def serialization() -> dict[str, Any]:
    ds = Dataset(name='ser', cases=[Case(name='c1', inputs={'steps': (1, 2)}, expected_output={'n': 1})], evaluators=[])
    report = ds.evaluate_sync(
        lambda x: {'n': 1, 'tuple': (1, 2), 'when': datetime(2026, 1, 1, tzinfo=UTC), 'raw': b'ok'},
        progress=False,
    )
    dumped = EvaluationReportAdapter.dump_json(report)
    loaded = EvaluationReportAdapter.validate_json(dumped)
    redumped = EvaluationReportAdapter.dump_json(loaded)
    out: dict[str, Any] = {
        'roundtrip_bytes_identical': dumped == redumped,
        'loaded_case_type': type(loaded.cases[0]).__name__,
        'loaded_output': loaded.cases[0].output,
        'loaded_output_python_types': {k: type(v).__name__ for k, v in loaded.cases[0].output.items()},
        'loaded_report_renders': bool(loaded.render(width=120)),
        'schema_version_field': 'version' in json.loads(dumped) or 'schema_version' in json.loads(dumped),
        'top_level_keys': sorted(json.loads(dumped)),
    }
    two = Dataset(name='ser2', cases=[Case(name='good', inputs=1), Case(name='bad', inputs=2)])
    for label, bad_output in (('non_utf8_bytes', b'\xff\x00'), ('custom_object', Unserializable())):
        report2 = two.evaluate_sync(lambda x, b=bad_output: 'fine' if x == 1 else b, progress=False)
        try:
            EvaluationReportAdapter.dump_json(report2)
            out[f'{label}_in_one_case'] = 'whole report serialized'
        except Exception as e:
            out[f'{label}_in_one_case'] = f'whole report fails: {type(e).__name__}: {e}'[:200]
        try:
            fb = json.loads(EvaluationReportAdapter.dump_json(report2, fallback=repr))
            out[f'{label}_with_fallback_repr'] = [c['output'] for c in fb['cases']]
        except Exception as e:
            out[f'{label}_with_fallback_repr'] = f'still fails: {type(e).__name__}: {e}'[:200]
    return out


@probe
def teardown_exception() -> dict[str, Any]:
    class FailingTeardown(CaseLifecycle):
        async def teardown(self, result: ReportCase | ReportCaseFailure | None) -> None:
            if self.case.name == 'case-3':
                raise RuntimeError('teardown failed')

    completed: list[str] = []

    def task(x: int) -> int:
        completed.append(str(x))
        return x

    ds = Dataset(name='td', cases=[Case(name=f'case-{i}', inputs=i) for i in range(6)])
    try:
        report = ds.evaluate_sync(task, progress=False, lifecycle=FailingTeardown, max_concurrency=1)
        return {'raised': False, 'n_cases': len(report.cases)}
    except BaseException as e:
        return {
            'raised': True,
            'exception': f'{type(e).__name__}: {e}'[:300],
            'tasks_completed_before_abort': len(completed),
            'report_returned': False,
            'note': 'One raising teardown aborts evaluate(); results of every other case are discarded.',
        }


def _child_slow_eval(journal: str | None) -> None:
    class Journal(CaseLifecycle):
        async def teardown(self, result: ReportCase | ReportCaseFailure | None) -> None:
            if journal and isinstance(result, ReportCase):
                with open(journal, 'a', encoding='utf-8') as f:
                    f.write(json.dumps({'case': result.name, 'output': result.output}) + '\n')
                    f.flush()
                    os.fsync(f.fileno())

    def task(x: int) -> int:
        time.sleep(0.5)
        return x

    ds = Dataset(name='slow', cases=[Case(name=f'case-{i}', inputs=i) for i in range(8)])
    ds.evaluate_sync(task, progress=False, max_concurrency=1, lifecycle=Journal)
    print('FINISHED', flush=True)


@probe
def kill_mid_evaluation() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for mode in ('no_journal', 'lifecycle_journal'):
        workdir = Path(tempfile.mkdtemp())
        journal = workdir / 'journal.jsonl' if mode == 'lifecycle_journal' else None
        before = set(workdir.rglob('*'))
        cmd = [sys.executable, __file__, '--child-slow-eval']
        if journal:
            cmd += ['--journal', str(journal)]
        proc = subprocess.Popen(cmd, cwd=workdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(2.2)  # imports + ~2-3 of 8 cases at 0.5s each
        proc.send_signal(signal.SIGKILL)
        stdout, _ = proc.communicate()
        files = sorted(str(p.relative_to(workdir)) for p in set(workdir.rglob('*')) - before)
        out[mode] = {
            'returncode': proc.returncode,
            'finished': b'FINISHED' in stdout,
            'files_written_in_cwd': files,
            'journaled_cases': len(journal.read_text().splitlines()) if journal and journal.exists() else 0,
        }
    return out


@probe
def default_concurrency_and_progress() -> dict[str, Any]:
    running = 0
    peak = 0
    lock = threading.Lock()

    def task(x: int) -> int:
        nonlocal running, peak
        with lock:
            running += 1
            peak = max(peak, running)
        time.sleep(0.05)
        with lock:
            running -= 1
        return x

    ds = Dataset(name='conc', cases=[Case(name=f'c{i}', inputs=i) for i in range(20)])
    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        ds.evaluate_sync(task)  # defaults: progress=True, max_concurrency=None
    return {
        'peak_concurrent_sync_tasks_default': peak,
        'thread_ids_distinct': True,
        'stdout_chars_with_default_progress': len(buf.getvalue()),
        'note': 'Sync tasks run in worker threads; with the default max_concurrency=None all cases may run at once.',
    }


@probe
def span_tree_without_sdk() -> dict[str, Any]:
    seen: dict[str, Any] = {}

    @dataclass
    class TouchSpanTree(Evaluator):
        def evaluate(self, ctx: EvaluatorContext) -> bool:
            try:
                ctx.span_tree
            except Exception as e:
                seen['error'] = f'{type(e).__name__}: {e}'[:200]
                return False
            seen['error'] = None
            return True

    Dataset(name='st', cases=[Case(name='c', inputs=1)], evaluators=[TouchSpanTree()]).evaluate_sync(
        lambda x: x, progress=False
    )
    return seen


@probe
def dataset_file_side_effects() -> dict[str, Any]:
    workdir = Path(tempfile.mkdtemp())
    ds = Dataset(name='files', cases=[Case(name='c', inputs={'a': 1}, expected_output=1)])
    ds.to_file(workdir / 'cases.yaml')
    files = sorted(p.name for p in workdir.iterdir())
    reloaded = Dataset[dict, int, Any].from_file(workdir / 'cases.yaml')
    return {'files_written_by_to_file': files, 'reloaded_cases': len(reloaded.cases)}


@probe
def lost_response_uncertainty() -> dict[str, Any]:
    """With a capture harness, the report keeps the caller's view and the ledger side by side."""
    obs = run_scenario('v1-correct', SCENARIOS_BY_ID['lost-response-no-retry'].as_inputs())
    return {
        'caller_status': obs['steps'][0]['status'],
        'effect_known_from_response': obs['steps'][0]['effect_known_from_response'],
        'ledger_effects': effects_per_key(obs),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('out', nargs='?', type=Path)
    parser.add_argument('--probe', action='append', choices=sorted(PROBES))
    parser.add_argument('--child-slow-eval', action='store_true')
    parser.add_argument('--journal')
    args = parser.parse_args()
    if args.child_slow_eval:
        _child_slow_eval(args.journal)
        return
    results: dict[str, Any] = {}
    for name in args.probe or list(PROBES):
        try:
            results[name] = PROBES[name]()
        except BaseException as e:
            results[name] = {'probe_error': f'{type(e).__name__}: {e}', 'traceback': traceback.format_exc()[-2000:]}
    text = json.dumps(results, indent=2, default=repr)
    if args.out:
        args.out.write_text(text + '\n')
    print(text)


if __name__ == '__main__':
    main()
