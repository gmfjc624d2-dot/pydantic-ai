# Evaluation: dev (Linux run; counts only)

```json
{
  "set": "dev",
  "tool_version": "1.0.0",
  "ruleset_canonical_sha256": "b33ac9e99a5177e317ab7ab274a7ca6821491cb912f10264b9a50a3a5726af63",
  "fixtures_sha256": "d9702afaf321826fe81a0d21f8875ec32292683f4a0a3df0636f38ea4f10cf77",
  "items": 24,
  "gold_spans": 48,
  "gold_hit": 48,
  "highlights": 53,
  "highlight_classes": {
    "on_distractor": 2,
    "redundant_nested": 3,
    "true_positive": 48
  },
  "by_language": {
    "en": {
      "gold": 23,
      "gold_hit": 23,
      "highlights": 27,
      "true_positive_highlights": 23
    },
    "es": {
      "gold": 25,
      "gold_hit": 25,
      "highlights": 26,
      "true_positive_highlights": 25
    }
  },
  "by_topic_gold_recall": {
    "condition": {
      "gold": 9,
      "hit": 9
    },
    "exception": {
      "gold": 7,
      "hit": 7
    },
    "negation": {
      "gold": 14,
      "hit": 14
    },
    "uncertainty": {
      "gold": 7,
      "hit": 7
    },
    "attribution": {
      "gold": 9,
      "hit": 9
    },
    "obligation": {
      "gold": 5,
      "hit": 5
    }
  },
  "by_cue_origin": {
    "in_dev_gold": {
      "gold": 48,
      "hit": 48
    },
    "in_annotation_spec": {
      "gold": 0,
      "hit": 0
    },
    "closed_class_lexicon_only": {
      "gold": 0,
      "hit": 0
    },
    "not_in_lexicon": {
      "gold": 0,
      "hit": 0
    }
  },
  "format_feature_items": {
    "d-en-06": {
      "features": [
        "nbsp_inside_multiword_cue"
      ],
      "all_gold_hit": true
    },
    "d-en-11": {
      "features": [
        "upper_case"
      ],
      "all_gold_hit": true
    },
    "d-en-12": {
      "features": [
        "emoji_vs16_before_cue",
        "crlf"
      ],
      "all_gold_hit": true
    },
    "d-es-01": {
      "features": [
        "word_containing_cue_letters"
      ],
      "all_gold_hit": true
    },
    "d-es-09": {
      "features": [
        "nbsp_inside_multiword_cue"
      ],
      "all_gold_hit": true
    },
    "d-es-11": {
      "features": [
        "upper_case"
      ],
      "all_gold_hit": true
    },
    "d-es-12": {
      "features": [
        "decomposed_accent_in_cue",
        "decomposed_non_cue"
      ],
      "all_gold_hit": true
    }
  },
  "empty_gold_items": {}
}
```

## Omissions (gold spans without an exact, topic-compatible highlight)

| item | span | topics | reason |
|---|---|---|---|

## Highlights that are not true positives

| item | highlight | rule | class | note |
|---|---|---|---|---|
| d-en-04 | `'except'` [23,29) | en.exception.except | redundant_nested |  |
| d-en-06 | `'may'` [4,7) | en.uncertainty.may | on_distractor | permission, not a configured topic |
| d-en-10 | `'except'` [35,41) | en.exception.except | redundant_nested |  |
| d-en-12 | `'if'` [63,65) | en.condition.if | redundant_nested |  |
| d-es-04 | `'salvo'` [64,69) | es.exception.salvo | on_distractor | "a salvo" means "safe" |
