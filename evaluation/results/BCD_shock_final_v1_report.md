# Formal B/C/D Shock-Mount Evaluation Results

**Status:** Frozen v1 raw runs analysed without modifying the benchmark, runner, prompts, tools, or JSONL records.

## Analysis rules

- The statistical unit is one benchmark case, not one repeated response.
- Three repeats are reduced to a strict majority verdict per case.
- All-different outcomes are labelled `NO_MAJORITY` and scored incorrect.
- Tool-required accuracy excludes no-tool cases; abstention is reported separately.
- McNemar tests use paired case-majority correctness on the same 140 decision cases.
- Latency, arguments, retrieval, citations, and hard failures remain repeat-level descriptive measures.

## Frozen inputs

| Input | Path |
|---|---|
| Frozen benchmark | `evaluation\benchmark\final_shock_draft_v0.jsonl` |
| System B raw runs | `evaluation/runs/B_shock_final_v1.jsonl` |
| System C raw runs | `evaluation/runs/C_shock_final_v1.jsonl` |
| System D raw runs | `evaluation/runs/D_shock_final_v1.jsonl` |

## Case-level engineering outcomes

| Metric | B | C | D |
|---|---:|---:|---:|
| Verdict accuracy | 54/140 (38.6%); 95% CI 30.9%-46.8% | 115/140 (82.1%); 95% CI 75.0%-87.6% | 118/140 (84.3%); 95% CI 77.4%-89.4% |
| False-safe rate | 4/29 (13.8%); 95% CI 5.5%-30.6% | 4/29 (13.8%); 95% CI 5.5%-30.6% | 1/29 (3.4%); 95% CI 0.6%-17.2% |
| False-fail rate | 1/71 (1.4%); 95% CI 0.2%-7.6% | 0/71 (0.0%); 95% CI 0.0%-5.1% | 0/71 (0.0%); 95% CI 0.0%-5.1% |
| Three-repeat unanimity | 129/140 (92.1%); 95% CI 86.5%-95.6% | 126/140 (90.0%); 95% CI 83.9%-93.9% | 129/140 (92.1%); 95% CI 86.5%-95.6% |

## Corrected tool-use denominators

| Metric | B | C | D |
|---|---:|---:|---:|
| Tool-required runs | 0 | 300 | 390 |
| First-tool accuracy | n/a | 300/300 (100.0%) | 381/390 (97.7%) |
| Exact sequence accuracy | n/a | 300/300 (100.0%) | 375/390 (96.2%) |
| Valid schema | n/a | 300/300 (100.0%) | 387/390 (99.2%) |
| Argument accuracy | n/a | 2376/2430 (97.8%) | 2382/2430 (98.0%) |
| No-tool expected runs | 510 | 210 | 120 |
| Tool abstention accuracy | 510/510 (100.0%) | 120/210 (57.1%) | 72/120 (60.0%) |

## ASK safety behaviour

| Metric | B | C | D |
|---|---:|---:|---:|
| ASK Precision | 34.4% | 100.0% | 100.0% |
| ASK Recall | 82.5% | 50.0% | 47.5% |
| ASK F1 | 48.5% | 66.7% | 64.4% |
| Exact missing-field accuracy | 31/40 (77.5%) | 18/40 (45.0%) | 19/40 (47.5%) |

## Boundary-band safety

| Band | Metric | B | C | D |
|---|---|---:|---:|---:|
| Boundary | Verdict accuracy | 14/45 (31.1%) | 41/45 (91.1%) | 44/45 (97.8%) |
| Boundary | False-safe | 1/10 (10.0%) | 3/10 (30.0%) | 1/10 (10.0%) |
| Non Boundary | Verdict accuracy | 40/95 (42.1%) | 74/95 (77.9%) | 74/95 (77.9%) |
| Non Boundary | False-safe | 3/19 (15.8%) | 1/19 (5.3%) | 0/19 (0.0%) |

## Paired case-level comparisons

| Comparison | First only correct | Second only correct | Accuracy difference | Exact McNemar p |
|---|---:|---:|---:|---:|
| B -> C | 14 | 75 | +43.6% | <0.0001 |
| C -> D | 7 | 10 | +2.1% | 0.6291 |

## System D retrieval and citation

| Metric | Result |
|---|---:|
| Hit@3, repeat level | 78/90 (86.7%) |
| Hit@3, case-majority | 26/30 (86.7%) |
| Recall@3 | 86.7% |
| MRR | 0.7944 |
| Citation precision | 42.2% |
| Citation recall | 86.7% |
| Every cited ID was retrieved | 81/90 (90.0%) |

## Operational measures

| Metric | B | C | D |
|---|---:|---:|---:|
| Hard failures | 0/510 (0.0%) | 0/510 (0.0%) | 6/510 (1.2%) |
| Latency p50 | 14.1 s | 27.3 s | 26.0 s |
| Latency p95 | 66.0 s | 41.0 s | 117.8 s |

## Verdict accuracy by category

| Category | B | C | D |
|---|---:|---:|---:|
| `adversarial_assumed_mass` | 3/5 (60.0%) | 2/5 (40.0%) | 3/5 (60.0%) |
| `adversarial_conflicting_mass` | 0/5 (0.0%) | 0/5 (0.0%) | 0/5 (0.0%) |
| `adversarial_invalid_value` | 5/5 (100.0%) | 5/5 (100.0%) | 0/5 (0.0%) |
| `adversarial_missing_mass` | 5/5 (100.0%) | 0/5 (0.0%) | 1/5 (20.0%) |
| `missing_input` | 20/20 (100.0%) | 13/20 (65.0%) | 15/20 (75.0%) |
| `multi_tool` | 0/10 (0.0%) | 10/10 (100.0%) | 10/10 (100.0%) |
| `selection` | 11/35 (31.4%) | 34/35 (97.1%) | 35/35 (100.0%) |
| `unit_conversion` | 5/10 (50.0%) | 10/10 (100.0%) | 10/10 (100.0%) |
| `verification` | 5/45 (11.1%) | 41/45 (91.1%) | 44/45 (97.8%) |

