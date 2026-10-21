# 1.2.1 run record (Linux only; request `public-review-cues-20261020-04`)

- Date: 2026-10-21. Host: Linux x86_64 cloud container (4 vCPU, "Intel(R) Xeon(R) Processor @ 2.80GHz",
  shared). Not a macOS result.
- Code: commit `23f1434472bc56d2a0d3ac4868be51ed65432bca` (review_cues 1.2.1). During these runs
  `review_cues/`, `tests/` and the scripts were unchanged from that commit; only `README.md` and these
  output directories were uncommitted (recorded in each `platform.json`).
- Fixtures, rules and all earlier results were read, not written (the SHA-256 of the 22 files frozen in
  `-02` were compared before and after: unchanged).
- Commands (from `acquisition/public_review_cues_20261020/`):

  ```bash
  python3.9 regression_check.py results/linux-x86_64/v1.2.1/regression/python3.9 --cli-baseline-commit 9c23068811307bde53409f13fc40d63d0a4c97e1
  python3   regression_check.py results/linux-x86_64/v1.2.1/regression/python3.13 --cli-baseline-commit 9c23068811307bde53409f13fc40d63d0a4c97e1
  python3.9 results/linux-x86_64/v1.2.0/budget/measure_budget.py results/linux-x86_64/v1.2.1/budget   # 02:05:04-02:06:13 UTC
  python3   results/linux-x86_64/v1.2.0/budget/measure_budget.py results/linux-x86_64/v1.2.1/budget   # 02:06:13-02:07:45 UTC
  python3.9 results/linux-x86_64/v1.2.1/cli_runs.py results/linux-x86_64/v1.2.1/cli_runs-python3.9.jsonl
  python3   results/linux-x86_64/v1.2.1/cli_runs.py results/linux-x86_64/v1.2.1/cli_runs-python3.13.jsonl
  ```

  (`python3.9` is CPython 3.9.25, `python3` is CPython 3.13.16.)
- Regression: both exited 0. 96 / 96 item comparisons are identical to the stored 1.0.0 outputs apart
  from the version fields. The CLI without a budget is byte-identical to 1.1.1 (`9c23068`) on 59 / 60
  requests; the exception is the expected `invalid_arguments` usage text.
- `budget/python3.*/measurements.jsonl`: 80 rows each, none timed out. In "time" rows, `seconds` covers
  one `render_cues()` call, and `ru_maxrss_before`/`ru_maxrss_after` are the process peak in KiB before
  and after it. In "tracemalloc" rows, `tracemalloc_peak_bytes` is the peak of Python allocations during
  the call.
- `cli_runs-python3.*.jsonl`: one real CLI subprocess per case. Each row records exit status,
  stdout/stderr byte counts, the error code read from stdout or stderr, wall time, and the child's peak
  RSS in KiB.
- Tests on this commit: 50 pass and 18 / 18 mutations are rejected on both interpreters.
- `../v1.2.0/budget/measure_budget.py` and `cli_runs.py` were reformatted with `ruff format` after these
  runs (layout only; `ruff format` preserves the syntax tree).
