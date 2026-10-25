# Benchmark evidence and limits

Command: `python -m patchcourt benchmark --output outputs/benchmark`. Published raw ledger: `evidence/benchmark.json`.

Fourteen developer-authored cases contain 9 defects, 3 successful controls and 2 abstentions. The recorded deterministic arm detects 9/9 defects, produces 0/3 false positives and abstains correctly twice. This small constructed suite does not establish universal accuracy.

All 70 scheduled rows are preserved. A is the deterministic comparator; B (original ACV), C (Nemotron), D (Nemotron+Tavily) are BLOCKED without credentials. E is INCONCLUSIVE as a detector: ASM is a scoped evidence store, not an independent classifier. Demo lookup/reuse is separately measured and never skips execution. No token or latency savings are claimed.

Independent review supplied held-out adversarial cases after implementation: conflicting roles/calls, nonfinite values, stream schema extensions, knowledge integrity/type checks, version isolation, second-call repair corruption and multimodal controls. Failures were fixed and rerun. They are now visible regression tests, not a permanently blind evaluation set. No model test generator was used.

Inference latency/cost, relative model effectiveness, meaningful Tavily improvement, general repair success and live task recovery remain unmeasured. Null means unknown. Mocked transport results do not enter platform reliability rates. Future comparison requires a frozen new holdout, preregistered arms/budgets and publication of every outcome.
