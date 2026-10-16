"""Deterministic synthetic worker with a durable SQLite ledger.

This is the *system under evaluation* for comparing pytest + Hypothesis with Pydantic Evals.
It is synthetic and public: no network, no models, no private data.

The worker answers JSON requests with JSON text (as a tool or worker process would on a wire),
so that malformed or truncated output is representable. Side effects are rows in a SQLite
ledger, which is the worker's own durable execution record.

Operations:
- `lookup`: read a local value.
- `sum`: pure computation (lets broken variants return incorrect results).
- `record`: side-effecting write guarded by an idempotency key.
- `balance`: read-only report of an account (can be truncated by a fault).

Faults are injected per request via the `fault` field. They simulate the environment, not the
implementation, and are identical across implementation variants:
- `raise_before_effect`: raise before touching the database.
- `lose_response`: commit the effect, then raise `ResponseLost` instead of returning the result.
- `truncate_output`: return the first half of the serialized response.

Implementation variants (`IMPLEMENTATIONS`), one defect each, so an evaluation can be checked for
whether it rejects each defect:
- `v1-correct`: reference implementation.
- `v2-dup-on-retry`: re-applies the effect when a request is retried with the same idempotency key.
- `v3-wrong-sum`: `sum` treats negative values as positive.
- `v4-nonatomic-resume`: the job runner commits the effect and the job completion separately and
  does not dedupe, so a crash between the two commits duplicates the effect on resume.
- `v5-default-on-miss`: `lookup` of a missing key returns `0` instead of an error.
- `v6-int32-sum`: `sum` wraps like a signed 32-bit integer (only visible with large values).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import sqlite3
import sys
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Any

IMPLEMENTATIONS = (
    'v1-correct',
    'v2-dup-on-retry',
    'v3-wrong-sum',
    'v4-nonatomic-resume',
    'v5-default-on-miss',
    'v6-int32-sum',
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (
    key TEXT PRIMARY KEY,
    value INTEGER NOT NULL
);
-- Deliberately no UNIQUE constraint on idempotency_key: exactly-once is the worker's job,
-- and broken variants must be able to violate it so that evaluations can be shown to catch it.
CREATE TABLE IF NOT EXISTS effects (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    idempotency_key TEXT NOT NULL,
    account TEXT NOT NULL,
    amount INTEGER NOT NULL,
    receipt TEXT NOT NULL,
    worker_version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS results (
    idempotency_key TEXT PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    response TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    request TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'done')),
    response TEXT
);
"""

SEED_VALUES = {'alpha': 42, 'beta': -7}

# Crash points for the job runner. `SIGKILL` is used so no Python cleanup runs.
CRASH_POINTS = ('before_effect', 'after_effect', 'after_done')


class WorkerError(Exception):
    """The worker failed before applying any side effect."""


class ResponseLost(Exception):
    """The worker produced (and durably recorded) a result, but the caller never received it."""


class SimulatedCrash(BaseException):
    """In-process stand-in for process termination (used where spawning processes is too slow)."""


def connect(db_path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, isolation_level=None, timeout=30)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=FULL')
    if os.environ.get('SW_SQLITE_FULLFSYNC') == '1':
        # macOS only: `fsync()` does not flush the drive cache there; F_FULLFSYNC does. No-op elsewhere.
        conn.execute('PRAGMA fullfsync=ON')
        conn.execute('PRAGMA checkpoint_fullfsync=ON')
    return conn


def init_db(db_path: Path | str) -> None:
    with closing(connect(db_path)) as conn:
        conn.executescript(SCHEMA)
        conn.executemany('INSERT OR IGNORE INTO kv (key, value) VALUES (?, ?)', SEED_VALUES.items())


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    conn.execute('BEGIN IMMEDIATE')
    try:
        yield conn
    except BaseException:
        conn.execute('ROLLBACK')
        raise
    else:
        conn.execute('COMMIT')


def fingerprint(request: dict[str, Any]) -> str:
    """Hash of the semantically relevant request fields (fault injection excluded)."""
    relevant = {k: v for k, v in request.items() if k != 'fault'}
    return hashlib.sha256(json.dumps(relevant, sort_keys=True).encode()).hexdigest()


