# Ambiguity review (completed before the freeze)

Reviewed by the fixture author before any baseline or model prediction existed. The frozen labels
are in `dev.jsonl` / `heldout.jsonl` (hashes in `freeze_manifest.json`). Later observations go to
`errata.md`; labels are not changed.

## Labeling convention

Strict three-way NLI over the *reference text alone*:

- **entailment**: every situation in which the reference is true makes the hypothesis true;
- **contradiction**: no situation makes both true (same entities, same time, same rule);
- **neutral**: otherwise. In particular, a hypothesis that drops a condition, hedge, attribution
  or source qualifier is **neutral**, not contradictory: the reference neither guarantees nor rules
  it out.

Background knowledge is limited to word meaning (a dictionary is a book; a magazine is not;
two thousand years are twenty centuries; a gallery of the museum is "in the museum"). No item
depends on mathematical, historical or encyclopedic facts.

## Retained items with residual concerns

| Item | Frozen label | Concern | Why retained |
|---|---|---|---|
| `d-modality-4`, `h-modality-4` | neutral | Colloquially, "probably will rain" / "might be finished" is sometimes read as a prediction of the event. | Strict NLI: probable or possible does not guarantee. This is exactly the hedge-dropping case under study. |
| `d-modality-3` | contradiction | "Probable rain" vs "certain no rain" mixes probability with certainty. | Probable rain and certain absence of rain cannot both be correct assessments. |
| `h-negation-4` | neutral | Readers may equate "the station recorded no snowfall" with "it did not snow". | The reference reports a record, not the weather; unrecorded snow is possible. Source-vs-fact distinction is intended. |
| `h-exception-4` | neutral | Some readers might treat magazines as covered by a books rule. | Magazines are not books; the reference is silent about them. |
| `d-exception-4` | neutral | Flash use might be considered part of "taking photographs". | Permission to photograph does not settle a separate flash rule. |
| `d-attribution-3`, `h-attribution-1/2` | contradiction | A source could in principle say two inconsistent things. | Standard NLI reading: the hypothesis misreports what that source said. |
| Span trials of `d-reference-1..3`, `h-reference-1..3` | neutral (strict) | Convention-sensitive: annotators who resolve the span's pronoun / null subject to the hypothesis entity would choose entailment or contradiction. | Kept and flagged `convention_sensitive: true`; the scorer reports them separately so no headline number depends on the convention. |

## Pre-freeze corrections

- `h-negation-1` (Spanish): "En marzo no se registró ninguna nevada **en** la estación
  meteorológica" (recorded *at* the station, by anyone) was not equivalent to the English "No
  snowfall was recorded **by** the weather station". Replaced by "Ninguna nevada fue registrada por
  la estación meteorológica en marzo." Made before any prediction existed.

## Exclusions

Nine drafts were excluded and are preserved, with reasons, in `excluded.jsonl` (never scored):
generic vs episodic hours, loan-period implicature, three pronoun drafts whose antecedent was
ambiguous in at least one language, "Roman" origin vs style, attributed modality, geometry
background knowledge, and "take home" vs "borrow".

## Paired-variant caveat

Spanish and English texts are written to be equivalent, but they are not guaranteed to be equally
difficult or to carry identical implicatures. Each item is scored once per language; per-language
results and the agreement between the two are reported, and the unit of analysis is the item
(24 per set), not the 48 sentences.
