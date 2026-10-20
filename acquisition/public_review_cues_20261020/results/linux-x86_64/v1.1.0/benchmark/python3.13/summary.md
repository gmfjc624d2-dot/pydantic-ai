# Benchmark: review_cues 1.0.0 (baseline) vs 1.1.0 (Python 3.13.16, Linux-6.18.44-fc-v139-x86_64-with-glibc2.39)

find_cues() wall time per call, one fresh process per run, 3 repeats, timeout 60 s. Raw rows: measurements.jsonl; platform: platform.json. "outputs identical": every completed run of both versions produced the same output apart from tool.version and configuration_sha256.

| shape | language | code points | 1.0.0 seconds (min / median / max) | this version seconds (min / median / max) | matches | overlapping pairs | outputs identical |
|---|---|---|---|---|---|---|---|
| cue_free | en | 2,000 | 0.0008 / 0.0008 / 0.0009 | 0.0008 / 0.0008 / 0.0010 | 0 | 0 | yes |
| cue_free | en | 10,000 | 0.0039 / 0.0041 / 0.0077 | 0.0040 / 0.0041 / 0.0053 | 0 | 0 | yes |
| cue_free | en | 50,000 | 0.0191 / 0.0194 / 0.0196 | 0.0194 / 0.0210 / 0.0225 | 0 | 0 | yes |
| cue_free | en | 100,000 | 0.0381 / 0.0388 / 0.0391 | 0.0383 / 0.0384 / 0.0447 | 0 | 0 | yes |
| dense_disjoint | es | 2,000 | 0.0582 / 0.0592 / 0.0777 | 0.0073 / 0.0075 / 0.0077 | 667 | 0 | yes |
| dense_disjoint | es | 10,000 | 1.3777 / 1.4229 / 1.5737 | 0.0293 / 0.0315 / 0.0335 | 3333 | 0 | yes |
| dense_disjoint | es | 50,000 | 42.8395 / 43.1106 / 46.5618 | 0.1343 / 0.1374 / 0.1631 | 16667 | 0 | yes |
| dense_disjoint | es | 100,000 | timeout (> 60 s) | 0.3257 / 0.3361 / 0.3439 | 33333 | 0 | not compared |
| dense_nested | en | 2,000 | 0.0302 / 0.0314 / 0.0318 | 0.0042 / 0.0044 / 0.0046 | 500 | 250 | yes |
| dense_nested | en | 10,000 | 0.8204 / 0.8693 / 0.9354 | 0.0232 / 0.0240 / 0.0262 | 2500 | 1250 | yes |
| dense_nested | en | 50,000 | 21.6402 / 23.5521 / 24.6915 | 0.1178 / 0.1203 / 0.2197 | 12500 | 6250 | yes |
| dense_nested | en | 100,000 | timeout (> 60 s) | 0.2311 / 0.2475 / 0.2511 | 25000 | 12500 | not compared |
| mixed_sentences | es+en | 2,000 | 0.0049 / 0.0050 / 0.0062 | 0.0029 / 0.0030 / 0.0032 | 142 | 25 | yes |
| mixed_sentences | es+en | 10,000 | 0.0616 / 0.0620 / 0.0629 | 0.0158 / 0.0160 / 0.0203 | 654 | 95 | yes |
| mixed_sentences | es+en | 50,000 | 1.6294 / 1.6827 / 1.6895 | 0.0702 / 0.0753 / 0.0770 | 3368 | 541 | yes |
| mixed_sentences | es+en | 100,000 | 6.2353 / 6.8154 / 6.8891 | 0.1444 / 0.1591 / 0.1675 | 6715 | 1066 | yes |
