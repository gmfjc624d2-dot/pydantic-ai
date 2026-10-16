"""Convert a saved Pydantic Evals report plus the worker's preserved ledgers into neutral evidence records.

Usage:
    python neutral/to_neutral.py REPORT_JSON --ledgers DIR [--inline] > records.jsonl
    python neutral/to_neutral.py --write-schema neutral/evidence-record.v0.schema.json

Design rules (see ../REPORT.md, "Reports and portability"):
- Evaluator outcomes reuse the OpenTelemetry GenAI evaluation attribute names that pydantic-evals
  already emits for online evaluation (`gen_ai.evaluation.*`, `error.type`), with the same
  bool -> score.value 1.0/0.0 + score.label pass/fail mapping. No new scoring vocabulary.
- Nothing the framework did not observe is filled in. Unobserved facts are `null` with a
  provenance entry saying so (e.g. attempt counts, run start time).
- Side effects come only from the worker's durable ledger (SQLite, re-read and hashed here), never
  from the caller's view. A missing response is recorded as "effect unknown from response".
- Inputs and outputs are content-addressed (`sha256:`); inlining them is opt-in.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_ID = 'evidence-record/v0'


class _Model(BaseModel):
    model_config = ConfigDict(extra='forbid', populate_by_name=True)


class ContentRef(_Model):
    sha256: str
    inline: Any = None


class CaseIdentity(_Model):
    id: str
    source_case_id: str | None = Field(description='Case name before repetition indexing (`repeat > 1`).')
    dataset: str | None
    dataset_digest: str | None = Field(description='Supplied by the harness via experiment metadata.')


class RunIdentity(_Model):
    name: str
    framework: Literal['pydantic-evals']
    framework_version: str | None
    trace_id: str | None = Field(description='Only present when an OpenTelemetry tracer provider was configured.')
    span_id: str | None
    started_at: None = Field(default=None, description='Not recorded by pydantic-evals reports.')


class Attempt(_Model):
    index: int | None
    count: int | None
    repetition_index: int | None = Field(description='From `repeat=N`; a repetition is not a retry.')
    repetition_of: int | None


class WorkerIdentity(_Model):
    version: str | None


class ErrorInfo(_Model):
    message: str
    type: str | None
    type_derived_from_message: bool
    stacktrace_sha256: str | None


class Output(_Model):
    status: Literal['returned', 'task_raised']
    ref: ContentRef | None
    error: ErrorInfo | None


class Evaluation(_Model):
    kind: Literal['assertion', 'score', 'label', 'evaluator_error']
    name: str = Field(alias='gen_ai.evaluation.name')
    score_value: float | None = Field(default=None, alias='gen_ai.evaluation.score.value')
    score_label: str | None = Field(default=None, alias='gen_ai.evaluation.score.label')
    explanation: str | None = Field(default=None, alias='gen_ai.evaluation.explanation')
    error_type: str | None = Field(default=None, alias='error.type')
    evaluator_source: str = Field(alias='gen_ai.evaluation.evaluator.source')
    evaluator_version: str | None = Field(default=None, alias='gen_ai.evaluation.evaluator.version')


class Effect(_Model):
    seq: int
    idempotency_key: str
    account: str
    amount: int
    receipt: str
    worker_version: str


class EffectsObserved(_Model):
    status: Literal['observed']
    source: Literal['worker_ledger']
    ledger_file: str
    ledger_sha256: str
    integrity: Literal['ledger_matches_report_snapshot', 'ledger_differs_from_report_snapshot', 'no_report_snapshot']
    effects: list[Effect]
    effects_per_idempotency_key: dict[str, int]


class EffectsNotObserved(_Model):
    status: Literal['not_observed']
    reason: str


class StepUncertainty(_Model):
    step: int
    caller_status: str
    effect_known_from_response: bool
    idempotency_key: str | None
    ledger_effects_for_key_at_scenario_end: int | None = Field(
        description='From the ledger after the whole scenario, not at the time of the step; null if no ledger.'
    )


class Timing(_Model):
    task_duration_s: float | None
    total_duration_s: float | None


class EvidenceRecord(_Model):
    schema_id: Literal['evidence-record/v0'] = Field(alias='schema')
    record_id: str
    case: CaseIdentity
    run: RunIdentity
    attempt: Attempt
    worker: WorkerIdentity
    environment: dict[str, Any] | None
    input: ContentRef
    output: Output
    evaluations: list[Evaluation]
    effects: EffectsObserved | EffectsNotObserved = Field(discriminator='status')
    uncertainty: list[StepUncertainty]
    retry_identity: list[str] = Field(description='Idempotency keys used by the case, from its inputs.')
    timing: Timing
    provenance: dict[str, str]
    converted_at: str
    converter: str


def sha256_json(value: Any) -> str:
    return 'sha256:' + hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _ref(value: Any, inline: bool) -> ContentRef:
    return ContentRef(sha256=sha256_json(value), inline=value if inline else None)


def _evaluation(kind: str, result: dict[str, Any]) -> Evaluation:
    value = result['value']
    fields: dict[str, Any] = {}
    if isinstance(value, bool):
        fields = {'score_value': 1.0 if value else 0.0, 'score_label': 'pass' if value else 'fail'}
    elif isinstance(value, int | float):
        fields = {'score_value': float(value)}
    else:
        fields = {'score_label': value}
    return Evaluation(
        kind=kind,  # type: ignore[arg-type]
        name=result['name'],
        explanation=result.get('reason'),
        evaluator_source=json.dumps(result['source'], sort_keys=True),
        evaluator_version=result.get('evaluator_version'),
        **fields,
    )


def _read_ledger(path: Path) -> list[dict[str, Any]]:
    with closing(sqlite3.connect(f'file:{path}?mode=ro&immutable=1', uri=True)) as conn:
        rows = conn.execute(
            'SELECT seq, idempotency_key, account, amount, receipt, worker_version FROM effects ORDER BY seq'
        ).fetchall()
    keys = ('seq', 'idempotency_key', 'account', 'amount', 'receipt', 'worker_version')
    return [dict(zip(keys, row)) for row in rows]


def _effects(output: Any, ledgers: Path | None) -> EffectsObserved | EffectsNotObserved:
    evidence = output.get('evidence') if isinstance(output, dict) else None
    if not evidence or ledgers is None:
        return EffectsNotObserved(
            status='not_observed', reason='no preserved worker ledger for this case; a report alone cannot show effects'
        )
    path = ledgers / evidence['ledger_db']
    if not path.exists():
        return EffectsNotObserved(status='not_observed', reason=f'ledger file {path.name!r} is missing')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    effects = _read_ledger(path)
    snapshot = output.get('ledger', {}).get('effects')
    if snapshot is None:
        integrity = 'no_report_snapshot'
    elif snapshot == effects and digest == evidence.get('ledger_db_sha256'):
        integrity = 'ledger_matches_report_snapshot'
    else:
        integrity = 'ledger_differs_from_report_snapshot'
    per_key: dict[str, int] = {}
    for effect in effects:
        per_key[effect['idempotency_key']] = per_key.get(effect['idempotency_key'], 0) + 1
    return EffectsObserved(
        status='observed',
        source='worker_ledger',
        ledger_file=path.name,
        ledger_sha256='sha256:' + digest,
        integrity=integrity,  # type: ignore[arg-type]
        effects=[Effect(**e) for e in effects],
        effects_per_idempotency_key=per_key,
    )


def _idempotency_keys(inputs: Any) -> list[str]:
    keys: list[str] = []
    for step in inputs.get('steps', []) if isinstance(inputs, dict) else []:
        key = (step.get('request') or {}).get('idempotency_key')
        if key and key not in keys:
            keys.append(key)
    return keys


def _uncertainty(output: Any, inputs: Any, effects: EffectsObserved | EffectsNotObserved) -> list[StepUncertainty]:
    if not isinstance(output, dict) or 'steps' not in output:
        return []
    per_key = effects.effects_per_idempotency_key if isinstance(effects, EffectsObserved) else None
    rows = []
    for i, step in enumerate(output['steps']):
        if step.get('effect_known_from_response', True):
            continue
        request = step.get('request') or (
            inputs['steps'][i].get('request') if i < len(inputs.get('steps', [])) else None
        )
        key = (request or {}).get('idempotency_key')
        rows.append(
            StepUncertainty(
                step=i,
                caller_status=step['status'],
                effect_known_from_response=False,
                idempotency_key=key,
                ledger_effects_for_key_at_scenario_end=(per_key.get(key, 0) if per_key is not None and key else None),
            )
        )
    return rows


def _repetition(name: str, source: str | None) -> tuple[int | None, int | None]:
    if source is None or not name.endswith(']') or '[' not in name:
        return None, None
    index, of = name.rsplit('[', 1)[1].rstrip(']').split('/')
    return int(index), int(of)


def convert(report: dict[str, Any], ledgers: Path | None, inline: bool) -> list[EvidenceRecord]:
    meta = report.get('experiment_metadata') or {}
    environment = meta.get('environment')
    framework_version = ((environment or {}).get('packages') or {}).get('pydantic-evals')
    run = RunIdentity(
        name=report['name'],
        framework='pydantic-evals',
        framework_version=framework_version,
        trace_id=report.get('trace_id'),
        span_id=report.get('span_id'),
    )
    now = datetime.now(UTC).isoformat()
    provenance = {
        'case, input, output, evaluations, timing, errors': 'pydantic_evals.EvaluationReport (JSON via EvaluationReportAdapter)',
        'worker.version, environment, case.dataset_digest': 'harness-supplied experiment_metadata, not observed by pydantic-evals',
        'effects': 'worker durable ledger (SQLite) re-read by this converter; hash recorded',
        'uncertainty': 'caller view recorded by the task harness, joined with the worker ledger',
        'attempt.index, attempt.count': 'not exposed by pydantic-evals (retry_task attempts are not recorded)',
        'run.started_at': 'not recorded in pydantic-evals reports',
        'attempt.repetition_*': 'derived from the report case name suffix "[i/n]"',
        'output.error.type': 'derived from the "Type: message" prefix of error_message',
    }
    records: list[EvidenceRecord] = []
    rows = [('returned', c) for c in report['cases']] + [('task_raised', f) for f in report['failures']]
    for status, case in rows:
        repetition_index, repetition_of = _repetition(case['name'], case.get('source_case_name'))
        output_value = case.get('output') if status == 'returned' else None
        evaluations: list[Evaluation] = []
        error = None
        if status == 'returned':
            for kind, group in (('assertion', 'assertions'), ('score', 'scores'), ('label', 'labels')):
                evaluations += [_evaluation(kind, r) for r in case[group].values()]
            for failure in case.get('evaluator_failures', []):
                evaluations.append(
                    Evaluation(
                        kind='evaluator_error',
                        name=failure['name'],
                        explanation=failure['error_message'],
                        error_type=failure.get('error_type') or 'pydantic_evals.EvaluatorFailure',
                        evaluator_source=json.dumps(failure['source'], sort_keys=True),
                        evaluator_version=failure.get('evaluator_version'),
                    )
                )
        else:
            message = case['error_message']
            error = ErrorInfo(
                message=message,
                type=message.split(':', 1)[0] if ':' in message else None,
                type_derived_from_message=True,
                stacktrace_sha256=sha256_json(case.get('error_stacktrace')),
            )
        effects = _effects(output_value, ledgers)
        record_key = {'run': run.name, 'case': case['name'], 'trace': run.trace_id, 'span': case.get('span_id')}
        records.append(
            EvidenceRecord(
                schema_id=SCHEMA_ID,
                record_id=sha256_json(record_key),
                case=CaseIdentity(
                    id=case['name'],
                    source_case_id=case.get('source_case_name'),
                    dataset=report.get('dataset_name'),
                    dataset_digest=meta.get('dataset_digest'),
                ),
                run=run,
                attempt=Attempt(index=None, count=None, repetition_index=repetition_index, repetition_of=repetition_of),
                worker=WorkerIdentity(version=meta.get('worker_version')),
                environment=environment,
                input=_ref(case['inputs'], inline),
                output=Output(
                    status=status,  # type: ignore[arg-type]
                    ref=_ref(output_value, inline) if status == 'returned' else None,
                    error=error,
                ),
                evaluations=evaluations,
                effects=effects,
                uncertainty=_uncertainty(output_value, case['inputs'], effects),
                retry_identity=_idempotency_keys(case['inputs']),
                timing=Timing(task_duration_s=case.get('task_duration'), total_duration_s=case.get('total_duration')),
                provenance=provenance,
                converted_at=now,
                converter=f'to_neutral.py ({SCHEMA_ID})',
            )
        )
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('report', nargs='?', type=Path)
    parser.add_argument('--ledgers', type=Path)
    parser.add_argument('--inline', action='store_true')
    parser.add_argument('--write-schema', type=Path)
    args = parser.parse_args()
    if args.write_schema:
        schema = EvidenceRecord.model_json_schema(by_alias=True)
        schema['$id'] = SCHEMA_ID
        args.write_schema.write_text(json.dumps(schema, indent=2) + '\n')
        return
    report = json.loads(args.report.read_text())
    for record in convert(report, args.ledgers, args.inline):
        line = record.model_dump_json(by_alias=True)
        EvidenceRecord.model_validate_json(line)  # every emitted record re-validates against the schema
        sys.stdout.write(line + '\n')


if __name__ == '__main__':
    main()
