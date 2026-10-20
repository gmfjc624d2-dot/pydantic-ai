# 1.1.0 run record (Linux only; request `public-review-cues-20261020-03`)

- Date: 2026-10-20. Host: Linux x86_64 cloud container (4 vCPU, "Intel(R) Xeon(R) Processor @ 2.80GHz",
  shared; other tenants may add timing noise). Not a macOS result.
- Code: commit `0419f015fbdfa3e11dcbe99e4d9d21341af101b3` (review_cues 1.1.0), clean working tree apart
  from this output directory. Baseline: review_cues 1.0.0 from commit
  `1c8c9ca3bc40a842296acab56436ccc1d1283c46` (code identical to the rules-freeze commit
  `3671e0ff05fe2018e7c7926bd0250d141ff75631`), extracted with `git show`; file SHA-256 in
  `benchmark/*/platform.json`.
- Fixtures and the stored 1.0.0 results under `../dev/` and `../reserved/` were read, not written
  (SHA-256 of all 22 tracked files under `fixtures/`, `results/` and `rules_v1.json` compared before and
  after: unchanged).
- Commands (from `acquisition/public_review_cues_20261020/`):

  ```bash
  python3.9 regression_check.py results/linux-x86_64/v1.1.0/regression/python3.9    # CPython 3.9.25
  python3   regression_check.py results/linux-x86_64/v1.1.0/regression/python3.13   # CPython 3.13.16
  python3.9 benchmark.py results/linux-x86_64/v1.1.0/benchmark/python3.9             # run sequentially,
  python3   benchmark.py results/linux-x86_64/v1.1.0/benchmark/python3.13            # one after the other
  ```

  Defaults: sizes 2,000 and 10,000 then 50,000 and 100,000 code points; 3 repeats; 60 s timeout per
  process. The extracted `baseline_src/` copies were deleted after the run (recoverable with
  `git show 1c8c9ca3:./review_cues/review_cues.py`).
- Both regression checks exited 0 (`"all_identical": true`). Both benchmarks exited 0 (no output
  differed between versions wherever both finished): 3.9.25 ran 23:02:58–23:09:25 UTC (6 min 27 s),
  3.13.16 ran 23:09:25–23:15:34 UTC (6 min 9 s). During the 3.13.16 run only `README.md` and
  `CONTRACT.md` were being edited (recorded in its `platform.json`); `review_cues/` stayed identical to
  `0419f01` (revised file SHA-256 `e9dc723a…` in both `platform.json` files).
- Superseded for the CLI by 1.1.1 (`9c23068`, see `../v1.1.1/RUN.md`), which does not change
  `find_cues()`; these timings were not repeated for 1.1.1.
- Additional checks recorded in `README.md` ("1.1.0" section): the deep-nesting counterexample and its
  1.0.0 thresholds (bisected with the 1.0.0 CLI), the empty-phrase hang, the `yes |` broken-pipe check,
  CLI output sizes, and the standalone relocation example.
