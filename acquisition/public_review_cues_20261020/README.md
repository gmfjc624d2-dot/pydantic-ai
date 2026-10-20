# Review-cue highlighter prototype (`public-review-cues-20261020-02`)

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
| Implemented and executed (Linux x86_64 only; CPython 3.9.25 and 3.13.16) | pure function + JSON CLI; 47-rule / 79-phrase ES/EN lexicon; 22 contract tests and a 5-mutation check (all pass, every mutation rejected); dev evaluation; one reserved evaluation after the rules freeze |
| Not done | macOS qualification (requester will qualify separately); any rule change after the reserved run; any parser, model, corpus or network use |

## Timeline (commits on `claude/sweet-carson-tjohp1`)

1. `ffb913afb7310e17bc63a944aff5c91531b0a30e` — annotation guidelines and **reserved** set frozen; no
   lexicon, code or dev set existed yet.
2. `3671e0ff05fe2018e7c7926bd0250d141ff75631` — dev set, rules, tool, contract, tests and dev results
   frozen; reserved set not yet run.
3. Reserved set run once on both interpreters from that clean commit; results and this documentation
   committed afterwards. Rules unchanged.

## Layout

| Path | Contents |
|---|---|
| `review_cues/review_cues.py` | `find_cues()` and the CLI (standard library only) |
| `review_cues/rules_v1.json` | the lexicon: ids, languages, topics, phrases, ambiguity notes, construction policy |
| `fixtures/` | `ANNOTATION.md`; `reserved_source.py` → `reserved.jsonl`; `dev_source.py` → `dev.jsonl`; SHA-256 files |
| `tests/test_review_cues.py`, `tests/mutation_check.py` | contract tests; proof that the tests reject broken variants |
| `evaluate.py` | runs a fixture set and lists every hit, omission and distracting highlight |
| `results/linux-x86_64/{dev,reserved}/python3.{9,13}/` | `raw_results.jsonl` (full tool output per item), `evaluation.json`, `evaluation.md`; `reserved/RUN.md` |

## Reproduce

From `acquisition/public_review_cues_20261020/` (any CPython ≥ 3.9; no dependencies):

```bash
python3 -m unittest discover -s tests -v          # 22 contract tests
python3 tests/mutation_check.py                   # each of 5 mutations must be rejected
(cd fixtures && python3 reserved_source.py && python3 dev_source.py && sha256sum -c reserved.sha256 dev.sha256)
python3 evaluate.py dev "$OUT/dev"
python3 evaluate.py reserved "$OUT/reserved" --rules-are-frozen
cmp "$OUT/reserved/evaluation.json" results/linux-x86_64/reserved/python3.9/evaluation.json

printf '%s' '{"text": "Visitors must not touch the vases, unless a guide is present.", "language": "en"}' \
  | python3 review_cues/review_cues.py
```

`evaluation.json` is expected to be identical on every Python version; `raw_results.jsonl` records the
running Python's Unicode database version, so `configuration_sha256` differs between versions by design.

## Results (counts only; tiny, hand-written, non-independent items)

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
