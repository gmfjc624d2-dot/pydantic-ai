"""Shared scenario catalog and scenario runner.

Both the pytest/Hypothesis baseline and the Pydantic Evals experiment consume the *same* scenarios
and the *same* runner, so that the comparison is about what each harness can express and report,
not about two different sets of checks drifting apart.

The runner returns an `Observation`: a JSON-serializable record of what the caller saw (per step)
plus a snapshot of the worker's durable ledger. The two are deliberately kept separate:
a missing response is recorded as `effect_known_from_response = False`, never as "no effect".
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from synthetic_worker import ResponseLost, WorkerError, handle, init_db, ledger_snapshot, submit

WORKER_MODULE = Path(__file__).with_name('synthetic_worker.py')


@dataclass(frozen=True)
class Scenario:
    id: str
    description: str
    steps: list[dict[str, Any]]
    expected: dict[str, Any]
    catches: list[str] = field(default_factory=list[str])
    """Implementation variants this scenario is designed to reject."""

    def as_inputs(self) -> dict[str, Any]:
        return {'id': self.id, 'steps': self.steps}


def _record(key: str, amount: int, account: str = 'acct-1', fault: str | None = None) -> dict[str, Any]:
    request: dict[str, Any] = {'op': 'record', 'account': account, 'amount': amount, 'idempotency_key': key}
    if fault:
        request['fault'] = fault
    return {'kind': 'call', 'request': request}


def _call(fault: str | None = None, **request: Any) -> dict[str, Any]:
    if fault:
        request['fault'] = fault
    return {'kind': 'call', 'request': request}


SCENARIOS: list[Scenario] = [
    Scenario(
        id='lookup-hit',
        description='Lookup of a seeded local value returns it.',
        steps=[_call(op='lookup', key='alpha')],
        expected={'statuses': ['ok'], 'responses': {'0': {'ok': True, 'value': 42}}},
    ),
    Scenario(
        id='lookup-miss',
        description='Lookup of a missing key is an explicit error, not a default value.',
        steps=[_call(op='lookup', key='gamma')],
        expected={'statuses': ['rejected'], 'responses': {'0': {'ok': False, 'error': 'not_found'}}},
        catches=['v5-default-on-miss'],
    ),
    Scenario(
        id='sum-correct',
        description='Pure computation returns the correct result.',
        steps=[_call(op='sum', values=[1, 2, 3])],
        expected={'statuses': ['ok'], 'responses': {'0': {'value': 6}}},
    ),
    Scenario(
        id='sum-mixed-sign',
        description='Pure computation with negative values.',
        steps=[_call(op='sum', values=[5, -3])],
        expected={'statuses': ['ok'], 'responses': {'0': {'value': 2}}},
        catches=['v3-wrong-sum'],
    ),
    Scenario(
        id='balance-truncated',
        description='Malformed (truncated) output must be classified as malformed, not as success.',
        steps=[_record('k-1', 100), _call(op='balance', account='acct-1', fault='truncate_output')],
        expected={'statuses': ['ok', 'malformed'], 'effects_per_key': {'k-1': 1}},
    ),
    Scenario(
        id='raise-before-effect-then-retry',
        description='A failure before the effect leaves no effect; the retry applies it exactly once.',
        steps=[_record('k-1', 100, fault='raise_before_effect'), _record('k-1', 100)],
        expected={
            'statuses': ['raised', 'ok'],
            'effects_per_key': {'k-1': 1},
            'balances': {'acct-1': 100},
        },
    ),
    Scenario(
        id='lost-response-no-retry',
        description='The effect is committed but the response is lost; the ledger, not the caller, knows.',
        steps=[_record('k-1', 100, fault='lose_response')],
        expected={'statuses': ['no_response'], 'effects_per_key': {'k-1': 1}, 'balances': {'acct-1': 100}},
    ),
    Scenario(
        id='lost-response-then-retry',
        description='Retrying a lost response with the same key returns the original result, no new effect.',
        steps=[_record('k-1', 100, fault='lose_response'), _record('k-1', 100)],
        expected={
            'statuses': ['no_response', 'ok'],
            'effects_per_key': {'k-1': 1},
            'balances': {'acct-1': 100},
            'receipt_from_ledger_matches_step': 1,
        },
        catches=['v2-dup-on-retry'],
    ),
    Scenario(
        id='duplicate-after-success',
        description='A duplicate of a successful request returns the same receipt and applies nothing.',
        steps=[_record('k-1', 100), _record('k-1', 100)],
        expected={
            'statuses': ['ok', 'ok'],
            'effects_per_key': {'k-1': 1},
            'balances': {'acct-1': 100},
            'same_receipt_steps': [0, 1],
        },
        catches=['v2-dup-on-retry'],
    ),
    Scenario(
        id='key-reuse-different-payload',
        description='Reusing an idempotency key with a different payload is rejected without effect.',
        steps=[_record('k-1', 100), _record('k-1', 999)],
        expected={
            'statuses': ['ok', 'rejected'],
            'responses': {'1': {'ok': False, 'error': 'idempotency_conflict'}},
            'effects_per_key': {'k-1': 1},
            'balances': {'acct-1': 100},
        },
        catches=['v2-dup-on-retry'],
    ),
    Scenario(
        id='distinct-keys',
        description='Distinct idempotency keys are distinct effects (guards against over-deduplication).',
        steps=[_record('k-1', 100), _record('k-2', 100)],
        expected={'statuses': ['ok', 'ok'], 'effects_per_key': {'k-1': 1, 'k-2': 1}, 'balances': {'acct-1': 200}},
    ),
    Scenario(
        id='crash-before-effect-resume',
        description='SIGKILL before the effect; restart resumes the job and applies it exactly once.',
        steps=[
            {'kind': 'submit', 'job_id': 'job-1', 'request': _record('k-1', 100)['request']},
            {'kind': 'run_process', 'crash_at': 'before_effect'},
            {'kind': 'run_process', 'crash_at': None},
        ],
        expected={
            'statuses': ['submitted', 'terminated', 'ok'],
            'effects_per_key': {'k-1': 1},
            'jobs_done': ['job-1'],
        },
    ),
    Scenario(
        id='crash-after-effect-resume',
        description='SIGKILL after the effect commit; restart must not apply the effect again.',
        steps=[
            {'kind': 'submit', 'job_id': 'job-1', 'request': _record('k-1', 100)['request']},
            {'kind': 'run_process', 'crash_at': 'after_effect'},
            {'kind': 'run_process', 'crash_at': None},
        ],
        expected={
            'statuses': ['submitted', 'terminated', 'ok'],
            'effects_per_key': {'k-1': 1},
            'jobs_done': ['job-1'],
            'balances': {'acct-1': 100},
        },
        catches=['v4-nonatomic-resume'],
    ),
]

SCENARIOS_BY_ID = {s.id: s for s in SCENARIOS}


def _classify_call(db_path: Path, request: dict[str, Any], impl: str) -> dict[str, Any]:
    """Call the worker once and record exactly what the caller observed."""
    step: dict[str, Any] = {'kind': 'call', 'request': request}
    try:
        text = handle(db_path, request, impl)
    except WorkerError as e:
        # The worker's contract says this is raised before any effect; the caller still only
        # *believes* that -- the ledger is what confirms it.
        step.update(status='raised', error=f'{type(e).__name__}: {e}', response_text=None)
        step['effect_known_from_response'] = False
        return step
    except ResponseLost as e:
        step.update(status='no_response', error=f'{type(e).__name__}: {e}', response_text=None)
        step['effect_known_from_response'] = False
        return step
    step['response_text'] = text
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        step.update(status='malformed', error=f'JSONDecodeError: {e}', parsed=None)
        step['effect_known_from_response'] = False
        return step
    step['parsed'] = parsed
    step['status'] = 'ok' if parsed.get('ok') else 'rejected'
    step['effect_known_from_response'] = True
    return step


def _run_process(db_path: Path, impl: str, crash_at: str | None) -> dict[str, Any]:
    cmd = [sys.executable, str(WORKER_MODULE), 'run-pending', '--db', str(db_path), '--impl', impl]
    if crash_at:
        cmd += ['--crash-at', crash_at]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env={**os.environ, 'PYTHONPATH': ''})
    step: dict[str, Any] = {'kind': 'run_process', 'crash_at': crash_at, 'returncode': proc.returncode}
    if proc.returncode == 0:
        step['status'] = 'ok'
        step['parsed'] = json.loads(proc.stdout)
        step['effect_known_from_response'] = True
    elif proc.returncode == -9:
        step['status'] = 'terminated'
        step['effect_known_from_response'] = False
    else:
        step['status'] = 'error'
        step['error'] = proc.stderr[-2000:]
        step['effect_known_from_response'] = False
    return step


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_scenario(impl: str, scenario: dict[str, Any], evidence_dir: Path | None = None) -> dict[str, Any]:
    """Run one scenario against a fresh database and return the observation.

    If `evidence_dir` is given, the SQLite database is preserved there (one file per scenario and
    implementation) and its SHA-256 is recorded, so the original evidence outlives the report.
    """
    workdir = Path(tempfile.mkdtemp(prefix=f'sw-{scenario["id"]}-'))
    db_path = workdir / 'worker.sqlite3'
    try:
        init_db(db_path)
        steps: list[dict[str, Any]] = []
        for step in scenario['steps']:
            if step['kind'] == 'call':
                steps.append(_classify_call(db_path, step['request'], impl))
            elif step['kind'] == 'submit':
                submit(db_path, step['job_id'], step['request'])
                steps.append({'kind': 'submit', 'status': 'submitted', 'job_id': step['job_id']})
            elif step['kind'] == 'run_process':
                steps.append(_run_process(db_path, impl, step['crash_at']))
            else:
                raise ValueError(f'unknown step kind {step["kind"]!r}')
        ledger = ledger_snapshot(db_path)
        observation: dict[str, Any] = {
            'scenario_id': scenario['id'],
            'worker_version': impl,
            'steps': steps,
            'ledger': ledger,
        }
        if evidence_dir is not None:
            evidence_dir.mkdir(parents=True, exist_ok=True)
            # Checkpoint WAL into the main file so the preserved copy is self-contained.
            import sqlite3

            with sqlite3.connect(db_path) as conn:
                conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            kept = evidence_dir / f'{scenario["id"]}--{impl}.sqlite3'
            shutil.copy2(db_path, kept)
            observation['evidence'] = {'ledger_db': kept.name, 'ledger_db_sha256': sha256_file(kept)}
        return observation
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# --- Checks shared by both harnesses ----------------------------------------------------------------
# Each check returns (passed, reason). The pytest baseline asserts on them; the Pydantic Evals
# evaluators wrap them. Keeping one implementation avoids comparing two different oracles.


def effects_per_key(observation: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for effect in observation['ledger']['effects']:
        counts[effect['idempotency_key']] = counts.get(effect['idempotency_key'], 0) + 1
    return counts


def check_statuses(observation: dict[str, Any], expected: dict[str, Any]) -> tuple[bool, str]:
    actual = [s['status'] for s in observation['steps']]
    return actual == expected['statuses'], f'statuses={actual} expected={expected["statuses"]}'


def check_responses(observation: dict[str, Any], expected: dict[str, Any]) -> tuple[bool, str]:
    for index, subset in expected.get('responses', {}).items():
        parsed = observation['steps'][int(index)].get('parsed') or {}
        mismatched = {k: parsed.get(k) for k, v in subset.items() if parsed.get(k) != v}
        if mismatched:
            return False, f'step {index}: expected {subset}, got {mismatched}'
    return True, 'responses match'


def check_exactly_once(observation: dict[str, Any], expected: dict[str, Any]) -> tuple[bool, str]:
    if 'effects_per_key' not in expected:
        return True, 'no effect expectation'
    actual = effects_per_key(observation)
    return actual == expected['effects_per_key'], f'effects_per_key={actual} expected={expected["effects_per_key"]}'


def check_balances(observation: dict[str, Any], expected: dict[str, Any]) -> tuple[bool, str]:
    if 'balances' not in expected:
        return True, 'no balance expectation'
    actual = observation['ledger']['balances']
    return actual == expected['balances'], f'balances={actual} expected={expected["balances"]}'


def check_receipts(observation: dict[str, Any], expected: dict[str, Any]) -> tuple[bool, str]:
    steps = observation['steps']
    if pair := expected.get('same_receipt_steps'):
        receipts = [(steps[i].get('parsed') or {}).get('receipt') for i in pair]
        if len(set(receipts)) != 1 or receipts[0] is None:
            return False, f'receipts differ across retries: {receipts}'
    if (index := expected.get('receipt_from_ledger_matches_step')) is not None:
        ledger_receipts = {e['receipt'] for e in observation['ledger']['effects']}
        got = (steps[index].get('parsed') or {}).get('receipt')
        if got not in ledger_receipts or len(ledger_receipts) != 1:
            return False, f'retry receipt {got!r} vs ledger receipts {sorted(ledger_receipts)}'
    return True, 'receipts consistent'


def check_jobs(observation: dict[str, Any], expected: dict[str, Any]) -> tuple[bool, str]:
    if 'jobs_done' not in expected:
        return True, 'no job expectation'
    done = [j['job_id'] for j in observation['ledger']['jobs'] if j['status'] == 'done']
    return done == expected['jobs_done'], f'jobs_done={done} expected={expected["jobs_done"]}'


def check_uncertainty_honest(observation: dict[str, Any]) -> tuple[bool, str]:
    """A step without a usable response must not be treated as evidence of 'no effect'."""
    for i, step in enumerate(observation['steps']):
        if step['status'] in {'no_response', 'malformed', 'terminated', 'raised'} and step.get(
            'effect_known_from_response'
        ):
            return False, f'step {i} ({step["status"]}) claims the effect is known from its response'
    return True, 'missing responses are not treated as proof of no effect'


ALL_CHECKS = {
    'statuses': check_statuses,
    'responses': check_responses,
    'exactly_once': check_exactly_once,
    'balances': check_balances,
    'receipts': check_receipts,
    'jobs': check_jobs,
}


def as_jsonable(scenario: Scenario) -> dict[str, Any]:
    return asdict(scenario)
