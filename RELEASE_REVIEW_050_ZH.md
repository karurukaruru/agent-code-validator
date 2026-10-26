# PatchCourt 0.5.0 开发与提交审查

用户要求继续原 Nebius × NVIDIA 比赛并完成可提交作品。原交接包中停止 NVIDIA 调用的约束是历史；新请求已明确继续比赛，Nebius 访问待用户补充。项目尚未宣称完成正式提交。

## 本轮已完成

- 接入用户指定的 DeepSeek Flash 与 Tavily；精确模型选择，不自动切换服务商。
- 真实模型提出有界字段映射；独立验证八项控制、故意损坏的修复和实际工具会话恢复到 21。
- 请求及返回模型身份、assistant 协议、finish_reason、refusal、原始 HTTP 与解析结果严格检查。
- 每个失败尝试也保留证据；预算在 HTTP 前预留，跨进程文件锁、重读与原子写入避免超额。
- 缓存绑定源代码、环境、验证器与模型；命中后仍执行验证、损坏负控及模型工具会话。
- 实验评估预先冻结 12 个开发者编写的案例，保留五组配对结果、失败和未知用量；不冒充独立盲测。
- 免费静态评委入口明确标注录制回放，提供实际 SDK 比较、请求证据和独立复验说明。
- 英文参赛稿、反馈稿、评委说明与提交检查器已准备；缺证据门槛不会误报通过。

## 已有真实开发证据

[evidence/development-050](evidence/development-050/README.md) 保存七次 DeepSeek 模型请求与两次 Tavily basic 搜索。首次流程 4094 tokens；重复流程 2816 tokens 但 cache MISS，因为源码仍在变化，不能据此声称缓存节省或性能提高。这些报告原样保留 0.4.0 版本标签，不能当作冻结 0.5.0 实验。

0.4.0 真实 SDK 双版本环境、CrewAI 格式化修复和流式协议验证证据继续保留。它们证明本地 SDK 边界，不证明 Nebius 平台推理。

## 本地验收

- 全量 **333 passed / 4 skipped**（Windows 链接权限），`evidence/tests/pytest-050.txt`。系统代理导致的两项旧ACV本机HTTP测试502，在明确NO_PROXY仅排除loopback后均通过。
- SDK双版本四场景 **4/4** 得到预期结果，`evidence/upgrade-run-050/real-sdk/matrix.json`，零模型调用。
- 隔离wheel安装资源与CLI验收通过，`evidence/tests/wheel-verification-050.json`。
- 评委导出包 **22项Chrome检查** 通过，含手机布局、第二次重放清空状态和无推理服务请求。
- **137秒** 英文配音/字幕开发样片已完整解码和视觉检查，明确DeepSeek与录制回放；它不是正式Nebius视频。

## 公开交付与远程验收

公开源码为 `e3aa4bd47edd8b4f20d100b66e2d27833c90bac2`，开发评委ZIP、wheel、137秒样片均匿名下载并与已审查字节一致；下载ZIP重新启动通过。证明在 `evidence/submission/public-*-050.json`。公开内容不需要评委购买API访问。

[远程CI run40260807511](https://github.com/karurukaruru/agent-code-validator/actions/runs/40260807511) **4/4 jobs成功**：Python3.10、3.13各337项通过；Ubuntu、Windows各4项SDK场景符合预期。每项均核对相同源码commit，证据 `evidence/tests/github-actions-050.json`。当前提交检查器10项PASS、5项BLOCKED；待补项来自正式平台、视频/YouTube、反馈与参赛人表单。

## 正式提交尚需

1. 用户补充可用 Nebius 访问后，在冻结代码上实际运行 NVIDIA Nemotron；保存原始请求、失败、模型身份与环境。DeepSeek 不能替代。
2. 完成指定平台的重复试验、确切缓存命中和反馈技术审阅；实测若无缺陷也如实报告。
3. 发布最终源码与免费评委测试构建，验证公开访问和 CI。
4. 完成英文小于三分钟的正式演示，检查真实平台归属，发布公共 YouTube 链接。
5. 在认证 Devpost 表单核对实际字段、参赛人资格、版权和最终提交。当前不自动提交，也不替用户填写未经确认的资格声明。

本地提交检查命令：`python scripts/submission_check.py`。BLOCKED 表示有真实待补项，不应删除检查或填造证明来达到 READY。
