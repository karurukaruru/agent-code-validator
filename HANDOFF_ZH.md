# PatchCourt 跨电脑开发交接（2026-10-25，0.3.2）

先读本文，再把 `NEXT_AGENT_PROMPT.md` 发给下一位 Agent。压缩包根目录的 `START_HERE_中文.md` 解释解压、校验和 Git 恢复。

## 当前水平

按“能够正式交付参赛”粗估约 **70%**，有较大不确定性。这是工程判断，不是测量出的完成率，更不是获奖概率。核心功能已有真实 API 演示、独立验证、视频、安装包和测试；比赛平台实测、有效反馈、最终提交以及部分工程能力仍未完成。不要再告诉用户“全部做好，只差 API”。

公开稳定版：0.3.1，分支 `patchcourt/award-build-20261024`，代码提交 `37aba3524acd109fd588e495e48a49fe1afecc38`，文档提交 `80edbddb6c5556d04c66db3ad40eb4f93b11765f`。公开地址：https://github.com/karurukaruru/agent-code-validator/tree/patchcourt/award-build-20261024 。

本交接版是 **0.3.2，仅本地新增提交，尚未推送**。只做两项收尾：

1. 明确生成测试时 PASS/FAIL/INCONCLUSIVE/NEEDS_REVIEW 的语义、正常行为对照；拒绝 GLM 返回其他模型或不唯一的 completion，防止错误推理证据被接受。
2. 离线报告不再断言“没有凭证、没有视频、尚未公开”，只陈述本次离线运行未验证相关能力。版本号随本版更新。

新提示词尚未进行额外真实推理评估，不能宣称提高了模型准确率。本轮没有真实 API 消耗。

## 用户要求优先

- 用中文，少问非必要问题，合理选择自行处理。用户剩余额度较低，本次明确要求只修一两处后打包，现已执行。
- 只允许使用 `glm-5.3-flash`，禁止 FlashX 和其他替代型号。用户明确要求停止 NVIDIA 模型调用；未经用户新授权，不得恢复 Nebius/NVIDIA 调用，包括为了比赛资格而自行试用。
- 用户曾提供临时 GLM/Tavily/Nebius 密钥。**密钥和个人凭证文件不在包中**，不可从旧日志猜测或寻找。新机器通过进程环境变量设置 `GLM_API_KEY`、可选 `TAVILY_API_KEY`。用户打算撤销临时密钥，旧密钥有效性不要假定。
- 原始任务授权已有仓库的专用开发分支提交/推送，不允许强推、新建公开仓库或未经批准最终提交 Devpost。
- 不编造平台问题、获奖概率、Tavily 提升，也不把 mock 当真实 API。

## 已经验证

- 0.3.2 本机：**163 passed, 4 skipped**，`evidence/tests/pytest-handoff-032.txt`。4 项是 Windows 不允许创建符号链接。新增两项测试为模型响应验证。
- 0.3.1 远端：Ubuntu Python 3.10 和 3.13 均 **165 passed**，`evidence/tests/github-actions-glm.json`。这不是 0.3.2 的 CI 结果；交接版尚未跑远端 CI。
- 真实 GLM：共六次工作流尝试，前四次开发失败保留、后两次成功。录制那次 3 次请求、2480 tokens、8/8 独立校验、故意损坏 ID 被拒绝、实际本地工具回传数量 3 和单价 7、模型答案 21。
- 五组开发评估：70 行全部执行。C 不带搜索 14/14；D 带 Tavily 13/14；没有证明搜索提升。原 ACV 审查任务与直接分类任务不同，不能据此宣称整体优劣。
- 已记录 GLM 总用量 31,734 tokens；两次 Tavily basic 搜索共 2 credits。美元费用未知。后续实验必须另记，不能覆盖原证据。
- 13 项真实 Chrome 工作台检查通过。95 秒实际浏览器视频有英文合成配音、英文烧录字幕、英文和中文 SRT；从未上传 YouTube。
- 真正安装 NVIDIA SDK 1.4.3 的离线复现已执行；这不等于调用 NVIDIA 模型。CrewAI 目前仍只执行固定源函数。

