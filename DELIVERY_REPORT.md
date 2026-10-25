# PatchCourt 交付报告 — 2026-10-25

目前可运行、可下载、已通过跨平台测试的版本是**离线开发版**。尚未完成真实 API 实验与最终参赛提交；不把模拟结果算作平台验证。

1. **实际实现**：消息语义比较、转换边界记录、两个历史缺陷复现、最小反例、经审查的修复、回归测试、确定性任务重放、ASM 知识保存与重验、静态证据界面、实验与反馈生成命令。
2. **文件与架构**：核心在 `patchcourt/`；测试在 `tests/test_patchcourt_*.py`；真实执行证据在 `evidence/`；安装包、演示压缩包、视频在 `release/`。沿用 ACV 检查能力和 ASM 证据约定；详见 `ARCHITECTURE.md`。
3. **Git**：公开分支 `patchcourt/award-build-20261024`；实施提交 `462fde1dbce1eb46b5f00df5e68cf7aa6bf2d368`。主分支未被覆盖。后续交付文档提交见该分支历史。
4. **测试**：Windows 为 143 通过、4 项符号链接权限跳过；GitHub Ubuntu 的 Python 3.10 和 3.13 各为 **147 全通过**。14 项真实 Chrome 界面检查通过；独立安装包执行通过。远程运行：https://github.com/karurukaruru/agent-code-validator/actions/runs/40155739894 。
5. **模型集成**：Nebius/Nemotron 与 Tavily 客户端、模型生成声明式测试及文档对照实验已实现并用模拟传输测试。没有真实模型推理证据，不能称为已满足比赛要求。
6. **反馈实验**：缺少凭证的计划实验明确记录 BLOCKED。新增反馈生成器会汇总真实 HTTP 结果、原始次数、不确定性、复现方法、影响、建议和验收测试；目前没有可声称的 Nebius 平台缺陷。
7. **竞品比较**：已核对 Attest、PortVerdict、PatchScout、Promptfoo 等公开材料；存在明显重叠。当前重点是转换边界的信息丢失、可信复现与版本重验。未实跑竞品，不宣称领先；详见 `COMPETITIVE_ANALYSIS.md`。
8. **安全审查**：修复了错误成功判定、第二次工具调用漏检、流式未知字段、JSON 非有限数与重复键、知识校验、密钥脱敏等问题。执行对象限于审查过的固定源码；没有执行任意模型生成 Python 的接口，也不声称具备操作系统级沙箱。发布扫描未发现已配置凭证或已识别密钥模式。
9. **演示**：在仓库根目录运行 `python -m patchcourt demo --output outputs/patchcourt`，然后 `python -m patchcourt serve outputs/patchcourt --port 8765`，访问 `http://127.0.0.1:8765`。也可下载 ZIP，解压打开 `index.html`，点击 Open evidence 选择 `report.json`。`release/patchcourt-offline-demo.mp4` 为 112 秒真实浏览器录制、完整英文字幕、无音轨；不是在线模型演示。
10. **Devpost 材料**：英文项目说明、架构、测试、来源、变更记录、视频脚本、奖项策略和提交清单已准备；公开源码与离线测试包可用。仍缺真实平台实验、正式公开 YouTube 地址及登录后的表单确认。
11. **风险与获奖判断**：NVIDIA SDK 历史缺陷已在真实安装包中复现并验证修复；CrewAI 仅验证审查过的源码转换函数。自动任意项目修复、广泛沙箱运行和真实任务重放未完成。官方未列人人可得的参与奖；无法给出有依据的获奖百分比。优先争取 10 个名额的 Most Valuable Feedback，但须先满足资格并产生具体、可复现的真实反馈。
12. **需要用户完成的事项**：提供合法可用的 Nebius 访问配置（本机环境变量 `NEBIUS_API_KEY`、可访问的 `NEBIUS_MODEL`）；争取 Tavily 奖时还需 `TAVILY_API_KEY`。不要在聊天里粘贴密钥。API 到位后仍需跑实验、审查发现并更新视频；用户还需完成 Devpost 登录、个人资格信息、视频发布授权及最终提交确认。截止时间为北京时间 **2026 年 10 月 31 日 01:00**。

规则来源：https://nebiusglobalaihackathon.devpost.com/rules 。当前状态不代表已参赛成功或保证获奖。
