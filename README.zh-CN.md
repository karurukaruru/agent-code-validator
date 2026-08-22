# Agent Code Validator（ACV）

[English](README.md) · [详细使用说明](使用说明.md)

ACV 是一个轻量级 Python 命令行代码审查工具。它扫描本地项目，通过 OpenAI 兼容的大模型接口分析代码，在终端显示问题，并保存带时间戳的 Markdown 报告。

ACV 只负责分析，不会修改代码，也不是自动编程 Agent。

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

填写 `config.json`：

```json
{
  "api_key": "你的 API Key",
  "base_url": "https://api.deepseek.com",
  "model": "deepseek-v4-flash",
  "timeout": 120
}
```

`base_url` 应填写 API 根地址，不要追加 `/chat/completions`。不同服务商的地址和模型名可能不同。`config.json` 已被 Git 忽略。

开始审查：

```powershell
.\启动ACV.cmd D:\你的项目目录
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

测试使用本地 OpenAI 兼容 HTTP 服务，不需要真实 API Key。

## 隐私与限制

源代码会发送给用户配置的模型服务商。审查私有代码前，请确认服务商的隐私与数据保留政策。模型可能误报或漏报，不能代替测试和人工审查。

## 许可证

本项目使用 [MIT License](LICENSE)。
