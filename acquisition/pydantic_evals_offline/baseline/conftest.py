import os

import pytest
from hypothesis import HealthCheck, settings

# Deterministic by default (repeatable evidence); `HYPOTHESIS_PROFILE=explore` searches randomly
# and keeps failing examples in Hypothesis' default example database (`.hypothesis/`) so they replay.
settings.register_profile(
    'deterministic',
    derandomize=True,
    database=None,
    deadline=None,
    max_examples=200,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.register_profile('explore', deadline=None, max_examples=500, suppress_health_check=[HealthCheck.too_slow])
settings.load_profile(os.environ.get('HYPOTHESIS_PROFILE', 'deterministic'))


@pytest.fixture
def impl() -> str:
    return os.environ.get('WORKER_IMPL', 'v1-correct')
