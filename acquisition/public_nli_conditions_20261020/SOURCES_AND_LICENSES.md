# Sources, identities and license notes

Each fact is labeled by how it was obtained: **verified** (checked by this session against bytes or
code), **requester-provided** (relayed in the request, not observed by this session), **to verify**
(expected, not yet confirmed), or **blocked** (could not be obtained here).

## Model: `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`

| Fact | Value | Status |
|---|---|---|
| Revision | `8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c` | requester-provided |
| Visibility / gating | public, ungated | requester-provided |
| License (model card metadata) | MIT | requester-provided |
| Architecture | `DebertaV2ForSequenceClassification` | requester-provided |
| Label order (`config.id2label`) | 0 entailment, 1 neutral, 2 contradiction | requester-provided; the runner reads it from `config.json` at run time and refuses anything else |
| `max_position_embeddings` | 512 | requester-provided; runner limit = min(tokenizer limit, this) |
| `config.torch_dtype` | float16 — but the card warns FP16 is unsupported | requester-provided; runner forces and asserts CPU float32 |
| Weights | `model.safetensors`, 557,652,046 bytes, SHA-256 `65af59b1ff4450b09ecbf13ca35c840dbf038b26ff8e10e5ea89ca724828ed1e` (Hub LFS) | requester-provided |
| Tokenizer | `spm.model` 4,305,025 bytes, SHA-256 `13c8d666d62a7bc4ac8f040aab68e942c861f93303156cc28f5c7e885d86d6e3`; `tokenizer.json` 16,331,396 bytes, SHA-256 `3aca3ce69a0a35aeb144a52c4f1d41c4246b8785f8f398315cc8fb6b24057810` | requester-provided |
| Loading path | `AutoTokenizer` / `AutoModelForSequenceClassification`, `local_files_only=True`, `use_safetensors=True`, `trust_remote_code=False`, `dtype=float32` | implemented; transformers 5.19.0 source statically confirmed to accept these arguments (it ignores `use_fast` and always uses the tokenizers-backed class) |
| Hub metadata, card text, file bytes | — | **blocked**: `huggingface.co` denied by this session's egress policy (curl CONNECT 403; documentation reader DNS failure; `fetch_model.py` `ProxyError 403`) |
| Base model `microsoft/mdeberta-v3-base` (MIT); training data MNLI + XNLI; XNLI's own license CC BY-NC 4.0 | — | **to verify** from the card and the dataset pages before any use beyond research |

Machine-readable copy: `model/expected/requester_metadata_8adb042d.json`. `model/verify_local_model.py`
checks a local directory against it before `run_model.py` will load anything.

**License note (not legal advice).** An MIT-licensed model card does not settle the terms of its
training data. If, as expected, the model was fine-tuned on XNLI data distributed under CC BY-NC 4.0,
non-research or commercial use deserves a separate review. Weights and caches are never committed.

## SummaC (`tingofurro/summac`) — verified from source

Commit `c1f3da93cd074c24d8033eb27a88b5a7cc5c08fa` (2025-01-30), Apache-2.0 (`LICENSE`). Laban et al.,
"SummaC: Re-Visiting NLI-based Models for Inconsistency Detection in Summarization", TACL 10 (2022).
What it does: splits document and summary (sentence/paragraph/…), scores every (document chunk,
summary chunk) pair with an English NLI model, and aggregates: SummaC-ZS takes the max entailment
minus max contradiction per summary chunk, then the mean; SummaC-Conv learns a histogram-based
1-D model over the score matrix. Limitations relevant here, read in `summac/model_summac.py`,
`summac/benchmark.py`, `summac/utils_scorer.py`:

1. **Silent truncation**: pairs are encoded with `truncation=True, max_length=500,
   truncation_strategy="only_first"` — long premises are cut without notice (this study refuses instead).
2. **Sentence filtering**: NLTK `sent_tokenize` (English punkt by default) and `len(sent) > 10` drop
   short sentences such as "No." or "It is closed." before scoring.
3. **Chunk independence**: each summary chunk is scored against each document chunk separately; a rule
   in one sentence and its exception or antecedent in another are never seen together at sentence
   granularity — the multi-sentence cases in these fixtures. A rule chunk and its exception chunk are
   combined arithmetically (max entailment minus max contradiction) and compared with a tuned threshold,
   rather than read together.
4. **Hard-coded label indices** per checkpoint (`entailment_idx`, `contradiction_idx` in `model_map`);
   a different checkpoint with another label order would be silently mis-scored (this study reads
   `id2label` and refuses unknown names).
5. **Pickle loading**: the default SummaC-Conv weights are loaded with `torch.load(start_file)` (a zip
   containing a pickle), after an `os.system("wget …")` download at run time.
6. **Threshold on the evaluated data**: `SummaCBenchmark.evaluate()` picks, per dataset, the threshold
   that maximizes balanced accuracy *on the data it is scoring*; held-out discipline depends entirely on
   the caller.
7. **Scope**: six English summarization datasets (CNN/DM, XSum sources) with binary consistency labels.
   A SummaC score is a consistency score, not a three-way label, not a coverage measure, and not
   evidence of sufficiency; it says nothing about Spanish.

## ACL 2026 long paper `2026.acl-long.1472`

**Blocked / unidentified.** `aclanthology.org`, `doi.org`, `arxiv.org` and Semantic Scholar were all
denied from this session, and two web searches found no page for the identifier. No claim about its
content is made anywhere in this study. Smallest next step: read the anthology page and PDF from an
allowed network path and add a section here.

## Software

| Component | Version | Status |
|---|---|---|
| Python | 3.13.16 (Linux x86_64) | verified (baseline, scorer, self-test ran) |
| Baseline, scorer, self-test | stdlib only | verified |
| huggingface_hub (fetch attempt) | 2.2.0 | verified (installed in an isolated venv; attempt failed with 403) |
| Model run dependencies | torch 2.14.1, transformers 5.19.0, tokenizers 0.23.3, safetensors 0.8.0, huggingface-hub 2.2.0, sentencepiece 0.2.2, numpy 2.5.4 | resolved with hashes (`model/requirements-model.*.lock`), **not installed or executed** |

The Linux lock resolves PyPI's torch, which pulls 15 CUDA packages; a CPU-only install from the PyTorch
CPU index is preferable but `download.pytorch.org` was denied here. The macOS lock targets macOS 14+
(torch publishes arm64 wheels only for `macosx_14_0_arm64`).

Code and fixtures in this directory: original work, under the repository's MIT license.
