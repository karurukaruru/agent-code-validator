# DeepSeek development evidence — October 25, 2026

These are real development executions, not Nebius/NVIDIA competition evidence.
The code was still changing and reported package version 0.4.0. Keep their
original reports, requests and hashes intact; they do not describe a frozen
0.5.0 release.

- `deepseek-live-01`: PASS, three DeepSeek Flash completions, one Tavily basic search, 4,094 reported tokens. Eight independent checks, corrupted-repair rejection, and an actual model conversation using controlled local tools recovered inventory value 21.
- `deepseek-reuse-01`: PASS, three completions, 2,816 reported tokens, knowledge MISS because source identity changed. This is not evidence of reuse savings.
- `deepseek-reason-01`: PASS, one completion and one Tavily basic search. Declarative model-generated cases were evaluated locally; model Python never ran.

Total: seven model requests and two searches. All requests and responses are
preserved. No claim of statistical superiority, Tavily benefit, or competition
platform compliance follows from these small development runs.
