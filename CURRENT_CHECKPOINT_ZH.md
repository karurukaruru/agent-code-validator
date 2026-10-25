# 最终停止点与完整接手说明（2026-10-25）

> 本文记录原交接包 0.3.2 的历史停止点。用户在当前聊天已要求继续开发，最新 0.4.0 实现、实际验证和剩余事项以 [DEVELOPMENT_REVIEW_ZH.md](DEVELOPMENT_REVIEW_ZH.md) 为准；不要把下文旧停止要求当作本轮指令。

用户最初在约 41% 额度时要求停止打包，随后在约 30% 时明确追加授权一两个小修并重新打包。**追加的两项小修现已完成，最终停止新增功能，仅完成打包和恢复验证。** 下一位 Agent 应在用户要求继续时接手；不要把交接误解为已经参赛或所有原需求均完成。

## 1. 项目到底是什么

- **PatchCourt** 是本项目的名字：检测 AI Agent 与 SDK/模型接口之间的静默兼容性故障，留下可检查的边界、反例、修复与验证记录。
- **ACV / agent-code-validator** 是原有代码审查项目，也是当前仓库名；原功能保留。PatchCourt 作为新的包和 CLI 实现在同一个仓库中。
- **ASM / agent-software-map** 是原任务希望结合的软件知识积累思路。当前做的是严格按源码、环境和验证器身份匹配的证据/修复方案复用，不是通用软件知识引擎。
- **CrewAI** 是外部开源 Agent 框架，不是我们发明的名字，也不是本项目的主体。官方项目 https://github.com/crewAIInc/crewAI ，发行包 https://pypi.org/project/crewai/1.15.28/ 。
- 当前 CrewAI 案例引用其公开问题 https://github.com/crewAIInc/crewAI/issues/8434 ：特定 Gemini 消息转换器会丢失 image_url 内容。执行的是带 SHA-256 校验的历史函数及固定修复，附第三方来源和许可；不是宣称自己开发了 CrewAI。
- 用户提到自己以前可能给 CrewAI 提过 PR。**本轮没有核实具体 PR 号码、作者或与 #8434 的关系**；不得把该公开 issue 或我们本地修复说成用户的 PR，也不得宣称上游已合并我们的修复。继续时先核对确切链接。

## 2. 当前水平：能做什么，不能做什么

按正式参赛交付粗估约 **75%**；暂不计算 NVIDIA/Nebius 授权和平台实测，约 **85%**。这是主观工程估计，不能相加，也不能用于推算剩余工时或获奖概率。此前 70% 为更早阶段判断；不应以完成测试的比例冒充整体任务完成率。

当前有实际用途：支持范围内比较消息语义、检出丢工具 ID/参数/图像的反例、运行两个固定实现、验证限定修复、运行真实 GLM 工具任务并复用精确匹配的已验证方案。可以展示、复现和让下一位开发者继续工作。

当前仍不能承诺：任意仓库自动升级检查、任意 SDK/模型兼容性、执行任意模型源码补丁的安全性、CrewAI 完整安装级复现、普遍节省 token 或实际获奖。没有完成正式赛事提交。不能回答“只要再给 API 就全部完成”。

## 3. 精确停止位置

- 主要边界功能代码提交：`5976355`，内容是 reviewed serializer pair runner、可视化、测试和安装包。随后追加 `check --input` 原始输入校验和 `verify` 缺失/空白 run_id 防护；最终提交以包内 MANIFEST.json 为准。
- 打包前还会有纯交接说明提交。**最终完整 HEAD 以 ZIP 根目录 MANIFEST.json 为准**，不要要求它等于上面的功能提交。
- 分支：`patchcourt/award-build-20261024`。
- 公开 0.3.1 代码提交：`37aba3524acd109fd588e495e48a49fe1afecc38`；公开文档提交：`80edbddb6c5556d04c66db3ad40eb4f93b11765f`。
- 最新 0.3.2 本地提交尚未推送。用户已授权现有仓库专用分支的普通提交/推送；未授权强推、新建公开仓库和最终 Devpost 提交。
- 所有新增产品代码已经完成测试并提交，没有需要下一位猜测的半写功能。
- 最后刚开始 CrewAI 安装级复现的环境调查。`pip --dry-run` 已解析成功，但**没有安装 CrewAI、没有运行其完整 SDK、没有调用模型**。用户要求收尾后停止，后续步骤未执行。
- 不要把这次 dry-run 当安装证据。对应固定顶层版本 `crewai[google-genai]==1.15.28`，建议以后先在独立环境评估，再安装；不要污染项目环境。旧固定源函数复现继续有效。

## 4. 最新功能入口

