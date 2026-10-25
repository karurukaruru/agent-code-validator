# PatchCourt 0.4.0 本轮开发与独立 review

本轮从用户提供的 `PatchCourt-Handoff-0.3.2-20261025.zip` 恢复。
1,257 个文件的 SHA-256 全部与原 MANIFEST 匹配；Git bundle 的基线为
`ea79df842f4e805449f8342d9d381a29243b531a`。原包和 `project/` 快照保留，
实际续开发位于同级 `work/`。本轮按用户当前续开发要求推进；附件中的旧停止、
远端推送和提交说明视为历史材料，没有据此发布或参赛。

本轮本地分支为 `patchcourt/award-build-20261025`；最终提交可用 `git log -1`
核对。安装包在 `release/agent_code_validator-0.4.0-py3-none-any.whl`，可解压的
离线演示在 `release/patchcourt-demo-0.4.0.zip`，哈希见 `release/SHA256SUMS.json`。

## 已完成的实质开发

1. **真实 SDK 双版本执行**：新增 `upgrade-run`，把 ACV 只读仓库发现连接到
   两个真正安装、未经修改的 NVIDIA SDK 1.4.3/1.5.0。39 个共同依赖固定版本；
   显式 `--prepare` 才安装官方 wheel，或从可信本地 wheelhouse 离线安装。
   两侧分别执行并捕获 framework_input / adapter_output，检查原始输入和版本差异。
2. **复用环境必须重验**：校验完整文件清单、SDK 源码、安装报告、当前约束和
   Python/runtime 身份。历史环境、篡改、依赖漂移及未知版本不会通过。
   两个版本同时丢数据时保持 NEEDS_REVIEW，不能因为输出相同判兼容。
3. **流式协议加固**：修复畸形容器引发崩溃、bool/float 索引混入、假值内容被丢弃、
   重复 choice、错误终止状态、缺失或重复调用 ID，以及未知语义被接受的问题。
   合法分片、Unicode、usage-only 尾和常规 token 计数仍支持。
4. **输入和证据保护**：解析工具参数中的敏感字段后再检查；需要脱敏或不支持的
   原始输入不写入报告。依赖和输出目录不参与应用源码扫描。缺失 worker 字段、
   安装失败和平台差异明确记录为不确定。
5. **CrewAI 安装级复现**：完整安装 `crewai[google-genai]==1.15.28`，使用真实
   `BaseLLM` 格式化器及 `google.genai` 的 Part/Content 类型。验证原版丢失两个
   图片数据载荷，固定审查补丁恢复对应字节和 MIME；独立控制与故意损坏第二个载荷的检查通过。
6. **展示与交付**：升级报告直接展示版本、工具调用保留数量、环境、任务和 worker
   证据；桌面和手机均实测。新增 Windows 一键离线启动器、四场景复现脚本、
   Windows/Ubuntu SDK CI 任务和新版 wheel 资源校验。

## 实际验证

| 检查 | 本轮结果 | 可核验证据 |
|---|---|---|
| 完整测试 | **222 passed，4 skipped**；CPython 3.12.13 / pytest 8.4.2 | `evidence/tests/pytest-040.txt` |
| 真实 SDK 四场景 | **4/4 符合预期**：升级 NEEDS_REVIEW、文本 PASS、故障 FAIL、恢复 NEEDS_REVIEW；恢复任务值 21 | `evidence/upgrade-run/real-sdk/matrix.json` 及各子报告 |
| 环境身份 | 两侧均为真实 SDK，39 个共同依赖相同；原始实现未修改 | `evidence/upgrade-run/environment-records/` |
| CrewAI 安装级复现 | **REPRODUCED_AND_REPAIRED**；原版 0 张、修复后 2 张；8 项控制全部通过 | `evidence/crewai-sdk/crewai-sdk-reviewed-local-platform/report.json` |
| 浏览器 | **41 项通过**，Chrome 155；1440 桌面和 390/320 手机宽度无横向溢出、无 JS 错误 | `evidence/upgrade-run/browser/qa-results.json` 和 9 张截图 |
| wheel 隔离校验 | 离开源码导入路径执行 demo、真实子进程及未配置环境的 upgrade-run；固定依赖文件和页面均打包 | `evidence/tests/wheel-verification-040.json` |
| 演示包 | 11 个明确允许的文件；报告版本和页面哈希与新版一致 | `evidence/tests/demo-package-040.json` |
| 密钥扫描 | 已扫描文件中未发现配置凭证值、识别的 token 或私钥标记 | `evidence/tests/secret-scan-040.json`；限定范围检查，不是隐私保证 |
| 导出回归测试 | 生成的 unittest 执行成功 | `python -m unittest discover -s outputs/demo-040 -p test_regression.py` |

