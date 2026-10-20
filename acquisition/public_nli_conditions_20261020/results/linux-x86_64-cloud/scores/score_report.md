# Re-scored results (replayed from retained predictions; no inference)

Fixtures: freeze manifest hashes {"dev.jsonl": "6f56dabcea2fa9e1a1815bd8960cfcb976be3f949ff10c0fcc1df17615bc58d8", "heldout.jsonl": "8cbe96a7a06b7977b3af534b6e58949034f70f96ee15171ed8b4efc046c17a74", "excluded.jsonl": "e0a5f93654b2ade7af8205d270ff0c46a63991b8ba283e87b3b87ecf21a1c631"}. Errata: `fixtures/errata.json` (sha256 9a86a273b6b8c611…), flags only.

## lexical-baseline/v1 — dev

Trials scored 64/64; non-ok: none.
Counts only; trials are paired and grouped, so no independence-based interval is given.

| Full-context subset | items | es | en | items correct in both |
|---|---|---|---|---|
| original_full_set | 24 | 14/24 | 14/24 | 14/24 |
| excluding_disputed | 24 | 14/24 | 14/24 | 14/24 |
| only:convention_coherent_source | 1 | 0/1 | 0/1 | 0/1 |
| only:convention_standing_rule | 2 | 0/2 | 0/2 | 0/2 |
| only:pre_freeze_residual_concern | 3 | 2/3 | 2/3 | 2/3 |
| assumption_light_core | 21 | 14/21 | 14/21 | 14/21 |

| Scenario group | es | en | items: gold → pred es / en |
|---|---|---|---|
| d-attribution | 2/4 | 2/4 | 1:ent→ent/ent; 2:ent→ent/ent; 3:con→ent/ent*; 4:neu→ent/ent |
| d-condition | 1/4 | 1/4 | 1:con→ent/ent*; 2:con→ent/ent*; 3:ent→ent/ent; 4:neu→ent/ent |
| d-exception | 2/4 | 2/4 | 1:ent→con/neu; 2:ent→neu/neu; 3:con→con/con; 4:neu→neu/neu* |
| d-modality | 3/4 | 3/4 | 1:ent→ent/ent; 2:ent→ent/ent; 3:con→con/con*; 4:neu→ent/ent* |
| d-negation | 3/4 | 3/4 | 1:con→con/con; 2:con→con/con; 3:ent→ent/ent; 4:neu→ent/ent |
| d-reference | 3/4 | 3/4 | 1:ent→ent/ent; 2:ent→ent/ent; 3:con→con/con; 4:neu→ent/ent |

`*` = item carries an errata flag. Abbreviations: ent/neu/con.

| Paired diagnostic | count |
|---|---|
| paraphrase consistency (base vs paraphrase, per group × language) | 11/12 |
| minimal-pair sensitivity (base vs meaning change differ) | 7/12 |
| cross-lingual agreement (es vs en, per item) | 23/24 |
| role base (es+en trials) | 8/12 |
| role paraphrase (es+en trials) | 8/12 |
| role meaning_change (es+en trials) | 10/12 |
| role missing_qualifier (es+en trials) | 2/12 |

| Class (es+en trials) | support | predicted | correct | precision | recall |
|---|---|---|---|---|---|
| entailment | 20 | 32 | 16 | 0.5 | 0.8 |
| neutral | 12 | 5 | 2 | 0.4 | 0.1667 |
| contradiction | 16 | 11 | 10 | 0.9091 | 0.625 |

Confusion (rows gold, columns predicted): {"entailment": {"entailment": 16, "neutral": 3, "contradiction": 1}, "neutral": {"entailment": 10, "neutral": 2, "contradiction": 0}, "contradiction": {"entailment": 6, "neutral": 0, "contradiction": 10}}

| Single-span trials | count |
|---|---|
| correct vs span label, es | 6/8 |
| correct vs span label, en | 3/8 |
| excluding convention-sensitive spans | 5/10 |
| convention-sensitive spans only | 4/6 |
| span prediction equals full-reference label | 6/16 |

Errors (27):