| 能力 | 入口 | 验证与限制 |
|---|---|---|
| 语义比较 | patchcourt/semantic.py；check 命令 | 严格处理工具关联、参数、部分多模态；未知格式弃权 |
| 已有日志的输入检查 | check baseline.json candidate.json --input original.json | 两份日志相同但同时丢数据时不能误报兼容；原始输入不支持时弃权 |
| 报告完整性检查 | verify DIRECTORY | 校验摘要及非空、相同的运行编号；畸形顶层结构不再导致崩溃或错误通过 |
| 自动执行受控边界 | patchcourt/boundary_run.py；boundary-run 命令 | 两个子进程运行固定上游/修复序列化器；不是任意依赖版本管理 |
| 边界捕获 | patchcourt/recorder.py | runner 自动记录 framework_input/adapter_output；未提供通用全框架 hook |
| 历史问题及固定修复 | patchcourt/reproductions.py、fixtures/ | 来源和校验和固定；CrewAI 仍使用惰性协议类型 |
| 真实 GLM 修复工作流 | patchcourt/live_workflow.py、repair_plan.py | 模型提限定映射；8 个独立检查及变异检查；真实本地工具调用和答案验证 |
| 精确方案复用 | live --knowledge-dir；knowledge.py | 验证器/环境/源码变更失效；命中仍重验与实际任务 |
| 推理生成用例 | patchcourt/reasoning.py | 不能信任模型自行给出的预期标签；错误记录保留 |
| 五组对比 | patchcourt/evaluation.py | 真实 GLM 开发评估；原 ACV 任务不同，不能宣称公平胜出 |
| UI | patchcourt/web/index.html、live.html | 静态报告浏览器和限次 loopback 真实工作台 |
| 平台试验 | patchcourt/lab.py、providers.py、feedback.py | 实现存在，不等于已做足目标平台实验；当前禁止 NVIDIA 模型调用 |

## 5. 验证事实与可打开的证据

1. 最新本机完整测试：**186 passed, 4 skipped**，`evidence/tests/pytest-final-032.txt`；4 项是 Windows 不允许创建链接。
2. 新边界执行：`evidence/boundary-run/matrix.json`，8 个实际执行场景全部符合预期；其中 5 个源码场景、3 个安装 NVIDIA SDK 的场景。预期 FAIL/NEEDS_REVIEW 是检出问题，不是测试失败。
3. 新页面：`evidence/boundary-run/browser/qa-results.json`，10 个 Chrome 检查通过；附桌面/手机截图。
4. 新安装包：`evidence/tests/wheel-verification-final-032.json`，从 wheel 隔离解压，离线 demo 和新增子进程 runner 均执行成功。
5. 0.3.2 wheel：117,318 bytes，SHA-256 `be8121081e3320ed056a025e52b7254b0ba78f5859f6f7eb2a1f3f37f06b7287`。`release/SHA256SUMS.json` 可复核。
6. 密钥扫描：`evidence/tests/secret-scan-final-032.json`；最后交接新增文件还会随 ZIP 打包扫描，结果见外部 PACKAGE_VERIFICATION.json。
7. 真实 GLM 首轮/复用：`evidence/glm-reuse/`，3 请求/2472 tokens 与 2 请求/426 tokens；任务均成功。总计实际 GLM 记录 **34,632 tokens**。本轮边界 runner 和收尾没有增加付费模型请求。
8. 公开旧 0.3.1 CI：Ubuntu Python 3.10/3.13 各 165 passed。**不是本地新版本的远端验证**。
9. 95 秒真实 GLM 演示：`release/patchcourt-glm-live-demo.mp4`，英文配音、烧录英文字幕及中英 SRT。不是 NVIDIA 演示，也未上传 YouTube。
10. Tavily 两次 basic 搜索，已有对照未显示提升。不能为争取奖项把负结果改成正结果。

## 6. ZIP 内有什么，以及哪些东西必须重配

包含当前全部 Git 跟踪源码、测试、文档、第三方许可、wheel、原始实验 JSON、失败记录、图像、视频成片、字幕、824 帧原始录制图和配音；Git bundle 包含本地领先提交与完整可达历史；context 包含完整原始任务、原 ACV/ASM 快照及初审。

不包含：API 密钥、私人凭证文件、浏览器登录/cookie、旧机器虚拟环境、已安装 SDK 目录和依赖缓存。这些不是遗漏；跨机器需要安全重新配置或安装。**这不是离线自带所有第三方依赖的系统镜像**。无需依赖即可运行项目源码的离线 demo/源码 boundary-run；完整测试、ACV 和真实 API 功能需按文档安装依赖。