## 新机器最快启动

使用 Python 3.10+（推荐 3.13）、Git。进入解压后的 `project`：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e . pytest==8.4.2
.venv\Scripts\python -m pytest -ra
.venv\Scripts\python -m patchcourt demo --output outputs/restored-demo
.venv\Scripts\python -m patchcourt serve outputs/restored-demo --port 8765
```

以上命令不会使用付费 API。macOS/Linux 用 `.venv/bin/python` 替换解释器路径。真实工作台另开终端，在安全配置 GLM_API_KEY 后运行 `python -m patchcourt live-demo --port 8780`，访问 `http://127.0.0.1:8780`。每次点击会真实调用 GLM；服务器最多接受三次运行。`benchmark --provider glm` 最多三次模型请求和一次 Tavily 搜索，必须显式运行。

新安装包位于 `release/agent_code_validator-0.3.2-py3-none-any.whl`。开发推荐 `pip install -e .`，保证修改生效。旧 0.3.0/0.3.1 安装包和证据为历史资料，不能误当最新代码。

## 下一阶段优先级

先读 `REQUIREMENTS_GAP_AUDIT.md`，按实际授权继续，避免盲目重写已有系统。

1. 最小可交付工程：让一次受控依赖升级自动执行 baseline/candidate 并接上实际边界录制；保留不支持时明确弃权。现有 inspect 是只读候选发现，不是自动安装执行。
2. 用已有源函数、独立断言和限定修复计划完善真实框架覆盖。不得在缺少 OS 隔离时执行任意模型 Python。当前没有经过验证的 Docker/Podman 隔离后端。
3. 改善任务相关的官方文档检索并重复对照试验，保留所有失败；不因为接上 Tavily 就声称有奖项优势。
4. 若用户另行恢复授权，再完成比赛要求的 Nebius/NVIDIA 实测和可复现反馈；GLM 结果不能替代。竞赛官方规则需要在接手时重新核对。
5. 完成英文材料、公开视频、 entrant/account 字段和最终提交批准。原记录截止时间为北京时间 2026-10-31 01:00，接手时核对官方规则和当前日期。

## 包内材料与恢复

项目源码、所有已跟踪证据/文档、旧与新安装包、成片/字幕在 `project/`；完整 Git 历史在根目录 `repository.bundle`。原始任务在 `context/ORIGINAL_MISSION.txt`，属于历史需求，遇到冲突以本文记录的用户后续限制为准。原始 ACV/ASM 源码快照和最初审查在 `context/`；视频帧、配音 WAV、capture manifest 和编码日志在 `media/live-video/`，可复制回 `project/dist/live-video/` 继续剪辑。

不包含机器绑定的虚拟环境、SDK 安装目录、浏览器进程、私人临时启动器、原始凭证文件。依赖由 pip 恢复；实际 SDK 固定依赖见 `evidence/full-sdk/README.md`。视频脚本当前使用 Windows Chrome、System.Speech 和 `.video-deps/imageio_ffmpeg` 的固定路径，换系统需要适配，成片可直接播放。重剪可安装 `imageio-ffmpeg==0.6.0` 到 `.video-deps` 并核对 ffmpeg 可执行文件路径。

Git 恢复优先 `git clone repository.bundle work --branch patchcourt/award-build-20261024`，然后 `git -C work remote set-url origin https://github.com/karurukaruru/agent-code-validator.git`；本地 HEAD 会领先已公开分支，禁止 hard reset 丢掉交接修复。旧电脑 Git 凭证助手曾指向不存在的 `F:\tools\gh\bin\gh.exe`；新电脑重新正常配置认证，不复制旧配置。最后阶段 Git HTTPS 连接失败，已用 API 返回的 Git 对象核对 SHA 后同步过提交；这属于旧电脑环境问题，不是项目运行依赖。
