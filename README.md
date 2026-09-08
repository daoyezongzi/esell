# ESell

把维修配件选品整理成可复用的 Agent Skill：外部发现具体件号、历史去重、实物/适配核对、Amazon竞争与eBay需求筛选，最后交人工复核。

**每款结果都要说明如何在1688搜索**：准确件号和写法、确认替代号及依据、中文组合词、图片来源、完整实物检查点。建议搜索和已确认货源严格分开。

## 使用

让助手读取 [skills/esell-sourcing/SKILL.md](skills/esell-sourcing/SKILL.md)，提供当前任务和历史状态文件。若已在使用环境注册该skill，可用 `$esell-sourcing` 调用；仅克隆仓库不代表它已注册到所有助手。

示例请求：

> 使用 esell-sourcing，找非拉线的割草机和老商用卡车维修件，搜索约8分钟。能查的自动查，缺数据留最后人工；每款结果附可复制的1688搜索词和实物核对点。

> 按 esell-sourcing 为 A17-13787-002 生成1688搜索交接，不重新做整轮市场搜索。

## 内容

- [Skill入口](skills/esell-sourcing/SKILL.md)
- [默认规则](skills/esell-sourcing/references/profile.md)：价格、竞争、需求和用户范围，可被本轮明确要求覆盖。
- [市场核查](skills/esell-sourcing/references/market-checks.md)：计数、时间窗、停止及缺项处理。
- [1688怎么搜](skills/esell-sourcing/references/1688-search.md)：件号、中文、图片和三个历史示例。
- [输出约定](skills/esell-sourcing/references/output-contract.md)与[候选JSON示例](skills/esell-sourcing/assets/example-candidates.json)。

批次文件校验（Python 3标准库，无网络或付费API）：

```powershell
python skills/esell-sourcing/scripts/validate_candidates.py skills/esell-sourcing/assets/example-candidates.json
```

此仓库是工作方法和交付规范，没有捆绑抓取服务、平台账号或付费市场接口。浏览器/搜索工具使用运行环境已有能力；缺数据按实际原因记录，费用和利润由用户后续核实。研究不包含联系商家、询价消息或采购。

方法来源是2026-09-08的实际流程复盘：12项历史边界校准、20条新线索及2款市场抽样。它支持可执行的初筛和证据交接；没有验证稳定推荐率、人工节省或盈利。详细当前检验见[LOG.md](LOG.md)。
