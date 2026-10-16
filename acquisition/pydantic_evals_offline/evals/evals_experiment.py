"""The same scenarios as the pytest/Hypothesis baseline, evaluated with Pydantic Evals.

Usage: python evals/evals_experiment.py OUT_DIR [--impl IMPL ...] [--generated N]

Writes, per implementation: the report as JSON (`EvaluationReportAdapter`), the rendered table
(alone and diffed against `v1-correct`), and the preserved SQLite ledgers. Writes a discrimination
summary (`discrimination.json`) listing which cases each implementation failed.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'worker'))

from envinfo import content_hash, environment
from scenarios import ALL_CHECKS, SCENARIOS, check_uncertainty_honest, effects_per_key, run_scenario
from synthetic_worker import IMPLEMENTATIONS

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import EvaluationReason, Evaluator, EvaluatorContext
from pydantic_evals.reporting import EvaluationReport, EvaluationReportAdapter

REPO = Path(__file__).resolve().parents[3]

Inputs = dict[str, Any]
Observation = dict[str, Any]
Expected = dict[str, Any]
Metadata = dict[str, Any]


@dataclass
class ScenarioCheck(Evaluator[Inputs, Observation, Metadata]):
    """Wraps one of the shared checks as an assertion with a reason."""

    check: str

    def get_default_evaluation_name(self) -> str:
        return self.check

    def get_evaluator_version(self) -> str | None:
        return 'v1'

    def evaluate(self, ctx: EvaluatorContext[Inputs, Observation, Metadata]) -> EvaluationReason:
        assert ctx.expected_output is not None
        passed, reason = ALL_CHECKS[self.check](ctx.output, ctx.expected_output)
        return EvaluationReason(value=passed, reason=reason)


@dataclass
class UncertaintyHonest(Evaluator[Inputs, Observation, Metadata]):
    def evaluate(self, ctx: EvaluatorContext[Inputs, Observation, Metadata]) -> EvaluationReason:
        passed, reason = check_uncertainty_honest(ctx.output)
        return EvaluationReason(value=passed, reason=reason)


@dataclass
class LedgerFacts(Evaluator[Inputs, Observation, Metadata]):
    """Non-assertion outputs: a score (effects observed in the ledger) and a label (last caller view)."""

    def evaluate(self, ctx: EvaluatorContext[Inputs, Observation, Metadata]) -> dict[str, int | str]:
        return {
            'ledger_effects': sum(effects_per_key(ctx.output).values()),
            'last_step_status': ctx.output['steps'][-1]['status'],
        }


@dataclass
class SumMatchesReference(Evaluator[Inputs, Observation, Metadata]):
    """Evaluator for generated `sum` cases (no expected_output needed: the oracle is Python's `sum`)."""

    def evaluate(self, ctx: EvaluatorContext[Inputs, Observation, Metadata]) -> EvaluationReason:
        values = ctx.inputs['steps'][0]['request']['values']
        got = (ctx.output['steps'][0].get('parsed') or {}).get('value')
        return EvaluationReason(value=got == sum(values), reason=f'got={got} expected={sum(values)}')


def build_dataset() -> Dataset[Inputs, Observation, Metadata]:
    cases = [
        Case(
            name=s.id,
            inputs=s.as_inputs(),
            expected_output=s.expected,
            metadata={'description': s.description, 'catches': s.catches},
        )
        for s in SCENARIOS
    ]
    evaluators: list[Evaluator[Inputs, Observation, Metadata]] = [ScenarioCheck(check) for check in ALL_CHECKS]
    evaluators += [UncertaintyHonest(), LedgerFacts()]
    return Dataset[Inputs, Observation, Metadata](name='synthetic-worker', cases=cases, evaluators=evaluators)


def build_generated_dataset(n: int, seed: int = 20261016) -> Dataset[Inputs, Observation, Metadata]:
    """Seeded random `sum` cases: what 'generative' evaluation looks like without Hypothesis."""
    rng = random.Random(seed)
    cases = []
    for i in range(n):
        values = [rng.randint(-(2**40), 2**40) for _ in range(rng.randint(0, 5))]
        steps = [{'kind': 'call', 'request': {'op': 'sum', 'values': values}}]
        cases.append(Case(name=f'gen-sum-{i:03d}', inputs={'id': f'gen-sum-{i:03d}', 'steps': steps}))
    return Dataset[Inputs, Observation, Metadata](
        name='synthetic-worker-generated', cases=cases, evaluators=[SumMatchesReference()]
    )


def failing_cases(report: EvaluationReport[Any, Any, Any]) -> dict[str, list[str]]:
    failing: dict[str, list[str]] = {}
    for case in report.cases:
        bad = [name for name, result in case.assertions.items() if result.value is not True]
        bad += [f'evaluator_failure:{f.name}' for f in case.evaluator_failures]
        if bad:
            failing[case.name] = bad
    for failure in report.failures:
        failing[failure.name] = [f'task_failure:{failure.error_message}']
    return failing


def run(out_dir: Path, impls: list[str], generated: int) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    dataset = build_dataset()
    env = environment(REPO)
    dataset_digest = content_hash([c.inputs for c in dataset.cases] + [c.expected_output for c in dataset.cases])
    (out_dir / 'environment.json').write_text(json.dumps(env, indent=2) + '\n')

    reports: dict[str, EvaluationReport[Any, Any, Any]] = {}
    for impl in impls:
        evidence_dir = out_dir / 'ledgers'

        def task(inputs: Inputs, impl: str = impl) -> Observation:
            return run_scenario(impl, inputs, evidence_dir)

        report = dataset.evaluate_sync(
            task,
            name=impl,
            task_name='run_scenario',
            max_concurrency=4,
            progress=False,
            metadata={'worker_version': impl, 'dataset_digest': dataset_digest, 'environment': env},
        )
        reports[impl] = report
        (out_dir / f'report--{impl}.json').write_bytes(EvaluationReportAdapter.dump_json(report, indent=2) + b'\n')
        rendered = report.render(width=220, include_reasons=False)
        (out_dir / f'report--{impl}.txt').write_text(rendered)

    if 'v1-correct' in reports:
        for impl, report in reports.items():
            if impl == 'v1-correct':
                continue
            diff = report.render(width=220, baseline=reports['v1-correct'])
            (out_dir / f'diff--v1-correct--{impl}.txt').write_text(diff)

    summary: dict[str, Any] = {'dataset_digest': dataset_digest, 'implementations': {}}
    for impl, report in reports.items():
        failing = failing_cases(report)
        expected_to_fail = sorted(s.id for s in SCENARIOS if impl in s.catches)
        averages = report.averages()
        summary['implementations'][impl] = {
            'rejected': bool(failing),
            'failing_cases': failing,
            'designed_to_be_caught_by': expected_to_fail,
            'caught_exactly_as_designed': sorted(failing) == expected_to_fail,
            'assertion_pass_rate': averages.assertions if averages else None,
        }

    if generated:
        gen = build_generated_dataset(generated)
        for impl in impls:
            if impl not in {'v1-correct', 'v3-wrong-sum', 'v6-int32-sum'}:
                continue
            report = gen.evaluate_sync(
                lambda inputs, impl=impl: run_scenario(impl, inputs),
                name=f'{impl}-generated',
                max_concurrency=4,
                progress=False,
            )
            failing = failing_cases(report)
            first = next(iter(failing), None)
            summary['implementations'].setdefault(impl, {})['generated_sum_cases'] = {
                'n': generated,
                'failing': len(failing),
                'first_failing_case': first,
                'first_failing_inputs': next(
                    (c.inputs['steps'][0]['request']['values'] for c in report.cases if c.name == first), None
                ),
            }

    (out_dir / 'discrimination.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('out_dir', type=Path)
    parser.add_argument('--impl', action='append', choices=IMPLEMENTATIONS)
    parser.add_argument('--generated', type=int, default=100)
    args = parser.parse_args()
    summary = run(args.out_dir, args.impl or list(IMPLEMENTATIONS), args.generated)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
