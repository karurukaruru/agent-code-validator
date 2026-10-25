> 2026-10-25 更新：0.3.1 已有真实 GLM 修复、工具任务、五组评估和 95 秒配音视频；完整状态见 [GLM_DEVELOPMENT.md](GLM_DEVELOPMENT.md)。下文保留先前版本说明，不能据此宣称已满足比赛或完成全部原始需求。

# Agent Code Validator（ACV）

[English](README.md) · [详细使用说明](使用说明.md) · [更新日志](CHANGELOG.md)

ACV 是一个轻量级 Python 命令行代码审查工具。v0.2 新增只读 Reviewer Agent：它不会一次性发送整个项目，而是先查看源码结构，再根据已有证据自主选择要读取或搜索的代码，最后生成 Markdown 审查报告。

ACV 只负责分析，不会修改项目文件，不执行 Shell、程序或测试，不安装依赖，也不自动提交代码。

## v0.2 相比 v0.1 的变化

- 新增基于证据工作的只读 Reviewer Agent，并提供 `list_files`、`read_file`、`search_code` 三个受限工具。
- 优先使用模型原生 Tool Calling；服务商不支持时自动回退到严格 JSON action。
- 终端和 Markdown 报告都会输出详细问题，包括证据、影响、置信度和修改建议。
- 新增 `report_language` 与 `--language`，可选择中文或英文报告正文。
- 新增火山方舟 Coding Plan、Agent Plan 专用 Provider，同时保留通用 OpenAI 兼容接口。
- 加强项目目录隔离，拒绝绝对路径、目录穿越、忽略目录、符号链接和 Windows Reparse Point 越界。
- API 请求不再人为发送输出 Token 上限；调查规模仍由 Agent 步数和工具输出边界控制。
- Windows 启动器统一改为英文文件名 `Start-ACV.cmd`。

## 两种审查模式

- `acv agent <项目目录>`：v0.2 Reviewer Agent，自主进行有限步数的只读调查。
- `acv review <项目目录>`：保留并兼容原有 v0.1 一次性上下文审查。

## 审查内容

- Bug 和潜在运行错误
- 安全与性能风险
- 架构和错误处理问题
- 可维护性与可测试性
- 代码异味、重复、复杂度和重构机会

支持 Python、JavaScript、TypeScript、Java、C、C++、头文件和 Go。

## 快速使用

需要 Python 3.10+ 和一个 OpenAI 兼容 API。

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e .
Copy-Item config.example.json config.json
```

默认模板用于火山方舟 Coding Plan。填写 `config.json`：

```json
{
  "provider": "volcengine-coding-plan",
  "api_key": "你的 Coding Plan API Key",
  "model": "ark-code-latest",
  "report_language": "zh-CN",
  "timeout": 120
}
```

Provider 预设会自动使用 Coding Plan 的 OpenAI 兼容套餐网关，不要改成普通方舟 `/api/v3`，否则不会消耗 Coding Plan 套餐额度。

使用 Agent Plan 时，请复制 `config.volcengine-agent-plan.example.json`，并填写 Agent Plan 控制台当前启用的模型 ID。Coding Plan、Agent Plan 和普通方舟 API 的 Key 不能混用。

使用其他 OpenAI 兼容服务时，从 `config.openai-compatible.example.json` 开始配置。`config.json` 已被 Git 忽略。

`report_language` 只能填写 `zh-CN` 或 `en`。说明正文使用所选语言，文件路径、代码标识符、Severity、Category 和通用技术术语保持英文。单次运行可以使用 `--language en` 或 `--language zh-CN` 覆盖配置。

运行 v0.2 Reviewer Agent：

```powershell
acv agent D:\你的项目目录
```

默认最多执行 15 个 Agent 步骤，也可以手动调整：

```powershell
acv agent D:\你的项目目录 --max-steps 20 --output reports\agent-review.md
```

使用英文 Windows 启动器（默认运行 v0.2 Agent）：

```powershell
.\Start-ACV.cmd D:\你的项目目录
```

需要运行兼容 v0.1 的传统审查时：

```powershell
.\Start-ACV.cmd D:\你的项目目录 review
```

或者使用安装后的命令：

```powershell
acv review D:\你的项目目录
```

AI 结果会直接显示在终端。当前 Windows 启动器把报告统一保存到工作区的 `acv_outputs` 目录；普通安装方式默认保存到当前目录的 `outputs` 中。

指定报告位置：

```powershell
acv review D:\你的项目目录 --output D:\reports\review.md
```

## 测试

```powershell
python -m pip install -r requirements.txt
python -m pytest
```

测试使用 Fake Provider 和本机临时 HTTP 服务模拟 OpenAI 兼容接口，不需要真实 API Key。

## Reviewer Agent 安全边界

Agent 只有 `list_files`、`read_file`、`search_code` 三个只读工具。每个路径都会相对项目根目录重新解析；绝对路径、`..` 跳转、忽略目录、符号链接、过大读取和不支持的源码类型都会被拒绝。单次输出、历史上下文、重复调用和总步骤数都有上限。模型支持时优先使用原生 Tool Calling，不支持时自动回退到严格 JSON action。

## 隐私与限制

源代码会发送给用户配置的模型服务商。审查私有代码前，请确认服务商的隐私与数据保留政策。模型可能误报或漏报，不能代替测试和人工审查。

## 许可证

本项目使用 [MIT License](LICENSE)。
