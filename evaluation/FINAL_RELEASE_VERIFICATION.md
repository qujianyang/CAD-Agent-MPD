# Final Evaluation Release Verification

Release: `eval-freeze-v1`
Verification date: 2026-07-26
Scope: shock-mount Systems B, C, and D

## Release contents

This release preserves the complete controlled comparison:

- System B: Qwen3.5 9B without engineering tools or RAG.
- System C: the same model with deterministic shock-mount tools and no RAG.
- System D: the same model and tools with the frozen BGE-M3 RAG configuration.
- 170 frozen cases, three repeats per system.
- 510 records per system and 1,530 records in total.

The selected model, prompt, tool schemas, benchmark, RAG index, raw run
records, scored records, formal statistical analysis, and human-readable report
are included in the release.

## Environment verification

The project interpreter used for development is Python 3.10.8 in
`mpd/Scripts/python.exe`.

A separate clean environment was created from this repository using:

```powershell
.\mpd\Scripts\python.exe -m venv tmp\eval-freeze-venv4
.\tmp\eval-freeze-venv4\Scripts\python.exe -m pip install -r requirements-dev.txt
```

The following release-focused suite then passed in that clean environment:

```powershell
.\tmp\eval-freeze-venv4\Scripts\python.exe -m pytest `
  tests\test_evaluation_harness.py `
  tests\test_tooluse_guard.py `
  tests\test_freeze_model_interface.py `
  tests\test_formal_analysis.py `
  tests\test_final_shock_draft.py `
  tests\test_shock_rag_scope.py -q
```

Result: `37 passed in 7.55s`.

`requirements.txt` uses ASCII comments because the Windows Python 3.10
installer otherwise reads the file with the local code page and can fail on a
Unicode dash before dependency installation begins. Package requirements were
not changed by this compatibility correction.

## Controlled inference settings

The final raw records capture the same configuration for Systems B, C, and D:

| Setting | Frozen value |
|---|---:|
| Model alias | `cad-eval-qwen35-9b:8k` |
| Context length | 8192 |
| Temperature | 0.0 |
| Maximum output tokens | 2048 |
| Seed | 42 |
| Reasoning effort | `none` |
| Top-p | 0.95 |
| Presence penalty | 0.0 |

The Ollama alias also contains `top_k=20` and `repeat_penalty=1`. Its Modelfile
contains `presence_penalty=1.5`, but the evaluation client overrides that value
to `0.0` on every request. A direct LangChain invocation-parameter inspection
confirmed the request-level override.

Every final run file contains its effective `system_config`. The tool traces
also show zero overlapping tool-call intervals. System C had up to three
sequential tool calls and System D had up to two.

Ollama 0.31.2 was documented when the model screening and final evaluation
environment was established. The installed application reported 0.32.3 during
release verification on 2026-07-26. The frozen model alias digest, model
parameters, request settings, raw responses, and scored outputs did not change.
This patch-version drift is recorded as a reproducibility limitation rather
than hidden or retroactively corrected.

## Dataset separation

The 10-case development set and 170-case final set were compared directly:

| Check | Result |
|---|---:|
| Case-ID overlap | 0 |
| Exact normalized question overlap | 0 |
| Engineering input-configuration overlap | 0 |

The development cases were therefore not reused in the final benchmark.

## Final results

Results use one majority verdict per case across the three repeats. The 30
information-only reference cases do not have PASS/FAIL/ASK gold verdicts, so
verdict accuracy is calculated on 140 decision cases.

| Metric | System B | System C | System D |
|---|---:|---:|---:|
| Verdict accuracy | 38.6% (54/140) | 82.1% (115/140) | 84.3% (118/140) |
| False-safe rate | 13.8% (4/29) | 13.8% (4/29) | 3.4% (1/29) |

Paired comparisons:

- B to C: +43.6 percentage points; exact McNemar `p < 0.0001`.
- C to D: +2.1 percentage points; exact McNemar `p = 0.6291`.

System D retrieval Hit@3 was 86.7% on the frozen reference cases. The detailed
retrieval, citation, operational, category, confusion-matrix, and failure
taxonomy results are in `evaluation/results/BCD_shock_final_v1_report.md`.

These results measure agreement with the frozen Python oracle. They do not
constitute physical certification of an isolator installation.

## Artifact checksums

| Artifact | Records | SHA-256 |
|---|---:|---|
| `evaluation/benchmark/final_shock_draft_v0.jsonl` | 170 | `e27e129a9b6a2750e18d16c007d664b1427bbc715ef743ea0ce5c1ecb13a60ed` |
| `evaluation/artifacts/model_interface_manifest.json` | - | `320ba7d0b7af061cef804f6a7cc37008dc6c9c2f94678b3cfd92ff0d99b26297` |
| `artifacts/embedding_candidates/bge_m3.json` | 34 chunks | `00d972b51d26981fa07dab64b27a121f6212a4ed781178a304c266fcd49ce528` |
| `evaluation/runs/B_shock_final_v1.jsonl` | 510 | `fce1a5b6965edb2ba0998e233efaa1dc2c8f8a78d67b7a2b2f9f4c2188ab12ee` |
| `evaluation/runs/C_shock_final_v1.jsonl` | 510 | `220923494405b3f45fd97e8619dade8608aea2a10f749bbcf829dd8582bc1a8f` |
| `evaluation/runs/D_shock_final_v1.jsonl` | 510 | `26d6219678f8b965bcc1761d0b6c5dd2d23acef107253cce8494590a451d906f` |
| `evaluation/results/B_shock_final_v1_scored.json` | 510 | `164eed5e0d41441403b04389ca1ce746be195264384f7f20f4a6cfac91a3dca2` |
| `evaluation/results/C_shock_final_v1_scored.json` | 510 | `10f12818e6ec730a15bc9d10bb0644744a46fdd1a6837d3b9ae8f0b789ee578f` |
| `evaluation/results/D_shock_final_v1_scored.json` | 510 | `7f81010fb61d36a21fbc32f44a39f67eb1251b7e2f9809d4405e1ce42bc5ce3e` |
| `evaluation/results/BCD_shock_final_v1_formal.json` | - | `3a24b3a42bd8993c71affa9cdfada75e3d138ae2c24a3ebef10626fe4573e8b6` |
| `evaluation/results/BCD_shock_final_v1_report.md` | - | `7efc08960a2da7abab47603a50b43a44e25d42e5219b2557a2fb4e7cb8ffd573` |

The manifest's canonical content hash is
`4946cfdf9386f8c350e76c7313726e30a849d72da60610d2df0b2996d0c22a6f`.
This differs from the physical file checksum because the file also stores that
canonical hash and uses indented JSON formatting.

## Change control

The release tag identifies the exact source and evidence used for this result.
Changing the model, inference settings, prompt, tool schemas, engineering
functions, benchmark, RAG corpus/index, verdict parser, scorer, or formal
analysis requires a new evaluation version. Final-set failures may be analysed,
but they must not be used for training followed by retesting on the same cases.
