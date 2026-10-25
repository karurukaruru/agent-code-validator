# Downloadable offline test build

- `patchcourt-demo-0.3.0.zip`: unpack, open `index.html`, then select `report.json` with **Open evidence**. No account, server or paid API required.
- `agent_code_validator-0.3.0-py3-none-any.whl`: install using `python -m pip install <wheel-path>`, then `patchcourt demo --output outputs/patchcourt`.
- `SHA256SUMS.json`: hashes and byte counts for the wheel, static archive, video and subtitles.
- `patchcourt-offline-demo.mp4` and `.en.srt`: actual 112-second browser recording with burned-in English subtitles; explicitly offline, no model claims. Full decode and provenance in `../evidence/video`.

The wheel's resources and CLI were tested from a clean extraction in Python isolated mode. This is a tested offline developer build; live Nebius/Nemotron/Tavily contributions remain blocked. Historical defect FAIL verdicts are expected; repair verification is reported separately.

Source, tests, provenance, third-party licenses and full SDK evidence are in the parent repository. No public arbitrary-code execution endpoint exists. [Public download](https://raw.githubusercontent.com/karurukaruru/agent-code-validator/462fde1dbce1eb46b5f00df5e68cf7aa6bf2d368/release/patchcourt-demo-0.3.0.zip) was anonymously fetched and its SHA-256 verified on October 25, 2026. Keep the dedicated branch and immutable commit available throughout judging.
