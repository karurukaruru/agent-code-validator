# Demo script — English narration, 175 seconds

An actual 112-second offline browser recording is available at `release/patchcourt-offline-demo.mp4`, with complete burned-in English subtitles and separate SRT. It contains no audio track. Capture hashes, timestamps, browser actions, full-decode validation and encoding details are in `evidence/video`. The following 175-second script remains the plan for the later live-enabled competition cut. Do not splice mocked calls into live footage; the offline recording does not establish the competition's live NVIDIA/Nebius requirement.

| Time | Actual footage | Narration |
|---|---|---|
| 0–15 | Open first recorded case; missing tool calls and failed replay | “The tools ran successfully. The next request forgot them. This is how an agent can pass basic tests and still break after an adapter change.” |
| 15–45 | Semantic diff, IDs and tool results; show provenance | “PatchCourt checks the conversion boundary. These identifiers disappeared, leaving results without their matching calls. Unknown formats produce an explicit inconclusive result.” |
| 45–80 | Run installed-SDK reproduction; show version and hash | “We reproduced this known issue with the actual NVIDIA SDK 1.4.3 and real LangChain messages. The report distinguishes this from our dependency-free source harness.” |
| 80–115 | Repair diff, both calls, five controls, task replay | “A reviewed patch restores both calls. Independent checks reject a deliberately corrupted second call. Deterministic task replay recovers the expected inventory value.” |
| 115–140 | Run demo twice, knowledge prior hit, CI YAML and trace exit code | “Version-scoped knowledge keeps the evidence and its limits. A cache hit does not skip verification. CI can block a changed trace using the same checks.” |
| 140–165 | Lab report with BLOCKED trials | “The Nebius Reliability Lab and Tavily documentation experiment are implemented. We currently lack credentials, so the live results are blocked. We do not substitute mocked calls for NVIDIA inference or invent platform feedback.” |
| 165–175 | Repository/build instructions | “PatchCourt makes hidden compatibility failures visible, reproducible and reviewable.” |

When authorized APIs are available, replace the blocked segment with genuine model-generated cases, usage and a repeated platform finding. Retain failed trials and visibly name exact NVIDIA model and Nebius Token Factory. Export public YouTube video under three minutes with English narration/subtitles; no YouTube upload has occurred.
