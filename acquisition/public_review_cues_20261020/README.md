# Review-cue highlighter prototype (`public-review-cues-20261020-02`, revised in `-03`)

A small, standard-library-only (Python ≥ 3.9) prototype that marks **lexical candidates** for six
review topics — condition, exception, negation, uncertainty, attribution, obligation — in Spanish and
English, with exact source coordinates and explicit ambiguity notes. It is research, not product
runtime code, and it never infers scope, a speaker's identity, entailment, semantic completeness,
permission or an acceptance verdict. **Empty highlights mean no configured cue matched, not that the
text has no relevant qualification.** The lexicon is small and makes no coverage claim.

Behavior and output format: [`CONTRACT.md`](CONTRACT.md). Annotation rules: [`fixtures/ANNOTATION.md`](fixtures/ANNOTATION.md).
Earlier research on this branch (`acquisition/pydantic_evals_offline/`,
`acquisition/public_nli_conditions_20261020/`) is untouched.

## Status

| | |
|---|---|
| Implemented and executed (Linux x86_64 only; CPython 3.9.25 and 3.13.16) | pure function + JSON CLI; 47-rule / 79-phrase ES/EN lexicon; dev evaluation; one reserved evaluation after the rules freeze (1.0.0) |
| 1.1.0 and 1.1.1 (`-03`) | CLI request byte limit, JSON nesting limit and long-integer handling with structured rejections; overlap lists without pairwise scans; 35 contract tests and a 12-mutation check (all pass, every mutation rejected); output identical to 1.0.0 on all 48 fixture items apart from the version fields; baseline-vs-1.1.0 timings ([below](#110-bounded-requests-and-overlaps-without-pairwise-scans)) |
| Not done | macOS qualification (requester will qualify separately); any rule or matching change after the reserved run (the `n't` boundary defect is still present by instruction); validation of custom `--rules` files; any parser, model, corpus or network use |

## Timeline (commits on `claude/sweet-carson-tjohp1`)

1. `ffb913afb7310e17bc63a944aff5c91531b0a30e` — annotation guidelines and **reserved** set frozen; no
   lexicon, code or dev set existed yet.
2. `3671e0ff05fe2018e7c7926bd0250d141ff75631` — dev set, rules, tool, contract, tests and dev results
   frozen; reserved set not yet run.
3. `1c8c9ca3bc40a842296acab56436ccc1d1283c46` — reserved set run once on both interpreters from that
   clean commit; results and this documentation committed afterwards. Rules unchanged.
4. `0419f015fbdfa3e11dcbe99e4d9d21341af101b3` — 1.1.0 code, tests, contract, `regression_check.py`
   and `benchmark.py` (`-03`). Rules and fixtures unchanged.
5. `9c23068811307bde53409f13fc40d63d0a4c97e1` — 1.1.1: long JSON integers parsed without `int()`;
   contract compatibility statement qualified (after review of commit 4). Rules and fixtures unchanged.
6. The commit that adds this section and `results/linux-x86_64/v1.1.{0,1}/`: 1.1.0 results produced
   from commit 4's code, 1.1.1 results from commit 5's (see each `RUN.md`).

## Layout

| Path | Contents |
|---|---|
| `review_cues/review_cues.py` | `find_cues()` and the CLI (standard library only) |
| `review_cues/rules_v1.json` | the lexicon: ids, languages, topics, phrases, ambiguity notes, construction policy |
| `fixtures/` | `ANNOTATION.md`; `reserved_source.py` → `reserved.jsonl`; `dev_source.py` → `dev.jsonl`; SHA-256 files |
| `tests/test_review_cues.py`, `tests/mutation_check.py` | contract tests; proof that the tests reject broken variants |
| `evaluate.py` | runs a fixture set and lists every hit, omission and distracting highlight |
| `regression_check.py` | compares this version's output on all fixture items with the stored 1.0.0 outputs (`-03`) |
| `benchmark.py` | times the 1.0.0 baseline (extracted from git) against this version on synthetic texts (`-03`) |
| `results/linux-x86_64/{dev,reserved}/python3.{9,13}/` | 1.0.0: `raw_results.jsonl` (full tool output per item), `evaluation.json`, `evaluation.md`; `reserved/RUN.md`. Never modified after `-02` |
| `results/linux-x86_64/v1.1.0/` | `RUN.md`; `regression/python3.{9,13}/regression.json`; `benchmark/python3.{9,13}/` (`measurements.jsonl`, `platform.json`, `summary.md`) |
| `results/linux-x86_64/v1.1.1/` | `RUN.md`; `regression/python3.{9,13}/regression.json`; `int_digits/` (`measure_int_digits.py`, raw `python3.{9,13}.jsonl`) |

## Reproduce

From `acquisition/public_review_cues_20261020/` (any CPython ≥ 3.9; no dependencies):

```bash
python3 -m unittest discover -s tests -v          # 35 contract tests (22 in 1.0.0, 33 in 1.1.0)
python3 tests/mutation_check.py                   # each of 12 mutations must be rejected (5 in 1.0.0)
python3 regression_check.py "$OUT/regression"     # vs stored 1.0.0 outputs; exit 1 on any difference
python3 benchmark.py "$OUT/benchmark"             # 1.0.0 vs this version; needs git history; minutes
(cd fixtures && python3 reserved_source.py && python3 dev_source.py && sha256sum -c reserved.sha256 dev.sha256)
python3 evaluate.py dev "$OUT/dev"

printf '%s' '{"text": "Visitors must not touch the vases, unless a guide is present.", "language": "en"}' \
  | python3 review_cues/review_cues.py
```

`evaluation.json` is expected to be identical on every Python version; `raw_results.jsonl` records the
running Python's Unicode database version, so `configuration_sha256` differs between versions by design.
The 1.0.0 reserved evaluation was a one-time event; `regression_check.py` reuses the reserved items only
to reproduce the stored outputs, which is not held-out evidence.

## 1.1.0: bounded requests and overlaps without pairwise scans

Request `public-review-cues-20261020-03`. Two patches to `review_cues.py`: 1.1.0 (this section) and
1.1.1 ([below](#111-long-json-integers-after-review-of-0419f01)); contract:
[`CONTRACT.md`, "Changes from 1.0.0"](CONTRACT.md#changes-from-100). Lexicon, matching semantics,
offsets, notes, observations and notices unchanged.

| Change | 1.0.0 | 1.1.0 |
|---|---|---|
| Reading the CLI request | `stdin.read()` without a size, then the 100,000-code-point check | chunks of ≤ 64 KiB, never more than 1,265,536 + 1 bytes; larger input → `request_too_large`, nothing parsed |
| JSON nested deeper than Python's `json` recursion limit | uncaught `RecursionError`, exit status 1, traceback | more than 64 levels outside strings → `json_too_deep` before parsing |
| `overlaps` lists | every pair of matches compared: O(m²) | bisection over sorted starts: O(m log m + overlapping pairs); same relation and order |
| `tool.version`, `configuration_sha256` | `1.0.0` | `1.1.0` (so the hash differs) |

**Deep-nesting counterexample** (reported on CPython 3.9.6; kept verbatim in
`tests/test_review_cues.py`): `b"[" * 1100 + b"0" + b"]" * 1100`, 2,201 bytes. Reproduced here with the
1.0.0 file from git, run as a script (bisected):

| Interpreter | 1.0.0: deepest structured rejection | 1.0.0: first crash (exit 1, `RecursionError`) | 1.1.0 |
|---|---|---|---|
| CPython 3.9.25 | 993 levels (`request_not_object`) | 994 levels (1,989 bytes) | `json_too_deep` above 64 levels, at every depth |
| CPython 3.13.16 | 9,998 levels | 9,999 levels (19,999 bytes) | same |

A byte limit alone cannot prevent this: the crashing inputs are far below it. The nesting check is a
regex scan over the decoded request; its worst measured cost at the byte limit was about 0.2 s
(1,265,534 bytes of `[],`).

### Regression against the stored 1.0.0 outputs

From a clean checkout of `0419f01`, `regression_check.py` recomputed all 24 dev and 24 reserved items
(each in its own language) and compared every full result with each stored 1.0.0 result, masking only
`tool.version`, `configuration.unicode_database_version` and `configuration_sha256`:

| Run | vs stored python3.9 | vs stored python3.13 | evaluation classes (`evaluate.classify`) |
|---|---|---|---|
| CPython 3.9.25 | 48 / 48 identical; unmasked `configuration` identical | 48 / 48 identical | 48 / 48 identical to both |
| CPython 3.13.16 | 48 / 48 identical | 48 / 48 identical; unmasked `configuration` identical | 48 / 48 identical to both |

This is regression reproduction, not held-out evidence: the reserved items were seen in `-02`. The
fixtures exercise overlaps weakly: the stored dev outputs contain 3 overlapping pairs (in 3 items) and
the reserved outputs none. The evidence that the overlap relation is preserved therefore rests mainly on
the tests: a separately written all-pairs oracle checked against the new computation on fixed layouts
(equal starts, nested, duplicate spans, touching, chain, 500 disjoint spans, empty spans) and 2,000
seeded random layouts, plus every `find_cues` result in the suite (dev fixtures, 500 random Unicode
strings, a dense overlapping text). A counting integer type shows that 20,000 disjoint spans need at
most 20,000 × 15 comparisons (a pairwise check needs about 4 × 10⁸). A negative control (one result's
`overlaps` perturbed in memory) made `regression_check.py` exit 1, naming the 3 dev items.

### Runtime: 1.0.0 vs 1.1.0 (Linux only)

`benchmark.py` from a clean checkout of `0419f01`; 1.0.0 extracted from `1c8c9ca` with `git show`.
One fresh process per run, `find_cues()` timed after a warm-up call, 3 repeats, 60 s timeout. Medians
in seconds; min and max, every raw row and the platform details are in
`results/linux-x86_64/v1.1.0/benchmark/python3.{9,13}/`. Host: shared 4-vCPU x86_64 container
("Intel(R) Xeon(R) Processor @ 2.80GHz"); timings are for this host only.

| Text shape (language) | code points | matches | overlapping pairs | 3.9.25: 1.0.0 | 3.9.25: 1.1.0 | 3.13.16: 1.0.0 | 3.13.16: 1.1.0 |
|---|---|---|---|---|---|---|---|
| no cue (en) | 10,000 | 0 | 0 | 0.0051 | 0.0048 | 0.0041 | 0.0041 |
| no cue (en) | 100,000 | 0 | 0 | 0.048 | 0.048 | 0.039 | 0.038 |
| `no ` repeated (es), disjoint | 10,000 | 3,333 | 0 | 1.39 | 0.033 | 1.42 | 0.032 |
| `no ` repeated (es), disjoint | 50,000 | 16,667 | 0 | 42.4 | 0.22 | 43.1 | 0.14 |
| `no ` repeated (es), disjoint | 100,000 | 33,333 | 0 | timeout (> 60) | 0.42 | timeout (> 60) | 0.34 |
| `Only if ` repeated (en), nested | 50,000 | 12,500 | 6,250 | 28.2 | 0.15 | 23.6 | 0.12 |
| `Only if ` repeated (en), nested | 100,000 | 25,000 | 12,500 | timeout (> 60) | 0.34 | timeout (> 60) | 0.25 |
| seeded ES/EN sentences (es+en) | 10,000 | 654 | 95 | 0.060 | 0.017 | 0.062 | 0.016 |
| seeded ES/EN sentences (es+en) | 100,000 | 6,715 | 1,066 | 8.16 | 0.18 | 6.82 | 0.16 |

Wherever both versions finished (all sizes except the two timeouts), their outputs were identical apart
from `tool.version` and `configuration_sha256`: 14 of 16 shape/size cells per interpreter. Where 1.0.0
timed out, its remaining repeats were not run, and nothing is inferred about how long it would have
taken. Cue-free text costs the same in both versions, because the regex scan is unchanged. These are
synthetic worst-case shapes, not a sample of real documents, and say nothing about time saved by a
human reviewer.

CLI output sizes for the 100,000-code-point texts (1.1.0, CPython 3.13.16, one run each):

| Text shape | request bytes | response bytes | CLI wall time |
|---|---|---|---|
| no cue | 100,030 | 2,362 | 0.09 s |
| `no ` repeated | 100,030 | 24,087,311 | 0.68 s |
| `Only if ` repeated | 100,030 | 18,967,650 | 0.55 s |
| seeded sentences | 108,128 | 4,729,800 | 0.25 s |

### 1.1.1: long JSON integers (after review of `0419f01`)

Published separately as `9c23068`, so `0419f01` stays recoverable as reviewed. Two review findings:

1. **Uncaught `ValueError`.** `b'{"text":' + b"7" * 5000 + b',"language":"en"}'` is only 5,025 bytes.
   CPython versions that limit integer string conversion (4,300 digits by default) raise `ValueError`
   inside `json.loads`, so 1.0.0 and 1.1.0 exited 1 with a traceback. This was reproduced here on 3.9.25
   and 3.13.16 and reported on 3.12.14. CPython 3.9.6, which has no such limit, returned
   `text_not_string` (reported).
2. **Quadratic conversion where there is no limit.** On 3.9.6, `int()` never raises, so a fallback that
   runs only after `int()` fails would still convert long literals in quadratic time (reported:
   0.0755 s at 100,000 digits and 0.2989 s at 200,000 on 3.9.6).

The fix: `json.loads(..., parse_int=_parse_int)` keeps literals of more than `MAX_INT_DIGITS` = 640
digits as an exact `decimal.Decimal` **before** any `int()` call. 640 is CPython's lowest configurable
conversion limit (`sys.int_info.str_digits_check_threshold`; `sys.set_int_max_str_digits(639)` is
refused), so `int()` cannot raise on the remaining literals under any setting. No request field accepts
a number, so the codes are the ones 3.9.6 gives (`text_not_string`, `invalid_language`,
`unknown_field`, `duplicate_key`, `request_not_object`), and they do not depend on the interpreter.
Integers up to 640 digits, floats, constants and duplicate keys are untouched. 16 such requests got
byte-identical responses from 1.0.0 and 1.1.1 on both interpreters. No interpreter setting is changed.

Raw timings of the CLI path (`main()` on an in-memory request `{"text": <N digits>, "language":
"en"}`), one process per cell, from a clean checkout of `9c23068`. "Limit disabled" uses
`-X int_max_str_digits=0`, which emulates an interpreter without the limit; 3.9.6 itself was not run
here. Raw rows: `results/linux-x86_64/v1.1.1/int_digits/`.

| digits | 3.9.25 default: 1.1.0 | 3.9.25 default: 1.1.1 | 3.9.25 limit disabled: 1.1.0 | 3.9.25 limit disabled: 1.1.1 | 3.13.16 limit disabled: 1.1.0 | 3.13.16 limit disabled: 1.1.1 |
|---|---|---|---|---|---|---|
| 5,000 | `ValueError`, exit 1 | `text_not_string`, 0.0002 s | 0.0003 s | 0.0002 s | 0.0003 s | 0.0002 s |
| 100,000 | `ValueError`, exit 1 | 0.0020 s | 0.0498 s | 0.0025 s | 0.0169 s | 0.0020 s |
| 200,000 | `ValueError`, exit 1 | 0.0038 s | 0.2146 s | 0.0040 s | 0.0480 s | 0.0045 s |
| 1,265,511 (fills the byte limit) | `ValueError`, exit 1 | 0.0252 s | 7.8140 s | 0.0239 s | 0.9330 s | 0.0205 s |

With the default limit, 3.13.16 behaves like 3.9.25 (1.1.0: `ValueError` at every size; 1.1.1:
`text_not_string` within 0.022 s). The `regression_check.py` result for 1.1.1 is the same as for 1.1.0:
48 / 48 items identical apart from the version fields, on both interpreters.

The compatibility statement in `CONTRACT.md` is now qualified, as the review asked. Requests valid
under 1.0.0 that fit the new bounds get the same result. A valid request larger than 1,265,536 bytes,
which is only possible with more than 65,421 bytes of JSON whitespace, is now rejected by design.

### Residual limits

- **Custom rule files are still unvalidated** (out of scope): `--rules PATH` can exit 1 with a raw
  Python traceback on a malformed file, and **an empty phrase makes the search loop forever** (verified:
  killed by a 10 s timeout). `re.compile('').search(text, pos)` keeps returning an empty match at the
  end of the text, so the `pos = start + 1` loop never ends. The default rule file has no empty phrase.
- **No output bound.** Input is bounded (100,000 code points; 1,265,536 request bytes), but each match
  carries its rule notes and observations, so dense input yields large output (24 MB for 100 KB of
  `no `; table above). Output is never truncated; a caller that needs a bound must enforce it on the
  input.
- Overlap lists are proportional to the overlapping pairs, which is the size of that part of the output
  itself; no computation can be smaller.
- The cue search itself (one regex scan per phrase form) is unchanged and was not analyzed beyond the
  timings above.
- A rejected oversized request is not drained: an upstream producer may receive `SIGPIPE`/`EPIPE`
  (verified: `yes | python3 review_cues/review_cues.py` returns `request_too_large`, and `yes` exits 141).
- The `n't` boundary defect, the missing reserved-set wordings and all other `-02` failures remain, as
  instructed; the lexicon is byte-identical (SHA-256 `3588b3b5…4346`).
- Linux x86_64 only. The repository's `fix-smartquotes` and `fix-spaces` pre-commit hooks rewrite the
  deliberate `'` and NBSP characters in the tests and contract, so they were skipped for these files.
  The other hooks pass.

### macOS qualification (one command, from the repository root)

```bash
cd acquisition/public_review_cues_20261020 && OUT="$(mktemp -d)" && git rev-parse HEAD && python3 -VV \
  && python3 -m unittest discover -s tests -v && python3 tests/mutation_check.py \
  && python3 regression_check.py "$OUT/regression" && python3 benchmark.py "$OUT/benchmark" \
  && echo "qualified; outputs in $OUT"
```

Expected: 35 tests OK (including the deep-nesting and long-integer counterexamples), 12 mutations
rejected, `"all_identical": true`, and a benchmark with "outputs identical" = yes wherever both
versions finished. The benchmark needs the git history (it extracts 1.0.0 with `git show`) and took
6 min 27 s (3.9.25) and 6 min 9 s (3.13.16) on this Linux host, mostly in 1.0.0 runs and timeouts.
Timings will differ on macOS and are not comparable across machines. For the long-integer change alone:
`python3 results/linux-x86_64/v1.1.1/int_digits/measure_int_digits.py DIR_WITH_1.1.0 OUT.jsonl`, where
`DIR_WITH_1.1.0` holds `git show 0419f01:./review_cues/review_cues.py` and `rules_v1.json`.
With Apple's `/usr/bin/python3` (3.9.x, Unicode 13.0.0), the unmasked `configuration` should also equal
the stored `python3.9` one.

### Standalone relocation (runtime files and license only)

```bash
REPO="$(git rev-parse --show-toplevel)" && DEST="$(mktemp -d)"
cp "$REPO/acquisition/public_review_cues_20261020/review_cues/review_cues.py" \
   "$REPO/acquisition/public_review_cues_20261020/review_cues/rules_v1.json" "$DEST/"
cp "$REPO/LICENSE" "$DEST/LICENSE"      # MIT, repository root
cd "$DEST" && ls
printf '%s' '{"text": "Visitors must not touch the vases, unless a guide is present.", "language": "en"}' \
  | python3 -I review_cues.py
python3 -I -c 'import sys; sys.path.insert(0, "."); from review_cues import find_cues; print(find_cues("Si llueve, no abre.", "es")["match_count"])'
```

`review_cues.py` finds `rules_v1.json` next to itself, imports only the standard library and needs
nothing else. Run here with 1.1.1 (CPython 3.13.16): the directory held exactly `LICENSE`,
`review_cues.py` and `rules_v1.json`; the CLI found `must`, `not`, `unless`, and its response was
byte-identical to the in-repository CLI's; the import example printed `2`.

## Results (1.0.0; counts only; tiny, hand-written, non-independent items)

| | dev (24 items) | reserved (24 items) |
|---|---|---|
| gold spans with an exact, topic-compatible highlight | 48 / 48 | **35 / 42** |
| highlights | 53 | 41 |
| — true positives | 48 | 35 |
| — on a recorded distractor | 2 | 5 |
| — nested inside a gold span that was also hit (`if` in `Only if`) | 3 | 0 |
| — shorter than an unmatched gold span (`salvo` in `salvo que`) | 0 | 1 |
| cue-free items with zero highlights | — | 2 / 2 |
| format cases (emoji before cue, CRLF inside cue, decomposed accent) all hit | — | 3 / 3 |

The dev score is not evidence: the lexicon was built from dev. The reserved score is mostly a measure of
lexicon overlap, split by where each reserved cue type came from:

| Origin of the reserved cue type | gold | hit |
|---|---|---|
| also in the dev gold | 25 | 25 |
| in the frozen annotation spec examples | 10 | 10 |
| in the lexicon only as a closed-class completion | 1 | 0 |
| not in the lexicon | 6 | 0 |

Every cue whose string was configured was found except one, and no unconfigured wording was found:
this prototype finds exactly its list, minus a boundary defect.

## Failure analysis (all reserved failures)

**Omissions (7)**

| Item | Gold | Cause |
|---|---|---|
| `r-en-07` | `should` in `shouldn't` | **Boundary defect.** The right boundary rejects a match followed by an alphanumeric, so a modal contracted with `n't` is never reported (`shouldn't`, `mustn't`, `couldn't`, `mightn't`; only `n't` is highlighted). The dev set had `can't`, but `can` is not a cue, so dev never exercised this. |
| `r-en-09` | `Assuming` | not in lexicon |
| `r-en-11` | `does not apply to` (exception) | not in lexicon; its `not` was highlighted as negation |
| `r-es-01` | `probablemente` | not in lexicon (only the English `probably` is in the spec) |
| `r-es-02` | `salvo que` | not in lexicon; `salvo` alone highlighted (partial) |
| `r-es-06` | `siempre y cuando` | not in lexicon |
| `r-es-08` | `En el supuesto de que` | not in lexicon |

**Distracting or partial highlights (6)**: `May` (month, `r-en-08`); `pueden` as permission
(`r-es-06`, `r-es-11`); `nada` meaning "swims" (`r-es-07`); the `no` of `no obstante` (`r-es-11`);
`salvo` inside `salvo que` (partial). Each is covered by a rule note shown with the match; none is
suppressed, by design.

**Proposed, not implemented** (each would need a new, independently written reserved set to evaluate;
re-running this reserved set after such a change would not be held-out evidence): accept a cue whose
right neighbor begins a `n't`/`n’t` suffix; add the Spanish multiword conjunctions found missing; offer
an optional, reported (never silent) "known fixed expression" list for `no obstante`, `a salvo`,
`sin embargo`.

## Provenance, authorship and overlap limitations

- All texts are original, synthetic, harmless toy scenarios (museum, library, weather, geometry) written
  for this repository by the AI assistant (Claude) during this request; no corpus, no copyrighted,
  private or institutional text. The outputs and inputs are public and generic.
- **One author wrote everything**: guidelines, reserved set, dev set and rules. The reserved set was
  written and frozen first, but the rule author had read it and cannot forget it. The lexicon policy
  (dev gold + frozen spec examples + closed-class completions; nothing found only in the reserved set)
  limits but does not remove this leakage; 35 of 42 reserved gold spans have cue types that were already
  in dev or in the spec.
- The dev set was written after the reserved set by the same author, in the same toy domains and with
  similar sentence shapes, so it may echo the reserved set's style; dev and reserved are not independent
  samples of any real text.
- 24 items per set, 6 topics, 2 languages: far too few for rates or intervals. Only counts are reported.
- An independent check would need texts written by someone who has not seen the lexicon, ideally real
  public documents with their own annotation.

## Platform note

All checks above ran on Linux only. The requester will qualify macOS separately; the same commands
apply. Expected macOS differences: the Python build's Unicode database version (and therefore
`configuration_sha256`); everything else in `evaluation.json` should match byte for byte.
