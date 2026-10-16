"""Re-evaluate recorded observations from a saved report, without re-running the worker.

Usage: python evals/reevaluate_recorded.py REPORT_JSON OUT_JSON

The task replays the recorded output for each case, so no side effect can happen during evaluation
(no retries, concurrency or teardown hazards). The original evaluators are re-applied to check that the
evaluation is repeatable from preserved evidence, and one *new* evaluator is applied to old evidence.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'worker'))

from evals_experiment import Inputs, Metadata, Observation, build_dataset  # noqa: E402
from pydantic_evals import Case, Dataset  # noqa: E402
from pydantic_evals.evaluators import EvaluationReason, Evaluator, EvaluatorContext  # noqa: E402


@dataclass
class OneReceiptPerKey(Evaluator[Inputs, Observation, Metadata]):
    """New evaluator, written after the original run: every idempotency key has exactly one receipt row."""

    def get_evaluator_version(self) -> str | None:
        return 'v1'

    def evaluate(self, ctx: EvaluatorContext[Inputs, Observation, Metadata]) -> EvaluationReason:
        rows: dict[str, int] = {}
        for effect in ctx.output['ledger']['effects']:
            rows[effect['idempotency_key']] = rows.get(effect['idempotency_key'], 0) + 1
        duplicated = {k: n for k, n in rows.items() if n > 1}
        return EvaluationReason(value=not duplicated, reason=f'duplicated receipts: {duplicated or "none"}')


def main() -> None:
    report = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    recorded: dict[str, Any] = {c['name']: c['output'] for c in report['cases']}
    original = {c['name']: {k: v['value'] for k, v in c['assertions'].items()} for c in report['cases']}
    evaluators = [*build_dataset().evaluators, OneReceiptPerKey()]
    dataset = Dataset[Inputs, Observation, Metadata](
        name=f'{report["dataset_name"]}-recorded',
        cases=[
            Case(name=c['name'], inputs=c['inputs'], expected_output=c['expected_output'], metadata=c['metadata'])
            for c in report['cases']
        ],
        evaluators=evaluators,
    )
    calls: list[str] = []

    def replay(inputs: Inputs) -> Observation:
        calls.append(inputs['id'])
        return recorded[inputs['id']]

    again = dataset.evaluate_sync(replay, name=f'{report["name"]} (recorded)', progress=False)
    reevaluated = {c.name: {k: v.value for k, v in c.assertions.items()} for c in again.cases}
    same = all({k: reevaluated[n][k] for k in original[n]} == original[n] for n in original)
    new_failures = sorted(n for n, a in reevaluated.items() if a.get('OneReceiptPerKey') is False)
    result = {
        'source_report': Path(sys.argv[1]).name,
        'worker_executed': False,
        'cases_replayed': len(calls),
        'original_assertions_reproduced_exactly': same,
        'new_evaluator': 'OneReceiptPerKey v1',
        'new_evaluator_failing_cases': new_failures,
    }
    Path(sys.argv[2]).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
