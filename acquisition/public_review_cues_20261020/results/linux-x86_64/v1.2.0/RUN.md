# 1.2.0 measurement record (superseded by 1.2.1; Linux only; request `public-review-cues-20261020-04`)

- Code: commit `6594a181d98f9754fd3c89f2058659bdb6474a5a` (review_cues 1.2.0), clean checkout apart from
  this output directory.
- Command: `python3.9 results/linux-x86_64/v1.2.0/budget/measure_budget.py results/linux-x86_64/v1.2.0/budget`
  (CPython 3.9.25, 2026-10-21 01:59:17–02:00:48 UTC). Raw rows: `budget/python3.9/`.
- Finding: when the complete output fit the budget, 1.2.0 used about twice the memory of the unbudgeted
  path. With 100,000 code points of `no ` under `es+en` (output 48,794,486 bytes), peak RSS was 840 MiB
  and the call took 5.06 s with a 100 MiB budget, against 404 MiB and 3.30 s without one (highest RSS
  and median time of 3 runs).
  The cause was one `bytes` object per encoder piece. Fixed in 1.2.1 (`23f1434`, one `bytearray`); the
  output bytes were the same.
- The CPython 3.13.16 run was stopped after 19 of 80 rows to fix this. Those rows were deleted, not
  recorded. The 1.2.0 regression output was regenerated for 1.2.1 under `../v1.2.1/`.
- Rejected-budget rows here (64 KiB, 1 MiB, 10 MiB) exercise code that 1.2.1 did not change. They are
  superseded only because the version differs; see `../v1.2.1/` for the current measurements.