def receipt_for(idempotency_key: str) -> str:
    return 'r-' + hashlib.sha256(idempotency_key.encode()).hexdigest()[:12]


def _balance(conn: sqlite3.Connection, account: str) -> int:
    (total,) = conn.execute('SELECT COALESCE(SUM(amount), 0) FROM effects WHERE account = ?', (account,)).fetchone()
    return int(total)


def _wrap_int32(value: int) -> int:
    return (value + 2**31) % 2**32 - 2**31


def _apply_record(conn: sqlite3.Connection, impl: str, request: dict[str, Any]) -> str:
    """Apply a `record` request inside the caller's transaction and return the response text."""
    key = request['idempotency_key']
    account = request['account']
    amount = int(request['amount'])
    fp = fingerprint(request)

    if impl != 'v2-dup-on-retry':
        row = conn.execute('SELECT fingerprint, response FROM results WHERE idempotency_key = ?', (key,)).fetchone()
        if row is not None:
            stored_fp, stored_response = row
            if stored_fp != fp:
                return json.dumps({'ok': False, 'error': 'idempotency_conflict', 'idempotency_key': key})
            return stored_response

    receipt = receipt_for(key)
    conn.execute(
        'INSERT INTO effects (idempotency_key, account, amount, receipt, worker_version) VALUES (?, ?, ?, ?, ?)',
        (key, account, amount, receipt, impl),
    )
    response = json.dumps(
        {'ok': True, 'receipt': receipt, 'account': account, 'balance': _balance(conn, account)}, sort_keys=True
    )
    conn.execute(
        'INSERT OR REPLACE INTO results (idempotency_key, fingerprint, response) VALUES (?, ?, ?)',
        (key, fp, response),
    )
    return response


def handle(db_path: Path | str, request: dict[str, Any], impl: str = 'v1-correct') -> str:
    """Handle one request and return the response as JSON text.

    Raises:
        WorkerError: on `fault='raise_before_effect'` or an unknown operation (no effect applied).
        ResponseLost: on `fault='lose_response'`, after the result has been durably committed.
    """
    if impl not in IMPLEMENTATIONS:
        raise ValueError(f'unknown implementation {impl!r}')
    fault = request.get('fault')
    if fault == 'raise_before_effect':
        raise WorkerError(f'injected failure before effect for {request.get("op")!r}')

    op = request.get('op')
    with closing(connect(db_path)) as conn:
        if op == 'lookup':
            row = conn.execute('SELECT value FROM kv WHERE key = ?', (request['key'],)).fetchone()
            if row is None and impl == 'v5-default-on-miss':
                response = json.dumps({'ok': True, 'key': request['key'], 'value': 0}, sort_keys=True)
            elif row is None:
                response = json.dumps({'ok': False, 'error': 'not_found', 'key': request['key']}, sort_keys=True)
            else:
                response = json.dumps({'ok': True, 'key': request['key'], 'value': row[0]}, sort_keys=True)
        elif op == 'sum':
            values = [int(v) for v in request['values']]
            if impl == 'v3-wrong-sum':
                total = sum(abs(v) for v in values)
            elif impl == 'v6-int32-sum':
                total = _wrap_int32(sum(values))
            else:
                total = sum(values)
            response = json.dumps({'ok': True, 'value': total}, sort_keys=True)
        elif op == 'record':
            with transaction(conn):
                response = _apply_record(conn, impl, request)
        elif op == 'balance':
            account = request['account']
            history = conn.execute(
                'SELECT idempotency_key, amount, receipt FROM effects WHERE account = ? ORDER BY seq', (account,)
            ).fetchall()
            response = json.dumps(
                {
                    'ok': True,
                    'account': account,
                    'balance': _balance(conn, account),
                    'history': [{'idempotency_key': k, 'amount': a, 'receipt': r} for k, a, r in history],
                },
                sort_keys=True,
            )
        else:
            raise WorkerError(f'unknown op {op!r}')

    if fault == 'lose_response':
        raise ResponseLost(f'result for {op!r} was produced and committed but not delivered')
    if fault == 'truncate_output':
        return response[: len(response) // 2]
    return response


# --- Durable job queue: submit, run, crash, resume --------------------------------------------------


def submit(db_path: Path | str, job_id: str, request: dict[str, Any]) -> None:
    with closing(connect(db_path)) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO jobs (job_id, request, status) VALUES (?, ?, 'pending')",
            (job_id, json.dumps(request, sort_keys=True)),
        )


