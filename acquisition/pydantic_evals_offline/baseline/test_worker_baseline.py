"""Control baseline: the synthetic worker evaluated with pytest and Hypothesis only.

Select the implementation under test with `WORKER_IMPL=<variant>`; see `run_discrimination.py`.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule
from scenarios import ALL_CHECKS, SCENARIOS, check_uncertainty_honest, effects_per_key, run_scenario
from synthetic_worker import (
    CRASH_POINTS,
    SEED_VALUES,
    ResponseLost,
    SimulatedCrash,
    WorkerError,
    handle,
    init_db,
    ledger_snapshot,
    run_pending,
    submit,
)

IMPL = os.environ.get('WORKER_IMPL', 'v1-correct')

# --- 1. The shared scenario catalog, as ordinary parametrized tests ----------------------------------


_observations: dict[tuple[str, str], dict[str, Any]] = {}


def _observe(impl: str, scenario: Any) -> dict[str, Any]:
    """Run each scenario once per implementation, however many checks look at it."""
    key = (impl, scenario.id)
    if key not in _observations:
        _observations[key] = run_scenario(impl, scenario.as_inputs())
    return _observations[key]


@pytest.mark.parametrize('check', list(ALL_CHECKS), ids=list(ALL_CHECKS))
@pytest.mark.parametrize('scenario', SCENARIOS, ids=[s.id for s in SCENARIOS])
def test_scenario(scenario: Any, check: str, impl: str) -> None:
    observation = _observe(impl, scenario)
    passed, reason = ALL_CHECKS[check](observation, scenario.expected)
    assert passed, reason
    honest, reason = check_uncertainty_honest(observation)
    assert honest, reason


# --- 2. Properties over generated inputs ------------------------------------------------------------


@pytest.fixture(scope='module')
def db() -> Any:
    workdir = Path(tempfile.mkdtemp(prefix='sw-baseline-'))
    path = workdir / 'w.sqlite3'
    init_db(path)
    yield path
    shutil.rmtree(workdir, ignore_errors=True)


@given(values=st.lists(st.integers(min_value=-(2**40), max_value=2**40), max_size=20))
def test_sum_matches_reference(db: Path, values: list[int]) -> None:
    import json

    assert json.loads(handle(db, {'op': 'sum', 'values': values}, IMPL)) == {'ok': True, 'value': sum(values)}


@given(key=st.text(min_size=1, max_size=12).filter(lambda k: k not in SEED_VALUES))
def test_lookup_missing_is_explicit(db: Path, key: str) -> None:
    import json

    assert json.loads(handle(db, {'op': 'lookup', 'key': key}, IMPL))['error'] == 'not_found'


# --- 3. Model-based state machine: retries, lost responses, crashes and resume ----------------------


class LedgerMachine(RuleBasedStateMachine):
    """Random interleavings of requests, injected faults, crashes and restarts vs. a simple model.

    The model only encodes the worker's *contract*: an effect is applied exactly once per idempotency
    key unless the request failed before the effect. It does not look at responses to decide whether
    an effect happened, so a lost response is never read as "no effect".
    """

    def __init__(self) -> None:
        super().__init__()
        self.workdir = Path(tempfile.mkdtemp(prefix='sw-machine-'))
        self.db = self.workdir / 'w.sqlite3'
        init_db(self.db)
        self.applied: dict[str, int] = {}  # key -> amount of the single expected effect
        self.next_job = 0

    def teardown(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)

    def _expect_effect(self, key: str, amount: int) -> None:
        self.applied.setdefault(key, amount)

    @rule(
        key=st.sampled_from(['k0', 'k1', 'k2']),
        amount=st.integers(1, 1000),
        fault=st.sampled_from([None, 'raise_before_effect', 'lose_response', 'truncate_output']),
    )
    def record(self, key: str, amount: int, fault: str | None) -> None:
        request: dict[str, Any] = {'op': 'record', 'account': 'acct', 'amount': amount, 'idempotency_key': key}
        if fault:
            request['fault'] = fault
        try:
            handle(self.db, request, IMPL)
        except WorkerError:
            return  # contract: nothing applied
        except ResponseLost:
            pass  # contract: applied (or deduplicated); the caller just doesn't know
        self._expect_effect(key, amount)

    @rule(key=st.sampled_from(['k0', 'k1', 'k2', 'k3']), crash_at=st.sampled_from([None, *CRASH_POINTS]))
    def job_with_crash_and_restart(self, key: str, crash_at: str | None) -> None:
        job_id = f'job-{self.next_job:04d}'
        self.next_job += 1
        submit(self.db, job_id, {'op': 'record', 'account': 'acct', 'amount': 5, 'idempotency_key': key})
        try:
            run_pending(self.db, IMPL, crash_at=crash_at, in_process=True)
        except SimulatedCrash:
            pass
        run_pending(self.db, IMPL)  # restart and resume
        self._expect_effect(key, 5)

    @precondition(lambda self: bool(self.applied))
    @rule()
    def retry_everything(self) -> None:
        for key, amount in list(self.applied.items()):
            handle(self.db, {'op': 'record', 'account': 'acct', 'amount': amount, 'idempotency_key': key}, IMPL)

    @invariant()
    def exactly_once(self) -> None:
        snapshot = ledger_snapshot(self.db)
        counts = effects_per_key({'ledger': snapshot})
        assert all(n == 1 for n in counts.values()), f'duplicate effects: {counts}'
        assert set(counts) == set(self.applied), f'ledger keys {sorted(counts)} vs model {sorted(self.applied)}'
        expected_balance = sum(self.applied.values())
        assert snapshot['balances'].get('acct', 0) == expected_balance
        assert all(job['status'] == 'done' for job in snapshot['jobs'])


TestLedgerMachine = LedgerMachine.TestCase
