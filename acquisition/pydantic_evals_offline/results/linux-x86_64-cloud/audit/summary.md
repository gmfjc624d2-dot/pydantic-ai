| run | completed | inet connect attempts | processes spawned (execve) | fs writes outside harness/worker | env keys read (OTEL/LOGFIRE/other) | canaries in local sink | canaries in spans |
|---|---|---|---|---|---|---|---|
| A | yes (4 cases, 1 failure) | none | none | {'TMPDIR (other):openat': 1, 'TMPDIR (other):unlink': 1} | 1/0/11 | n/a | n/a |
| B | yes (4 cases, 1 failure) | none | none | {'TMPDIR (other):openat': 1, 'TMPDIR (other):unlink': 1} | 9/32/13 | n/a | n/a |
| C | yes (4 cases, 1 failure) | none | git rev-parse HEAD | {'TMPDIR (other):openat': 1, 'TMPDIR (other):unlink': 1} | 29/32/14 | n/a | n/a |
| D-A-otel | yes (4 cases, 1 failure) | none | none | {'TMPDIR (other):openat': 1, 'TMPDIR (other):unlink': 1} | 1/0/11 | 0 req, no canaries | n/a |
| D-B-otel | yes (4 cases, 1 failure) | none | none | {'TMPDIR (other):openat': 1, 'TMPDIR (other):unlink': 1} | 9/32/13 | 0 req, no canaries | n/a |
| D-B-token | yes (4 cases, 1 failure) | none | none | {'TMPDIR (other):openat': 1, 'TMPDIR (other):unlink': 1} | 9/32/12 | n/a | n/a |
| D-C-otel | yes (4 cases, 1 failure) | 127.0.0.1:4318 (-1) | git rev-parse HEAD | {'TMPDIR (other):openat': 1, 'TMPDIR (other):unlink': 1} | 69/32/14 | 1 req, {'INPUT': 5, 'META': 5, 'EXPECTED': 5, 'OUTPUT': 4, 'ERROR': 6} | n/a |
| D-C-token | yes (4 cases, 1 failure) | none | git rev-parse HEAD | {'TMPDIR (other):openat': 1, 'TMPDIR (other):unlink': 1} | 29/32/13 | n/a | n/a |
| E-memory | yes (4 cases, 1 failure) | none | git rev-parse HEAD | {'TMPDIR (other):openat': 1, 'TMPDIR (other):unlink': 1} | 29/32/14 | n/a | ['error', 'expected', 'input', 'metadata', 'output'] |
