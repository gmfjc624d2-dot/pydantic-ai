# Benchmark: review_cues 1.0.0 (baseline) vs 1.1.0 (Python 3.9.25, Linux-6.18.44-fc-v139-x86_64-with-glibc2.39)

find_cues() wall time per call, one fresh process per run, 3 repeats, timeout 60 s. Raw rows: measurements.jsonl; platform: platform.json. "outputs identical": every completed run of both versions produced the same output apart from tool.version and configuration_sha256.

| shape | language | code points | 1.0.0 seconds (min / median / max) | this version seconds (min / median / max) | matches | overlapping pairs | outputs identical |
|---|---|---|---|---|---|---|---|
| cue_free | en | 2,000 | 0.0010 / 0.0011 / 0.0011 | 0.0010 / 0.0010 / 0.0018 | 0 | 0 | yes |
| cue_free | en | 10,000 | 0.0050 / 0.0051 / 0.0053 | 0.0048 / 0.0048 / 0.0120 | 0 | 0 | yes |
| cue_free | en | 50,000 | 0.0242 / 0.0255 / 0.0279 | 0.0238 / 0.0243 / 0.0283 | 0 | 0 | yes |
| cue_free | en | 100,000 | 0.0471 / 0.0480 / 0.0622 | 0.0473 / 0.0484 / 0.0515 | 0 | 0 | yes |
| dense_disjoint | es | 2,000 | 0.0509 / 0.0524 / 0.0529 | 0.0065 / 0.0066 / 0.0067 | 667 | 0 | yes |
| dense_disjoint | es | 10,000 | 1.3804 / 1.3892 / 1.4581 | 0.0313 / 0.0328 / 0.0346 | 3333 | 0 | yes |
| dense_disjoint | es | 50,000 | 42.2742 / 42.4086 / 46.8083 | 0.1902 / 0.2174 / 0.2420 | 16667 | 0 | yes |
| dense_disjoint | es | 100,000 | timeout (> 60 s) | 0.3918 / 0.4152 / 0.4376 | 33333 | 0 | not compared |
| dense_nested | en | 2,000 | 0.0292 / 0.0314 / 0.0373 | 0.0051 / 0.0052 / 0.0053 | 500 | 250 | yes |
| dense_nested | en | 10,000 | 0.8623 / 0.8883 / 0.9456 | 0.0276 / 0.0292 / 0.0352 | 2500 | 1250 | yes |
| dense_nested | en | 50,000 | 25.8937 / 28.2046 / 29.2711 | 0.1486 / 0.1502 / 0.1754 | 12500 | 6250 | yes |
| dense_nested | en | 100,000 | timeout (> 60 s) | 0.2931 / 0.3411 / 0.3427 | 25000 | 12500 | not compared |
| mixed_sentences | es+en | 2,000 | 0.0054 / 0.0054 / 0.0058 | 0.0031 / 0.0033 / 0.0035 | 142 | 25 | yes |
| mixed_sentences | es+en | 10,000 | 0.0596 / 0.0602 / 0.0678 | 0.0161 / 0.0167 / 0.0172 | 654 | 95 | yes |
| mixed_sentences | es+en | 50,000 | 1.8219 / 1.8541 / 1.9073 | 0.0797 / 0.0838 / 0.0954 | 3368 | 541 | yes |
| mixed_sentences | es+en | 100,000 | 7.6718 / 8.1596 / 8.4754 | 0.1724 / 0.1758 / 0.1761 | 6715 | 1066 | yes |
