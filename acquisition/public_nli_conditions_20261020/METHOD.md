# Method and frozen fixtures

## Question

Can a small, offline, multilingual NLI classifier give a *useful advisory signal* for document review in
Spanish and English, on conditions, exceptions, negation, uncertain modality, attribution and
multi-sentence reference, compared with a transparent lexical baseline? "Advisory" is literal: a model
score is never an authorization, a verdict or ground truth.

What is deliberately **not** equated:

- benchmark accuracy (e.g. English MNLI/XNLI test sets) with accuracy on these phenomena;
- an entailment *probability* with the *truth* of a hypothesis or with calibrated confidence;
- *summary coverage* (does a text mention what the source says?) with *consistency* (does the source
  support what the text says?) or with *semantic sufficiency* (is the selected evidence enough to decide?);
- *citation* (where the supporting text is: the `evidence` spans) with *scope* (what that text licenses:
  the label). Fixtures store them separately, and neutral items deliberately have relevant-looking
  evidence that does not license the hypothesis.

## Fixtures (frozen in commit `733b7f763de04edcfeb33d12be90be145185e5c9`)

- `fixtures/dev.jsonl`, `fixtures/heldout.jsonl`: 24 items each. Per set, six phenomena × one toy
  scenario (museum, books, weather, geometry puzzle) × four hypotheses against the same reference:
  `base`, label-preserving `paraphrase`, small `meaning_change`, and `missing_qualifier` (a dropped
  condition, hedge, attribution or source qualifier, labeled **neutral**, not contradiction).
  Label counts: dev 10 entailment / 8 contradiction / 6 neutral; held-out 9 / 9 / 6.
- Every item has a Spanish and an English variant (paired, not independent), a strict three-way label,
  a rationale, and `evidence` spans with character offsets computed by the builder (each must occur
  exactly once in the reference).
- Exception and reference-resolution items carry a manually selected **single-span** trial (one
  sentence of the reference) with its *own* label for what that span alone supports. Four span trials
  per set are selection-risk cases (the span label differs from the full-reference label, e.g. a
  general rule without its exception); six per set are flagged `convention_sensitive` (an unresolved
  pronoun in the span: strict neutral; lenient readers would resolve it).
- `fixtures/excluded.jsonl`: nine drafts removed during the ambiguity review, with reasons.
- `fixtures/REVIEW.md`: labeling convention and residual concerns, written before any prediction.
- `fixtures/freeze_manifest.json`: SHA-256 of the three JSONL files; every script refuses fixtures
  that do not match it. `python3 fixtures/build_fixtures.py` regenerates the files byte-for-byte.
- `fixtures/errata.json` / `errata.md`: appended after the freeze, flags only (see below).

## Protocol and timeline

1. Fixtures authored, ambiguity-reviewed, frozen and pushed (`733b7f7`) — no scoring code existed.
2. Lexical baseline written; its single threshold fitted on **dev only**; predictions for both sets
   written once and hashed.
3. Independent requester review of the freeze (without any prediction) → `errata.json`.
4. Model run: **blocked** in this session (see `RESULTS.md`). The harness is implemented and
   self-tested; nothing imitates its output.

Labels were never changed after step 1. Thresholds were never fitted on held-out data. Inputs are
never translated at evaluation time (each language is its own frozen text) and never truncated
(over-length inputs are refused and recorded).

## Errata (flags, not relabels)

| Flag | Items | Reading |
|---|---|---|
| `disputed` | `h-negation-2` | "recorded no snow at all" ≠ "recorded no snowfall" (snow depth vs new snowfall) |
| `convention_standing_rule` | `d-condition-1`, `d-condition-2` | contradiction requires reading the conditional as a standing rule whose condition can occur; under a vacuous reading both conditionals hold |
| `convention_coherent_source` | `d-attribution-3`, `h-attribution-1`, `h-attribution-2` | contradiction assumes a coherent source and a single report |
| `pre_freeze_residual_concern` | six items listed in `REVIEW.md` | listed for inspection; stay in every headline count |

The scorer always reports the original full set first, then `excluding_disputed`, each flag group on
its own, and an `assumption_light_core` (without `disputed` and the two convention groups).

## Systems

**Lexical baseline (`lexical-baseline/v1`, `baseline_lexical.py`)**: accent-folded lowercase tokens;
fixed ES/EN stopword lists; coverage = share of hypothesis content tokens found in the premise (exact
or same first five characters); `contradiction` if coverage ≥ τ and negation-cue parity differs or a
digit is new; `entailment` if coverage ≥ τ otherwise; `neutral` below τ. τ ∈ {0.50…1.00} chosen by
dev macro-F1 (ties → larger τ): **τ = 0.60**. It is a transparent floor, not a competitor: it cannot
represent conditions, modality, attribution or reference by design.

**Model (`model/`)**: `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` at revision
`8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c` (requester-provided; see `SOURCES_AND_LICENSES.md`), one
forward pass per trial, label = argmax over the model's own `id2label`, CPU float32, no thresholds,
no calibration, no aggregation across sentences.

## Trials and scoring

Per set: 48 full-context trials (24 items × 2 languages) + 16 single-span trials (8 items × 2).
`score.py` replays retained predictions only — it never runs a model — and refuses mismatched hashes or
inputs. It reports counts (no independence-based intervals: 24 items share 6 scenario groups, and the
languages and span trials are paired), per scenario group, per role, per class, confusion matrices,
paraphrase consistency, minimal-pair sensitivity, cross-lingual agreement, span-vs-full comparisons,
descriptive probability statistics when present, and every error.

## Pydantic Evals

Not used. The earlier study in this branch (`acquisition/pydantic_evals_offline/`) found its value is
in scoring recorded observations and diffing implementations; here a 200-line stdlib scorer over
immutable JSONL already replays everything, and adding the dependency (which imports the Pydantic AI
agent framework) would add no information.
