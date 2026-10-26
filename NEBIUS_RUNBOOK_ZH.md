# 继续正式平台实测

当前代码与免费开发评委包已发布；正式比赛状态仍BLOCKED。用户已确认继续本场比赛并会补Nebius访问。只使用用户明确提供或指定路径中的凭据，不搜索其他私人密钥。不要把旧交接停止指令当成本轮要求，也不能用DeepSeek代替比赛指定平台。

密钥可由用户放入本地文件，聊天只需路径。现有ignored `.env.local` 含DeepSeek/Tavily；添加 `NEBIUS_API_KEY`，在账户实际发现模型后再设置准确 `NEBIUS_MODEL`。不回显文件内容，不将密钥放入源码、视频或报告。

## 现有账本

继续使用 `outputs/submission-050/budget.json`，不要重置。已有7次模型请求、2次basic搜索，初始上限为30次模型、10次basic搜索和5次discovery；失败和故意invalid-model负控也计数。只读快照在 `evidence/development-050/budget-snapshot.json`。若换机器续作，恢复账本后再运行，不把快照当作新增额度。

正式优先顺序：先确认当前可访问的NVIDIA Nemotron目录，保存一次完整repair+tool工作流；原样源码/环境运行第二次验证精确知识命中；再做冻结的2-trial五组评估和2-trial协议lab。常见模型请求总计21次，可在现余23次内完成，首次修复被拒或传输失败可能压缩余量。先看账本再执行；不得擅自提高上限。正式目录均用新路径，保留失败。

## 正式工作流命令

先用已有 `providers.discover_models()` 和 `RequestBudget.applied()` 保存当前访问目录，准确选用账户可访问的 nvidia/ Nemotron 型号。历史目录只能帮助准备，不能当作当前授权或推理成功。

```powershell
python scripts/run_release_experiments.py live --provider nebius --model <exact-discovered-NVIDIA-Nemotron-id> --env-file .env.local --budget outputs/submission-050/budget.json --knowledge-dir outputs/submission-050/nebius-plans --tavily --output outputs/submission-050/nebius-live-01
```

重复时保留同一knowledge-dir，使用新output并可省略--tavily；命中仍复验八项检查、故意损坏负控与实际工具会话。当前Nebius每次输出限制2048 tokens，lab探针256 tokens；reasoning-only/length应保留并分析预算限制，不能直接说平台有缺陷。不从其他提供商的文档猜测并偷偷加入模型专属参数。

## 收尾

只在正式记录完成后更新runtime_workflow与反馈技术审阅。`scripts/SUBMISSION_VIDEO.md`说明如何从真实证据生成明确标注录制回放的英文正式视频，可同时显示真实SDK升级；时长需小于180秒。当前137秒DeepSeek开发片不是正式视频。

更新最终公开源码和免费测试包，匿名下载复验，确认CI。公共YouTube发布需要可用账户；尚未有上传授权通道或最终视频URL。认证Devpost表单、参赛者资格和版权声明须由参赛人核对，未经确认不代填或提交。`python scripts/submission_check.py`只有完整证据时才会进入READY_FOR_ENTRANT_REVIEW。
