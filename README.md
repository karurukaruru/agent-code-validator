# Agent Code Validator (ACV)

[简体中文](README.zh-CN.md) · [Detailed usage](使用说明.md) · [Changelog](CHANGELOG.md)

ACV is a small Python CLI that reviews a local source-code project with an OpenAI-compatible LLM. v0.2 adds a read-only Reviewer Agent that explores code incrementally with bounded tools instead of sending the whole project in one request.

ACV analyzes code only. It does not edit project files, run shell commands or tests, install packages, or integrate with pull requests.

## What's new in v0.2

- Added an evidence-driven, read-only Reviewer Agent with `list_files`, `read_file`, and `search_code` tools.
- Added native model Tool Calling with strict JSON fallback for compatible providers that do not support tools.
- Added detailed findings to both the terminal and Markdown report, including evidence, impact, confidence, and suggested fixes.
- Added Chinese/English report selection through `report_language` and `--language`.
- Added dedicated Volcengine Ark Coding Plan and Agent Plan provider presets, while retaining generic OpenAI-compatible APIs.
- Hardened project isolation against absolute paths, traversal, ignored directories, symbolic links, and Windows reparse-point escapes.
- Removed artificial response-token parameters from API requests; investigation remains bounded by agent steps and tool-output limits.
- Replaced the Chinese Windows launcher name with the portable English `Start-ACV.cmd`.

## Review modes

- `acv agent <project>` — the v0.2 Reviewer Agent lists project source files, chooses what to read or search next, follows evidence, and stops autonomously.
- `acv review <project>` — the original v0.1 snapshot review flow, kept compatible.

## What it reviews

- Bugs and runtime failures
- Security and performance risks
- Architecture and error handling
- Maintainability and testability
- Code smells, unnecessary complexity, and refactoring opportunities

Supported files: Python, JavaScript, TypeScript, Java, C, C++, headers, and Go.

## Quick start

Requires Python 3.10+ and an OpenAI-compatible API.

```bash
python -m venv .venv
.venv/bin/python -m pip install -e .       # macOS/Linux
.venv\Scripts\python -m pip install -e .  # Windows
```

For Volcengine Ark Coding Plan, copy `config.example.json` to `config.json`:

```json
{
  "provider": "volcengine-coding-plan",
  "api_key": "your-coding-plan-api-key",
  "model": "ark-code-latest",
  "report_language": "zh-CN",
  "timeout": 120
}
```

The provider preset automatically uses the Coding Plan OpenAI-compatible gateway. Do not replace it with the standard Ark `/api/v3` gateway, which does not consume the Coding Plan subscription quota.

For Volcengine Ark Agent Plan, copy `config.volcengine-agent-plan.example.json` instead and enter a model ID currently enabled in the Agent Plan console. Its preset uses the separate Agent Plan gateway. Coding Plan, Agent Plan, and standard Ark API keys are not interchangeable.

For another OpenAI-compatible provider, start from `config.openai-compatible.example.json`. `config.json` is ignored by Git.

Set `report_language` to `zh-CN` or `en`. Explanatory prose follows that setting; file paths, code identifiers, severity/category values, and established technical terms remain in English. A single run can override it with `--language en` or `--language zh-CN`.

Run the v0.2 Reviewer Agent:

```bash
acv agent /path/to/project
```

The default investigation limit is 15 model steps. It can be changed explicitly:

```bash
acv agent /path/to/project --max-steps 20 --output reports/agent-review.md
```

Run the classic v0.1-compatible review:

```bash
acv review /path/to/project
```

Windows workspace launcher (defaults to v0.2 agent mode):

```powershell
.\Start-ACV.cmd D:\path\to\project
```

Use classic review mode explicitly when needed:

```powershell
.\Start-ACV.cmd D:\path\to\project review
```

Findings are printed in the terminal. The Windows launcher stores reports in the workspace-level `acv_outputs` directory. A normal installed command stores them in `./outputs` unless `--output` is supplied.

```bash
acv review /path/to/project --output reports/review.md
```

## Tests

```bash
python -m pip install -r requirements.txt
python -m pytest
```

Tests use fake providers and a local OpenAI-compatible HTTP server. They do not require a real API key.

## Reviewer Agent safety

The agent has only three inspection tools: `list_files`, `read_file`, and `search_code`. Every path is resolved against the requested project root. Absolute paths, `..` traversal, dependency/cache/build directories, symbolic links, oversized reads, and unsupported source types are rejected. Tool output, history size, repeated calls, and total steps are bounded. Native model tool calling is preferred; providers that reject it automatically use a strict JSON action fallback.

## Privacy and limitations

Source code selected by the snapshot reviewer or Reviewer Agent is sent to the API provider configured by the user. Check that provider's privacy and retention policy before reviewing private code. LLM findings can be incomplete or incorrect and should complement tests and human review.

## License

Released under the [MIT License](LICENSE).
