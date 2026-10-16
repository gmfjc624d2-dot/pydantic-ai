"""Reproduce: `retry_task` with `tenacity` installed but not the legacy `httpx` (see upstream-fix in REPORT.md)."""

from dataclasses import dataclass
from importlib.metadata import version

from tenacity import stop_after_attempt

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator

n = {'task': 0}


def task(x):
    n['task'] += 1
    if n['task'] == 1:
        raise RuntimeError('transient')
    return x


@dataclass
class Ok(Evaluator):
    def evaluate(self, ctx):
        return True


r = Dataset(name='r', cases=[Case(name='c1', inputs=1)], evaluators=[Ok()]).evaluate_sync(
    task, progress=False, retry_task={'stop': stop_after_attempt(2)}, retry_evaluators={'stop': stop_after_attempt(2)}
)
print(
    version('pydantic-evals'),
    'attempts',
    n['task'],
    'cases',
    len(r.cases),
    'failures',
    [f.error_message[:90] for f in r.failures],
)