| trial | role | gold | pred | flags |
|---|---|---|---|---|
| `d-condition-1/es/full` | base | contradiction | entailment | convention_standing_rule |
| `d-condition-1/en/full` | base | contradiction | entailment | convention_standing_rule |
| `d-condition-2/es/full` | paraphrase | contradiction | entailment | convention_standing_rule |
| `d-condition-2/en/full` | paraphrase | contradiction | entailment | convention_standing_rule |
| `d-condition-4/es/full` | missing_qualifier | neutral | entailment |  |
| `d-condition-4/en/full` | missing_qualifier | neutral | entailment |  |
| `d-exception-1/es/full` | base | entailment | contradiction |  |
| `d-exception-1/en/full` | base | entailment | neutral |  |
| `d-exception-1/en/span` | base | entailment | neutral |  |
| `d-exception-2/es/full` | paraphrase | entailment | neutral |  |
| `d-exception-2/es/span` | paraphrase | entailment | neutral |  |
| `d-exception-2/en/full` | paraphrase | entailment | neutral |  |
| `d-exception-2/en/span` | paraphrase | entailment | neutral |  |
| `d-exception-3/en/span` | meaning_change | entailment | neutral |  |
| `d-negation-4/es/full` | missing_qualifier | neutral | entailment |  |
| `d-negation-4/en/full` | missing_qualifier | neutral | entailment |  |
| `d-modality-4/es/full` | missing_qualifier | neutral | entailment | pre_freeze_residual_concern |
| `d-modality-4/en/full` | missing_qualifier | neutral | entailment | pre_freeze_residual_concern |
| `d-attribution-3/es/full` | meaning_change | contradiction | entailment | convention_coherent_source |
| `d-attribution-3/en/full` | meaning_change | contradiction | entailment | convention_coherent_source |
| `d-attribution-4/es/full` | missing_qualifier | neutral | entailment |  |
| `d-attribution-4/en/full` | missing_qualifier | neutral | entailment |  |
| `d-reference-1/es/span` | base | neutral | entailment | convention-sensitive span |
| `d-reference-1/en/span` | base | neutral | entailment | convention-sensitive span |
| `d-reference-4/es/full` | missing_qualifier | neutral | entailment |  |
| `d-reference-4/en/full` | missing_qualifier | neutral | entailment |  |
| `d-reference-4/en/span` | missing_qualifier | neutral | entailment |  |

## lexical-baseline/v1 — heldout

Trials scored 64/64; non-ok: none.
Counts only; trials are paired and grouped, so no independence-based interval is given.

| Full-context subset | items | es | en | items correct in both |
|---|---|---|---|---|
| original_full_set | 24 | 8/24 | 11/24 | 8/24 |
| excluding_disputed | 23 | 7/23 | 10/23 | 7/23 |
| only:convention_coherent_source | 2 | 0/2 | 0/2 | 0/2 |
| only:disputed | 1 | 1/1 | 1/1 | 1/1 |
| only:pre_freeze_residual_concern | 3 | 1/3 | 1/3 | 1/3 |
| assumption_light_core | 21 | 7/21 | 10/21 | 7/21 |

| Scenario group | es | en | items: gold → pred es / en |
|---|---|---|---|
| h-attribution | 1/4 | 1/4 | 1:con→ent/ent*; 2:con→ent/ent*; 3:ent→ent/ent; 4:neu→ent/ent |
| h-condition | 1/4 | 1/4 | 1:ent→ent/ent; 2:ent→con/con; 3:con→ent/ent; 4:neu→ent/ent |
| h-exception | 1/4 | 1/4 | 1:con→ent/ent; 2:con→ent/ent; 3:ent→ent/ent; 4:neu→ent/ent* |
| h-modality | 1/4 | 2/4 | 1:con→ent/ent; 2:con→ent/con; 3:ent→ent/ent; 4:neu→ent/ent* |
| h-negation | 2/4 | 4/4 | 1:ent→con/ent; 2:ent→ent/ent*; 3:con→ent/con; 4:neu→neu/neu* |
| h-reference | 2/4 | 2/4 | 1:ent→ent/ent; 2:ent→ent/ent; 3:con→ent/ent; 4:neu→ent/ent |

`*` = item carries an errata flag. Abbreviations: ent/neu/con.

| Paired diagnostic | count |
|---|---|
| paraphrase consistency (base vs paraphrase, per group × language) | 8/12 |
| minimal-pair sensitivity (base vs meaning change differ) | 2/12 |
| cross-lingual agreement (es vs en, per item) | 21/24 |
| role base (es+en trials) | 5/12 |
| role paraphrase (es+en trials) | 5/12 |
| role meaning_change (es+en trials) | 7/12 |
| role missing_qualifier (es+en trials) | 2/12 |

