# Evaluation: reserved (Linux run; counts only)

```json
{
  "set": "reserved",
  "tool_version": "1.0.0",
  "ruleset_canonical_sha256": "b33ac9e99a5177e317ab7ab274a7ca6821491cb912f10264b9a50a3a5726af63",
  "fixtures_sha256": "eecc0e2bfe0f68fdd1716501949efd447172278ede8304c9aa5a2b8929842ae3",
  "items": 24,
  "gold_spans": 42,
  "gold_hit": 35,
  "highlights": 41,
  "highlight_classes": {
    "on_distractor": 5,
    "partial_shorter_than_gold": 1,
    "true_positive": 35
  },
  "by_language": {
    "en": {
      "gold": 23,
      "gold_hit": 20,
      "highlights": 21,
      "true_positive_highlights": 20
    },
    "es": {
      "gold": 19,
      "gold_hit": 15,
      "highlights": 20,
      "true_positive_highlights": 15
    }
  },
  "by_topic_gold_recall": {
    "condition": {
      "gold": 8,
      "hit": 4
    },
    "exception": {
      "gold": 5,
      "hit": 3
    },
    "negation": {
      "gold": 11,
      "hit": 11
    },
    "uncertainty": {
      "gold": 9,
      "hit": 7
    },
    "attribution": {
      "gold": 8,
      "hit": 8
    },
    "obligation": {
      "gold": 6,
      "hit": 5
    }
  },
  "by_cue_origin": {
    "in_dev_gold": {
      "gold": 25,
      "hit": 25
    },
    "in_annotation_spec": {
      "gold": 10,
      "hit": 10
    },
    "closed_class_lexicon_only": {
      "gold": 1,
      "hit": 0
    },
    "not_in_lexicon": {
      "gold": 6,
      "hit": 0
    }
  },
  "format_feature_items": {
    "r-en-03": {
      "features": [
        "emoji_before_cue"
      ],
      "all_gold_hit": true
    },
    "r-en-06": {
      "features": [
        "crlf_inside_multiword_cue"
      ],
      "all_gold_hit": true
    },
    "r-es-10": {
      "features": [
        "decomposed_accent_in_cue"
      ],
      "all_gold_hit": true
    }
  },
  "empty_gold_items": {
    "r-en-12": 0,
    "r-es-12": 0
  }
}
```

## Omissions (gold spans without an exact, topic-compatible highlight)

| item | span | topics | reason |
|---|---|---|---|
| r-en-07 | `'should'` | obligation, uncertainty | no highlight |
| r-en-09 | `'Assuming'` | condition | no highlight |
| r-en-11 | `'does not apply to'` | exception | partially or wrongly highlighted |
| r-es-01 | `'probablemente'` | uncertainty | no highlight |
| r-es-02 | `'salvo que'` | exception, condition | partially or wrongly highlighted |
| r-es-06 | `'siempre y cuando'` | condition | no highlight |
| r-es-08 | `'En el supuesto de que'` | condition | no highlight |

## Highlights that are not true positives

| item | highlight | rule | class | note |
|---|---|---|---|---|
| r-en-08 | `'May'` [3,6) | en.uncertainty.may | on_distractor | month name, not a modal |
| r-es-02 | `'salvo'` [46,51) | es.exception.salvo | partial_shorter_than_gold |  |
| r-es-06 | `'pueden'` [13,19) | es.uncertainty.poder | on_distractor | permission, not a configured topic |
| r-es-07 | `'nada'` [8,12) | es.negation.pronoun | on_distractor | verb "nadar" (swims), not the negative pronoun |
| r-es-11 | `'no'` [44,46) | es.negation.no | on_distractor | concessive connective ("nevertheless"), not negation |
| r-es-11 | `'pueden'` [71,77) | es.uncertainty.poder | on_distractor | permission, not a configured topic |
