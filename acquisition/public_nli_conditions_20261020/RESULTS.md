# Results (Linux x86_64 cloud session, 2026-10-20) and failure analysis

**Status.** The lexical baseline ran on both frozen sets. **The model did not run**: `huggingface.co`
is denied by this session's egress policy, no local copy of the weights exists in this session, and no
mirror or relay was used. There is no model result, positive or negative, anywhere in this directory.

Full replayed report: `results/linux-x86_64-cloud/scores/score_report.md` (and `.json`). Counts only:
each set's 24 items come from 6 scenario groups of 4 related variants and Spanish/English are paired,
so no independence-based interval is given and none of these numbers generalizes beyond the fixtures.

## Lexical baseline (τ = 0.60, fitted on dev only)

| Full-context subset | dev es | dev en | held-out es | held-out en |
|---|---|---|---|---|
| original full set (24 items, unchanged labels) | 14/24 | 14/24 | 8/24 | 11/24 |
| excluding `disputed` (`h-negation-2`) | 14/24 | 14/24 | 7/23 | 10/23 |
| only `convention_standing_rule` | 0/2 | 0/2 | — | — |
| only `convention_coherent_source` | 0/1 | 0/1 | 0/2 | 0/2 |
| assumption-light core | 14/21 | 14/21 | 7/21 | 10/21 |

| Paired diagnostic | dev | held-out |
|---|---|---|
| `missing_qualifier` trials correct (should be neutral) | 2/12 | 2/12 |
| paraphrase consistency (base vs paraphrase) | 11/12 | 8/12 |
| minimal-pair sensitivity (base vs meaning change differ) | 7/12 | 2/12 |
| cross-lingual agreement (per item) | 23/24 | 21/24 |
| span prediction equals full-reference label | 6/16 | 2/16 |

| Scenario group (4 items; correct es / en) | dev | held-out |
|---|---|---|
| attribution | 2 / 2 | 1 / 1 |
| condition | 1 / 1 | 1 / 1 |
| exception | 2 / 2 | 1 / 1 |
| modality | 3 / 3 | 1 / 2 |
| negation | 3 / 3 | 2 / 4 |
| reference | 3 / 3 | 2 / 2 |

Every error (27 dev, 36 held-out trials, including span trials) is listed with its features in the
score report.

## Failure analysis (baseline; read from the recorded features)

1. **Dropped qualifiers read as entailment.** Removing a condition, hedge, attribution or source
   qualifier keeps almost every content word, so coverage stays ≥ τ: 10 of 12 neutral full-context
   trials per set were predicted entailment. Lexical overlap is not entailment.
2. **Contradiction without a negation word or digit is invisible.** "stays on" vs "is switched off"
   (`d-condition-1/2`), "impossible" vs "might" (`h-modality-1`), a swapped source (`d-attribution-3`,
   `h-attribution-1/2`), an excepted category (`h-exception-1/2`) and number words ("three"/"four",
   "forty"/"four hundred": `h-condition-3`, `h-reference-3`) keep high overlap and no cue change →
   entailment instead of contradiction. The converse of an "only if" rule (`h-condition-4`, neutral)
   is likewise read as entailment.
3. **Spanish negative concord breaks parity.** "no registró **ninguna** nevada" carries two negation
   cues where the English has one, so the parity rule flips `h-negation-1/es` to contradiction and
   `h-negation-3/es` to entailment, while the English versions are correct; likewise "no puede … de
   ningún modo" (`h-modality-2/es`). A multilingual pipeline cannot reuse an English negation heuristic.
4. **Spans: overlap "resolves" pronouns and ignores exceptions.** With only "It was made in 1850." the
   baseline predicts entailment for "The telescope was made in 1850." (strict label neutral), and with
   only the general-rule sentence it predicts entailment for the dictionaries — which is the span label
   but the opposite of the full-reference label. Only 2 of 16 held-out span predictions matched the
   full-reference label: span selection, not the classifier, decides these cases.
5. **Tokenization artifacts.** English possessives produce a stray `s` token ("map's"), lowering
   coverage for some English trials and creating spurious neutrals.
6. **Dev-to-held-out drop** (14 → 8–11 of 24) reflects the held-out set's harder composition (more
   contradiction bases, "only if", negative concord), not a tuning leak: τ came from dev alone and the
   held-out file was only read once to write predictions.

## Model: blocked, not failed

Executed in this session for the model path: one `fetch_model.py` attempt at revision `8adb042d…`
(`ProxyError: 403 Forbidden` at `model_info`, logged in `results/linux-x86_64-cloud/model-attempts/attempts.jsonl`,
not retried); one `verify_local_model.py` call recording that no local asset directory exists here;
the torch-free harness self-test (all checks pass); dependency resolution (not installation).
Negative network evidence, verbatim from the egress proxy, is in `results/linux-x86_64-cloud/network_evidence.json`.

## Smallest next test that could change the decision

On a machine that already holds the requester-recovered files: `verify_local_model.py` against
`model/expected/requester_metadata_8adb042d.json`, then one CPU float32 `run_model.py` inside a network
namespace, then `score.py` — about 128 forward passes, no download. Pre-registered reading, fixed now
before any model output exists:

- **Worth a larger, independently written test** if, on held-out full-context trials in *both*
  languages, the model gets most `missing_qualifier` trials neutral (baseline: 2/12) and beats the
  baseline on the assumption-light core, with no refusals and identical logits on its built-in re-run.
- **Not useful for this review task** if `missing_qualifier` trials are mostly predicted entailment —
  the baseline's failure — whatever its other scores.
- Either way, the result covers only these synthetic fixtures; it says nothing about calibration,
  other domains, or long documents, and the model output stays advisory.