使用 ZIP 内 MANIFEST.json 校验每个成员；外部 SHA256 文件校验完整 ZIP。PACKAGE_VERIFICATION.json 记录解压/Git 恢复/执行检查。历史旧 ZIP 不含本次新功能，不要混用。

## 7. 新电脑恢复（不调用付费 API）

先在 PowerShell 执行以下命令，路径按解压位置替换：

```powershell
git clone repository.bundle work --branch patchcourt/award-build-20261024
git -C work remote set-url origin https://github.com/karurukaruru/agent-code-validator.git
Set-Location work
git status --short
git rev-parse HEAD
python --version
python -m venv .venv
.venv\Scripts\python -m pip install -e . pytest==8.4.2
.venv\Scripts\python -m pytest -ra
.venv\Scripts\python -m patchcourt demo --output outputs/restored-demo
.venv\Scripts\python -m patchcourt boundary-run --output outputs/restored-boundary
# 上一条默认检出已知回归，exit 1 / FAIL 正常；不要据此认定安装失败。
.venv\Scripts\python -m patchcourt verify outputs/restored-boundary
.venv\Scripts\python -m patchcourt serve outputs/restored-boundary --port 8765
```

打开 `http://127.0.0.1:8765`。macOS/Linux 替换为 `.venv/bin/python`。每次运行使用新的输出目录，避免覆盖证据。离线源码演示可以直接在 `project/` 中用 `python -m patchcourt ...`，不一定先安装。

## 8. 真实 API 的授权不能丢

- 用户仅授权 `glm-5.3-flash`，不是 FlashX，不得静默替换模型。设置 `GLM_API_KEY` 后才运行 live/live-demo。
- 用户仍禁止 NVIDIA/Nebius 模型调用。未来即使找到旧密钥或有额度，也不能据此自动恢复；需要用户新的明确授权。
- Tavily 需要 `TAVILY_API_KEY`。无需为了检查启动而重复付费搜索。
- 本轮未将任何 API Key 放进 ZIP。用户说过会撤销临时 Key；新电脑必须重新配置有效凭证。
- `live-demo` 每次运行会真实消耗 GLM，服务限 3 次；`benchmark --provider glm` 最多 3 次推理和 1 次搜索。不要把它们当离线健康检查。
- 比赛平台资格、规则、截止时间应重新核对。GLM 能帮助开发，但不能冒充已满足 NVIDIA/Nebius 赛事要求。

## 9. 下一位接下来做什么

具体代码入口、完成标准和外部依赖见 `FINISH_PLAN_ZH.md`，不要另造一套泛泛计划：

1. 先恢复并做一次基本验证，确认拿到本地新版本而非公开旧版。
2. 核对最新赛事状态和必填材料；已经截止则如实报告，不继续假装能提交。
3. 自动环境/发现链路仍未完成：衔接 sentinel 与受控依赖版本执行，明确支持范围；不要仅把两个固定实现标成两个发行版。
4. CrewAI 安装级复现可独立推进，先做无凭证的序列化测试；当前 dry-run 成功不是安装完成。
5. 任意源码补丁执行须有实际可验证的 OS 隔离；Python audit hook 不够。先完成安全条件，不能直接 exec 模型代码。
6. 真正进入目标平台试验时，再向用户集中说明所需访问/新授权/预算；完成真实推理、平台研究和目标模型评估，不编造问题。
7. 更新可公开版本、跑新提交 CI、补充真实比赛平台演示段、检查评委访问和英语提交材料。尽量复用现有视频资产，别重新录所有内容。
8. 最终提交必须取得用户明确批准，之后保存提交回执。此前最多称“提交材料已准备”。

## 10. 完成的标准、风险和时间

可参赛交付需真实满足规则/资格、指定平台用于实质功能、证据链可复现、新版本 CI 和安装/访问成功、视频和必填材料齐全、实际反馈有依据、最终获批提交。原提示词全部完成还需逐项补齐广泛工程项，不能通过缩小范围声称 100%。

此前粗估集中补齐提交关键路径需 2–4 个工作日，原提示词所有广泛工程能力需 1–2 周或更久；账号/额度/外部审批等待另算。当前仍无法给出可靠获奖概率，也没有核实保证性的参与奖。不要许诺“再一轮额度必定完成”。

Git 普通 HTTPS 推送在本机曾受凭证 helper/网络影响，历史版本通过 GitHub 连接器发布成功。新电脑应使用自己的正常认证，不恢复旧机器凭证，不强推。公开代码仍旧于包内代码；审查远端差异后再推送。

若用户只要保留交接而未要求继续，读完本文后等待即可。恢复开发时每完成一个实质阶段再更新证据，避免反复重录、重复跑全部付费实验和无意义重打包。
