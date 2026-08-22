# Agent Code Validator (ACV)

[简体中文](README.zh-CN.md) · [Detailed usage](使用说明.md)

ACV is a small Python CLI that reviews a local source-code project with an OpenAI-compatible LLM. It prints actionable findings in the terminal and saves a timestamped Markdown report.

ACV analyzes code only. It does not edit files, act autonomously, or integrate with pull requests.

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

Copy `config.example.json` to `config.json`:

```json
{
  "api_key": "your-api-key",
  "base_url": "https://api.deepseek.com",
  "model": "deepseek-v4-flash",
  "timeout": 120
}
```

Use the API root as `base_url`; do not append `/chat/completions`. The model name and URL depend on your provider. `config.json` is ignored by Git.

Run a review:

```bash
acv review /path/to/project
```

Windows workspace launcher:

```powershell
.\启动ACV.cmd D:\path\to\project
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

Tests use a local OpenAI-compatible HTTP server and do not require a real API key.

## Privacy and limitations

Source code is sent to the API provider configured by the user. Check that provider's privacy and retention policy before reviewing private code. LLM findings can be incomplete or incorrect and should complement tests and human review.

## License

Released under the [MIT License](LICENSE).
