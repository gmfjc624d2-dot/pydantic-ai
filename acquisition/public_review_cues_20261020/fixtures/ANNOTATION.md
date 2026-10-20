# Annotation guidelines for review-cue fixtures

Written before any lexicon or matching code existed. Gold spans describe what a reviewer preparing
source-grounded notes would want *pointed at*, independently of what any rule list contains, so that
the evaluation is not circular.

## What is annotated

A **gold cue** is the minimal contiguous, exact substring whose presence signals one of six review
topics in that text:

| Topic | Signals | Examples |
|---|---|---|
| `condition` | something holds only if something else does | if, unless, provided that, si, en caso de que |
| `exception` | a carve-out from a generalization | except, other than, excepto, salvo |
| `negation` | polarity is reversed or denied | not, n't, never, nobody, no, nunca, nadie, sin |
| `uncertainty` | epistemic hedging or likelihood | may, might, probably, likely, quizás, podría, al parecer |
| `attribution` | content is presented as coming from a source | according to, said, reportedly, según, dice |
| `obligation` | deontic necessity or requirement | must, have to, shall, debe, hay que, tiene que |

Permission ("can", "pueden", "se permite") is **not** a topic; it is never annotated as gold. When a
word could equally signal two topics in context (e.g. "unless": condition or exception; "should":
obligation or uncertainty; "al parecer": uncertainty or attribution), the gold lists every acceptable
topic; a prediction is topic-correct if it names at least one of them.

## Span rules

- Exact substring as written: original case, accents, composed or decomposed characters, line breaks.
- Fixed multiword expressions are one span ("a menos que", "according to", "siempre y cuando").
- Reporting verbs: the verb form only ("said", "dice"), never the speaker.
- Contracted negation: "n't" is the negation span; the modal or auxiliary before it is annotated on its
  own if it is a cue ("should" in "shouldn't").
- Overlapping gold spans are allowed when a longer expression and a shorter word are both cues
  (e.g. "does not apply to" as exception and "not" as negation).
- Scope, the governed clause, the speaker's identity and the truth of anything are **not** annotated.

## Distractors

Strings that look like a cue but are not one in context are recorded as `distractors` with a note
("May" the month, "no obstante" the concessive connective, "nada" meaning "swims", "pueden" as
permission). A tool highlight on a distractor is reported as a distracting highlight.

## Provenance

All texts are original, synthetic, harmless toy scenarios (museum, library, weather, geometry) written
for this repository by the AI assistant (Claude) during request `public-review-cues-20261020-02`; no
corpus, no copyrighted or private text. The same author wrote the guidelines, both fixture sets and the
rules, so the reserved set is not independent of the rule author (see `README.md`, "Limitations").
