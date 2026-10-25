# Reproduction guide

Run `python -m patchcourt demo --output outputs/reproduction`. Inspect `report.json`, repair diffs, controls and exported tests. Run those tests with `python -m unittest discover -s outputs/reproduction -p test_regression.py`.

## NVIDIA tool-call loss

[Upstream issue #387](https://github.com/langchain-ai/langchain-nvidia/issues/387) identifies release 1.4.3. The dependency-free demo snapshot is upstream Git blob `8c23b708e8511c70e771f48fe71b4309d201f61b`, SHA-256 `ea569d556ed537e15bf5eea3db555adc9b4fb003a92543c70f1c719a9c47c873`. It executes audited conversion functions with inert LangChain-shaped types.

Stronger evidence was also executed: official PyPI `langchain-nvidia-ai-endpoints==1.4.3` with `langchain-core==1.7.0` and real `AIMessage`. Original serialization loses two normalized calls. A reviewed patched copy restores both IDs, names and all arguments. Five controls pass, including detection of corruption in the second call. See [full SDK evidence and replay](evidence/full-sdk/README.md). Its wheel-source SHA-256 is `ec8d2ef813a184d37a347f493242124319dbe3c6f6926124ba2f8a3560ed2531`; it differs from the demo's later upstream snapshot.

## CrewAI image loss

[Upstream issue #8434](https://github.com/crewAIInc/crewAI/issues/8434). Source from tag `1.15.28`, Git blob `1129d411257ce66d199f49ecb230c797374def24`, SHA-256 `715e68f80b32cbd97011bf8c616b3746149454083a32b163cf2010f136a63383`.

The original Gemini formatting method runs with inert Part/Content types and an identity base formatter. A PNG data URI loses its image part. The reviewed patch preserves bytes/MIME, passes text controls and rejects unsupported remote URLs. Held-out tests check multiple images and malformed base64. Full CrewAI installation and live vision outcomes are **not verified**.

These are credited known defects, not new discoveries. Hash mismatches refuse execution. Fixed patches do not modify installed packages or user repositories. The inventory replay is a deterministic task simulation; restored image bytes alone do not prove vision-task success.
