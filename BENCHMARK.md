# Benchmark evidence and limits

The default command stays offline: `python -m patchcourt benchmark --output outputs/benchmark`. Its historical 70-row ledger is `evidence/benchmark.json`. Model arms are deliberately not run by an offline command.

The new explicit live command is `python -m patchcourt benchmark --provider glm --output outputs/a-new-evaluation`, requiring local GLM_API_KEY and TAVILY_API_KEY. It freezes the 14-case corpus and protocol before requests, sends opaque IDs without expected labels, makes at most three exact-model inference calls plus one search, and preserves all outcomes. Raw protocol, replies, issues, retrieval, knowledge and final digest are in `evidence/glm-evaluation`.

| Arm | Exact labels matched | Defects detected / 9 | False positives / 3 controls | Abstentions |
|---|---:|---:|---:|---:|
| A deterministic comparator | 14/14 | 9 | 0 | 2 |
| B original ACV review prompt/parser with GLM | 2/14 | 1 | 0 | 13 |
| C GLM classification | 14/14 | 9 | 0 | 2 |
| D GLM with official Tavily documents | 13/14 | 8 | 0 | 3 |
| E scoped exact-repeat knowledge + comparator | 14/14 | 9 | 0 | 2 |

This is **not an apples-to-apples superiority result**. B invokes the actual original ACV snapshot-review prompt and parser on case JSON. Its explicit conservative adapter maps an exact-file `bug` finding to FAIL and otherwise abstains; absence of a review finding is never called PASS. This framing and scoring are different from C/D classification. Raw issues are available for inspection.

C and D see the same cases and contract; D additionally receives official documents returned by one shared Tavily basic search. The paired ledger shows one fewer exact match with documents. No positive search benefit or causal negative effect is claimed from a single stochastic trial. The 14 visible, developer-authored cases comprise nine defects, three controls and two abstentions, not an independent blinded holdout. Earlier adversarial tests are now public regressions.

E saves only model classifications independently confirmed as determinate by the comparator. Twelve matching records are retrieved; all fourteen cases are compared again. No new model request occurs in E, but token savings versus an unrun repeated-model baseline are not estimated. This demonstrates exact-repeat evidence reuse, not generalization.

All three live model calls together report 14,715 tokens. Dollar cost is unknown. This is GLM development evidence, not the requested NVIDIA/Nemotron evaluation. The initial ledger's environment field incorrectly says PatchCourt 0.3.0; the reporter has been fixed to read the actual version, and original raw records are preserved unchanged with this correction noted.
