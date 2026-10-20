# 1.1.1 run record (Linux only; request `public-review-cues-20261020-03`, after review of `0419f01`)

- Date: 2026-10-20. Same host as `../v1.1.0/RUN.md`. Not a macOS result; CPython 3.9.6 and 3.12.14 were
  not run here (their behavior is as reported by the reviewer).
- Code: commit `9c23068811307bde53409f13fc40d63d0a4c97e1` (review_cues 1.1.1). `review_cues/`, `tests/`
  and the scripts were unchanged from that commit during these runs (`git diff --quiet HEAD`); only
  documentation and this output directory were uncommitted. 1.1.0 for comparison:
  `git show 0419f015fbdfa3e11dcbe99e4d9d21341af101b3:./review_cues/review_cues.py`.
- Commands (from `acquisition/public_review_cues_20261020/`; `$B` holds that 1.1.0 file and
  `rules_v1.json`):

  ```bash
  python3.9 regression_check.py results/linux-x86_64/v1.1.1/regression/python3.9     # CPython 3.9.25
  python3   regression_check.py results/linux-x86_64/v1.1.1/regression/python3.13    # CPython 3.13.16
  python3.9 results/linux-x86_64/v1.1.1/int_digits/measure_int_digits.py "$B" results/linux-x86_64/v1.1.1/int_digits/python3.9.jsonl
  python3   results/linux-x86_64/v1.1.1/int_digits/measure_int_digits.py "$B" results/linux-x86_64/v1.1.1/int_digits/python3.13.jsonl
  ```

- Regression: both exited 0, `"all_identical": true` (48 / 48 items identical to the stored 1.0.0 outputs
  apart from the version fields; evaluation classes identical).
- `int_digits/*.jsonl`: the first line describes the interpreter; in later rows, `impl: "working tree"`
  is the clean checkout of `9c23068` (1.1.1), and `status` is the CLI exit status, or `uncaught` with
  the exception type in `outcome`. No run timed out.
- Real-process CLI checks (1.1.1, both interpreters): `b"[" * 1100 + b"0" + b"]" * 1100` exits 2 with
  `json_too_deep`; `b'{"text":' + b"7" * 5000 + b',"language":"en"}'` exits 2 with `text_not_string`;
  stderr empty in both cases. Sixteen ordinary numeric and duplicate-key requests got byte-identical
  responses from 1.0.0 and 1.1.1 on both interpreters.
- Standalone relocation (CPython 3.13.16): a directory holding only `LICENSE`, `review_cues.py` and
  `rules_v1.json` ran the CLI and import examples; its response was byte-identical to the in-repository
  CLI's.