## System B majority confusion matrix

| Gold / predicted | PASS | FAIL | ASK | NULL | INVALID | NO_MAJORITY |
|---|---:|---:|---:|---:|---:|---:|
| PASS | 21 | 1 | 42 | 4 | 3 | 0 |
| FAIL | 4 | 0 | 21 | 4 | 0 | 0 |
| ASK | 7 | 0 | 33 | 0 | 0 | 0 |

## System C majority confusion matrix

| Gold / predicted | PASS | FAIL | ASK | NULL | INVALID | NO_MAJORITY |
|---|---:|---:|---:|---:|---:|---:|
| PASS | 70 | 0 | 0 | 0 | 1 | 0 |
| FAIL | 4 | 25 | 0 | 0 | 0 | 0 |
| ASK | 7 | 0 | 20 | 0 | 13 | 0 |

## System D majority confusion matrix

| Gold / predicted | PASS | FAIL | ASK | NULL | INVALID | NO_MAJORITY |
|---|---:|---:|---:|---:|---:|---:|
| PASS | 71 | 0 | 0 | 0 | 0 | 0 |
| FAIL | 1 | 28 | 0 | 0 | 0 | 0 |
| ASK | 10 | 0 | 19 | 0 | 11 | 0 |

## Primary failure taxonomy

Counts are repeat-level primary labels; unique-case counts prevent repeated failures from appearing as independent cases.

| System | Failure class | Runs | Unique cases | Representative case IDs |
|---|---|---:|---:|---|
| B | `false_fail` | 3 | 1 | shock_final_022 |
| B | `false_safe` | 12 | 4 | shock_final_011, shock_final_033, shock_final_036, shock_final_078 |
| B | `missed_required_ask` | 21 | 7 | shock_final_126, shock_final_128, shock_final_131, shock_final_132, shock_final_133, shock_final_134, shock_final_135 |
| B | `other_verdict_error` | 24 | 8 | shock_final_017, shock_final_031, shock_final_035, shock_final_061, shock_final_079, shock_final_092, shock_final_093, shock_final_098 |
| B | `unnecessary_ask` | 189 | 63 | shock_final_001, shock_final_002, shock_final_003, shock_final_005, shock_final_006, shock_final_008, shock_final_009, shock_final_012, ... |
| B | `verdict_envelope_failure` | 9 | 3 | shock_final_018, shock_final_068, shock_final_083 |
| C | `false_safe` | 12 | 4 | shock_final_037, shock_final_074, shock_final_078, shock_final_079 |
| C | `missed_required_ask` | 21 | 7 | shock_final_126, shock_final_128, shock_final_131, shock_final_132, shock_final_133, shock_final_134, shock_final_135 |
| C | `unnecessary_tool` | 69 | 23 | shock_final_136, shock_final_137, shock_final_138, shock_final_141, shock_final_142, shock_final_143, shock_final_144, shock_final_145, ... |
| C | `verdict_envelope_failure` | 69 | 23 | shock_final_045, shock_final_104, shock_final_105, shock_final_109, shock_final_110, shock_final_112, shock_final_113, shock_final_117, ... |
| C | `wrong_or_missing_argument` | 51 | 17 | shock_final_014, shock_final_015, shock_final_025, shock_final_026, shock_final_029, shock_final_042, shock_final_044, shock_final_049, ... |
| D | `false_safe` | 3 | 1 | shock_final_079 |
| D | `infrastructure_or_tool_exception` | 6 | 2 | shock_final_139, shock_final_140 |
| D | `missed_required_ask` | 30 | 10 | shock_final_126, shock_final_128, shock_final_131, shock_final_132, shock_final_133, shock_final_134, shock_final_135, shock_final_136, ... |
| D | `missing_required_tool` | 3 | 1 | shock_final_168 |
| D | `retrieval_miss` | 3 | 1 | shock_final_149 |
| D | `unnecessary_tool` | 18 | 6 | shock_final_103, shock_final_107, shock_final_117, shock_final_119, shock_final_124, shock_final_129 |
| D | `verdict_envelope_failure` | 27 | 9 | shock_final_105, shock_final_108, shock_final_109, shock_final_112, shock_final_114, shock_final_121, shock_final_122, shock_final_123, ... |
| D | `wrong_first_tool` | 6 | 2 | shock_final_141, shock_final_152 |
| D | `wrong_or_missing_argument` | 48 | 16 | shock_final_005, shock_final_014, shock_final_015, shock_final_025, shock_final_026, shock_final_027, shock_final_029, shock_final_035, ... |
| D | `wrong_tool_sequence` | 6 | 2 | shock_final_151, shock_final_154 |

## Interpretation boundary

- Statistical results establish agreement with the frozen Python oracle, not certified physical safety.
- Exact McNemar p-values test paired majority correctness; they do not prove that every subgroup changed.
- Retrieval and citation rates describe the frozen 30-case reference set.
- Final-set failures are diagnostic evidence and must not be used to train and retest on the same benchmark.
- Any deterministic bug fix, output guard, or model adaptation starts a separately labelled evaluation version.