def _crash(crash_at: str | None, point: str, *, in_process: bool) -> None:
    if crash_at != point:
        return
    if in_process:
        raise SimulatedCrash(point)
    os.kill(os.getpid(), signal.SIGKILL)  # pragma: no cover - the process ends here


def run_pending(
    db_path: Path | str,
    impl: str = 'v1-correct',
    *,
    crash_at: str | None = None,
    in_process: bool = False,
) -> list[str]:
    """Run all pending jobs in `job_id` order and return the ids completed by this call.

    `crash_at` terminates the run at a crash point of the first pending job: by `SIGKILL`
    (`in_process=False`, the real thing) or by raising `SimulatedCrash` (`in_process=True`).
    """
    completed: list[str] = []
    with closing(connect(db_path)) as conn:
        pending = conn.execute("SELECT job_id, request FROM jobs WHERE status = 'pending' ORDER BY job_id").fetchall()
        for job_id, request_text in pending:
            request = json.loads(request_text)
            _crash(crash_at, 'before_effect', in_process=in_process)
            if impl == 'v4-nonatomic-resume':
                # Defect: effect committed on its own, without consulting `results`, and the job is
                # marked done in a second transaction.
                with transaction(conn):
                    receipt = receipt_for(request['idempotency_key'])
                    conn.execute(
                        'INSERT INTO effects (idempotency_key, account, amount, receipt, worker_version)'
                        ' VALUES (?, ?, ?, ?, ?)',
                        (request['idempotency_key'], request['account'], int(request['amount']), receipt, impl),
                    )
                    response = json.dumps(
                        {
                            'ok': True,
                            'receipt': receipt,
                            'account': request['account'],
                            'balance': _balance(conn, request['account']),
                        },
                        sort_keys=True,
                    )
                _crash(crash_at, 'after_effect', in_process=in_process)
                with transaction(conn):
                    conn.execute("UPDATE jobs SET status = 'done', response = ? WHERE job_id = ?", (response, job_id))
            else:
                with transaction(conn):
                    response = _apply_record(conn, impl, request)
                    conn.execute("UPDATE jobs SET status = 'done', response = ? WHERE job_id = ?", (response, job_id))
                _crash(crash_at, 'after_effect', in_process=in_process)
            completed.append(job_id)
            _crash(crash_at, 'after_done', in_process=in_process)
            crash_at = None  # only the first pending job is crash-injected
    return completed


def ledger_snapshot(db_path: Path | str) -> dict[str, Any]:
    """Read the worker's durable record. This, not the caller's view, is the evidence of effects."""
    with closing(connect(db_path)) as conn:
        effects = [
            {'seq': s, 'idempotency_key': k, 'account': a, 'amount': m, 'receipt': r, 'worker_version': v}
            for s, k, a, m, r, v in conn.execute(
                'SELECT seq, idempotency_key, account, amount, receipt, worker_version FROM effects ORDER BY seq'
            )
        ]
        jobs = [
            {'job_id': j, 'status': s, 'response': r}
            for j, s, r in conn.execute('SELECT job_id, status, response FROM jobs ORDER BY job_id')
        ]
        results = dict(conn.execute('SELECT idempotency_key, response FROM results ORDER BY idempotency_key'))
    balances: dict[str, int] = {}
    for effect in effects:
        balances[effect['account']] = balances.get(effect['account'], 0) + effect['amount']
    return {'effects': effects, 'jobs': jobs, 'results': results, 'balances': balances}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Synthetic worker job runner (for crash/resume scenarios).')
    parser.add_argument('command', choices=['run-pending'])
    parser.add_argument('--db', required=True)
    parser.add_argument('--impl', default='v1-correct', choices=IMPLEMENTATIONS)
    parser.add_argument('--crash-at', choices=CRASH_POINTS)
    args = parser.parse_args(argv)
    completed = run_pending(args.db, args.impl, crash_at=args.crash_at)
    sys.stdout.write(json.dumps({'completed': completed}) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
