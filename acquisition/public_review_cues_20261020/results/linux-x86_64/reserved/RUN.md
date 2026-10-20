# Reserved run record (Linux only)

- Date: 2026-10-20. Host: Linux x86_64 cloud container. Not a macOS result.
- Code and rules: commit `3671e0ff05fe2018e7c7926bd0250d141ff75631` (rules freeze), clean working tree.
- Reserved fixtures: frozen in commit `ffb913afb7310e17bc63a944aff5c91531b0a30e`,
  SHA-256 `eecc0e2bfe0f68fdd1716501949efd447172278ede8304c9aa5a2b8929842ae3`; written before any rule existed.
- Ruleset canonical SHA-256: `b33ac9e99a5177e317ab7ab274a7ca6821491cb912f10264b9a50a3a5726af63`.
- Commands (one evaluation event, two interpreters; nothing was changed between or after them):

  ```bash
  python3.9 evaluate.py reserved results/linux-x86_64/reserved/python3.9 --rules-are-frozen   # CPython 3.9.25, Unicode 13.0.0
  python3   evaluate.py reserved results/linux-x86_64/reserved/python3.13 --rules-are-frozen  # CPython 3.13.16, Unicode 15.1.0
  ```

- `evaluation.json` is byte-identical between the two interpreters; `raw_results.jsonl` differs only in
  `configuration.unicode_database_version` and therefore `configuration_sha256`.
- Rules were not modified after this run. Observations that would motivate a change are recorded in
  `README.md` ("Failure analysis") as proposals that would need new, independently written data.
