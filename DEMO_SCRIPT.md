# Final competition demo — recording plan and existing cut

**Recording status:** a genuine 95-second narrated GLM development cut exists at `release/patchcourt-glm-live-demo.mp4`. It is an intermediate artifact. No completed competition cut or public YouTube upload is recorded. Use actual captured Nebius/NVIDIA execution before marking the final video ready.

Aim for **145–165 seconds**, with English narration and readable English captions. Keep the exported duration below 180 seconds. Do not expose credentials or use unlicensed music. Mention the exact NVIDIA model and Nebius Token Factory aloud, as well as on screen.

| Time | Real screen action | English narration |
|---|---|---|
| 0–12 s | Show two calls missing from the historical SDK boundary. | “The tools ran. The agent still broke. An SDK adapter silently removed the tool calls the next request needed. PatchCourt makes that hidden contract visible.” |
| 12–32 s | Start the current real workflow; show exact provider/model and original failure. | “For developers upgrading AI agents, PatchCourt compares message meaning across the SDK boundary. This run uses NVIDIA Nemotron on Nebius Token Factory.” Say the exact model after it has actually run. |
| 32–60 s | Show the actual returned mapping and independent verifier results. | “The model proposes a bounded field mapping. It cannot execute arbitrary Python. Independent checks preserve IDs, names, nested arguments and existing behavior. We also corrupt the mapping; the verifier must reject it.” |
| 60–90 s | Show real model calls, local inventory/price tool execution, before/after boundary and final response. | “Here the live conversation calls two fixture tools. The original adapter loses their identities. The verified mapping preserves them, and the task completes with the checked inventory value.” State 21 only when this captured run actually returns it. |
| 90–112 s | Open controlled installed-SDK comparison and the NEEDS_REVIEW outcome. | “We also compare two actual installed SDK releases. Both can share the same defect. Equal output is not enough: the independent contract keeps this result under review.” |
| 112–137 s | Open sanitized request records, source hashes, failed attempts and retrieval comparison. | “Every result has inspectable evidence. Tavily retrieves official documentation; the paired evaluation reports what changed, including no improvement when that is what we observe.” State only the final measured outcome. |
| 137–155 s | Show clean judge starting point and free test-build instructions. | “Judges can run the packaged offline evidence without an API key, inspect source and replay the exported checks. Fresh cloud inference requires legitimate access. This build covers reviewed serializer boundaries and fixture tools.” |
| 155–165 s | Return to before/after and product name. | “PatchCourt helps a model-assisted repair earn trust through execution, before an upgrade reaches production.” |

The NVIDIA/Nebius segment must show real runtime activity and inspectable returned records. A configuration screen or model-list call is insufficient. If a slow request is trimmed, label the time compression and preserve the uncut run evidence. Do not reuse GLM footage under a Nemotron label.

Existing recording tooling is in `scripts/record_live_demo.cjs`, `scripts/live_video_narration.json`, `scripts/render_live_voice.ps1` and `scripts/encode_live_demo.py`. The existing cut has English narration, burned-in captions and separate English/Chinese SRTs. It was recorded through automated browser capture, with editorial pauses; it is not a recording of a human operator.

Final QA: inspect the start, provider attribution, actual repair, rejection control, live tool result, evidence view and closing at full size; verify caption bounds; decode the full file; record duration and SHA-256 in a fresh video manifest. Then anonymously verify the final public YouTube link. A local MP4 and a YouTube upload have separate acceptance gates in [SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md).