| Class (es+en trials) | support | predicted | correct | precision | recall |
|---|---|---|---|---|---|
| entailment | 18 | 41 | 15 | 0.3659 | 0.8333 |
| neutral | 12 | 2 | 2 | 1.0 | 0.1667 |
| contradiction | 18 | 5 | 2 | 0.4 | 0.1111 |

Confusion (rows gold, columns predicted): {"entailment": {"entailment": 15, "neutral": 0, "contradiction": 3}, "neutral": {"entailment": 10, "neutral": 2, "contradiction": 0}, "contradiction": {"entailment": 16, "neutral": 0, "contradiction": 2}}

| Single-span trials | count |
|---|---|
| correct vs span label, es | 5/8 |
| correct vs span label, en | 4/8 |
| excluding convention-sensitive spans | 5/10 |
| convention-sensitive spans only | 4/6 |
| span prediction equals full-reference label | 2/16 |

Errors (36):

| trial | role | gold | pred | flags |
|---|---|---|---|---|
| `h-condition-2/es/full` | paraphrase | entailment | contradiction |  |
| `h-condition-2/en/full` | paraphrase | entailment | contradiction |  |
| `h-condition-3/es/full` | meaning_change | contradiction | entailment |  |
| `h-condition-3/en/full` | meaning_change | contradiction | entailment |  |
| `h-condition-4/es/full` | missing_qualifier | neutral | entailment |  |
| `h-condition-4/en/full` | missing_qualifier | neutral | entailment |  |
| `h-exception-1/es/full` | base | contradiction | entailment |  |
| `h-exception-1/en/full` | base | contradiction | entailment |  |
| `h-exception-2/es/full` | paraphrase | contradiction | entailment |  |
| `h-exception-2/en/full` | paraphrase | contradiction | entailment |  |
| `h-exception-2/en/span` | paraphrase | entailment | neutral |  |
| `h-exception-4/es/full` | missing_qualifier | neutral | entailment | pre_freeze_residual_concern |
| `h-exception-4/es/span` | missing_qualifier | neutral | entailment | pre_freeze_residual_concern |
| `h-exception-4/en/full` | missing_qualifier | neutral | entailment | pre_freeze_residual_concern |
| `h-exception-4/en/span` | missing_qualifier | neutral | entailment | pre_freeze_residual_concern |
| `h-negation-1/es/full` | base | entailment | contradiction |  |
| `h-negation-3/es/full` | meaning_change | contradiction | entailment |  |
| `h-modality-1/es/full` | base | contradiction | entailment |  |
| `h-modality-1/en/full` | base | contradiction | entailment |  |
| `h-modality-2/es/full` | paraphrase | contradiction | entailment |  |
| `h-modality-4/es/full` | missing_qualifier | neutral | entailment | pre_freeze_residual_concern |
| `h-modality-4/en/full` | missing_qualifier | neutral | entailment | pre_freeze_residual_concern |
| `h-attribution-1/es/full` | base | contradiction | entailment | convention_coherent_source |
| `h-attribution-1/en/full` | base | contradiction | entailment | convention_coherent_source |
| `h-attribution-2/es/full` | paraphrase | contradiction | entailment | convention_coherent_source |
| `h-attribution-2/en/full` | paraphrase | contradiction | entailment | convention_coherent_source |
| `h-attribution-4/es/full` | missing_qualifier | neutral | entailment |  |
| `h-attribution-4/en/full` | missing_qualifier | neutral | entailment |  |
| `h-reference-1/es/span` | base | neutral | entailment | convention-sensitive span |
| `h-reference-1/en/span` | base | neutral | entailment | convention-sensitive span |
| `h-reference-3/es/full` | meaning_change | contradiction | entailment |  |
| `h-reference-3/en/full` | meaning_change | contradiction | entailment |  |
| `h-reference-4/es/full` | missing_qualifier | neutral | entailment |  |
| `h-reference-4/es/span` | missing_qualifier | neutral | entailment |  |
| `h-reference-4/en/full` | missing_qualifier | neutral | entailment |  |
| `h-reference-4/en/span` | missing_qualifier | neutral | entailment |  |
