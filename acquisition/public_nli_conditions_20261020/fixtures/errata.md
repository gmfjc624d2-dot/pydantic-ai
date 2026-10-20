# Errata and qualifications (appended after the freeze; labels unchanged)

Frozen labels live in commit `733b7f763de04edcfeb33d12be90be145185e5c9` and are never edited. These
errata only add flags (machine-readable in `errata.json`, which the scorer reads) and qualify how
results may be read. Every report keeps the original full-set score next to any subset.

Timeline: freeze commit pushed → lexical baseline fitted on dev and run on both sets (local) →
independent requester review of the freeze commit, made without seeing any per-item prediction →
these errata. No model prediction existed at any point.

1. **`h-negation-2` — disputed.** "In March, the weather station recorded no snow at all" is not a
   strict paraphrase of "did not record any snowfall": a station can record existing snow depth while
   recording no new snowfall (same in Spanish: "no registró nada de nieve" vs "ninguna nevada").
   The frozen label (entailment) is kept; results are shown with and without the item.
2. **`d-condition-1`, `d-condition-2` — standing-rule convention.** The `REVIEW.md` definition ("no
   situation makes both true") does not by itself make "if below zero, switched off" contradict "if
   below zero, stays on": if the temperature never drops below zero, both conditionals hold
   vacuously. The contradiction label assumes a standing rule whose condition can occur. Reported
   separately; not presented as assumption-free logical contradiction.
3. **`d-attribution-3`, `h-attribution-1`, `h-attribution-2` — coherent-source convention.** The
   contradiction label assumes a coherent source and a single reporting event (this was already a
   residual concern in `REVIEW.md`). Reported separately.
4. **Pre-freeze residual concerns** (`d-modality-3`, `d-modality-4`, `h-modality-4`, `h-negation-4`,
   `h-exception-4`, `d-exception-4`) are listed separately for inspection but stay in all headline
   counts, because their status was registered before any prediction existed.
5. **Not independent.** Each set's 24 items come from 6 scenario groups of 4 related variants;
   Spanish and English are paired variants; span trials reuse items. No independence-based
   confidence interval is reported. Results are counts, broken down by scenario group, with every
   error listed.
6. **Deliberately not acted on.** `h-modality-1/2` ("might" vs "impossible") also rely on a shared
   epistemic-state reading. This was noticed by the fixture author after the lexical-baseline
   predictions existed locally, so no subset flag was added (post-hoc subset selection); the items
   remain in every count.