4 个跳过是 Windows 不允许创建符号链接/目录链接，保留原原因。
浏览器结果不代表完整屏幕阅读器/键盘无障碍认证。CI 已配置，**本版没有远端 CI
运行记录**；历史公开 0.3.1 CI 不能当作新版结果。

本轮新增模型、搜索或付费 API 请求数为 **0**。官方依赖下载不是模型调用。
CrewAI 使用 `model_construct` 避免凭证/客户端初始化，但真实执行其基类格式化器；
这是安装级序列化证据，不是完整 Agent、Google 客户端或视觉任务成功证据。
SDK 四场景的任务回放是确定性的，不是模型作答。

## Review 发现及修复

独立审查分别覆盖环境/执行链路、协议正确性和实际浏览器体验。
修复了约束或 runtime 改变后仍可能复用环境、嵌套参数脱敏后原始输入仍落盘、
畸形 worker 结果未安全处理，以及上述流式数据漏洞。
在实际隔离环境复现中另修复 Windows 临时 AppData 缺失、native stderr 编码导致
诊断丢失、本机平台信息读取触发审计的问题。NVIDIA worker 保留完整网络/进程
限制；CrewAI 仅允许不产生网络请求的本机 gethostname 读取。

所有有意义的失败尝试均保留：`evidence/upgrade-run/attempts/` 与
`evidence/crewai-sdk/crewai-sdk-*`。首次 inventory 字典的敏感文件名被通用脱敏器
误改，后改为带 path/hash 的列表；后续增加 runtime 校验引发的 Windows 审计失败
也保留在旧矩阵中。没有把这些失败改成成功记录。

## 打开和复现

Windows 双击 `Start-PatchCourt.cmd`。或运行：

```powershell
python -m patchcourt demo --output outputs/my-demo
python -m patchcourt serve outputs/my-demo --port 8765
```

先安装当前项目，再运行真实升级/文本对照/修复恢复的完整验证：

```powershell
python -m pip install -e .
python scripts/verify_sdk_upgrade.py --environment-dir outputs/my-sdk-envs --prepare --output outputs/my-sdk-matrix
python examples/reproductions/full_sdk_crewai.py --sdk-root .sdk-crewai --output outputs/my-crewai-run
```

CrewAI 依赖单独安装，不要混入项目 venv：

```powershell
python -m pip install --target .sdk-crewai 'crewai[google-genai]==1.15.28'
```

准确固定版本见成功记录中的 `requirements-resolved.txt`；本次共有 142 个分发包。
图片载荷用于字节传递测试，其中 JPEG 标记载荷为 8 字节；本轮不验证其图像解码有效性。
原版问题来源是 [NVIDIA #387](https://github.com/langchain-ai/langchain-nvidia/issues/387)
和 [CrewAI #8434](https://github.com/crewAIInc/crewAI/issues/8434)，均为已公开问题。
不宣称新发现、上游合并或与用户过去 PR 有关系。

## 获奖与正式交付仍差什么

按 2026-10-25 重新读取的[官方规则](https://nebiusglobalaihackathon.devpost.com/rules)
和[比赛主页](https://nebiusglobalaihackathon.devpost.com/)，截止为新加坡时间
**2026-10-31 01:00**。比赛要求真实使用 NVIDIA 开源模型及 Nebius 平台；当前
新增工程与旧 GLM 演示不能代替该要求。

- **BLOCKED / 未实测**：指定平台/模型的真实推理、模型贡献、平台可靠性实验和反馈。
  需要合法账号、明确可用的访问和预算后再做；本轮没有寻找或恢复旧密钥。
- **未完成**：跨多个独立任务的 ASM 量化评估、Nemotron 对比实验，以及能证明
  Tavily 对结果有帮助的重复实验。保留旧搜索没有提升的结果。
- **范围外仍缺**：任意 SDK/任意仓库执行、通用框架请求与返回录制、任意模型源码
  补丁的 OS 级隔离。当前受控执行不能冒充这些能力。
- **尚未发布/提交**：新版远端 CI、公开新版安装/演示、比赛平台视频段和公开视频、
  登录后的实际表单及参赛人资格。最终提交需用户批准；本轮没有提交或对外发消息。

当前是有新增核心能力、独立审查和真实复现的开发交付，不能保证获奖，也不能
称原始大范围任务或正式参赛已全部完成。
