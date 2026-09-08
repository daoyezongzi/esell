# 候选结果输出约定 v1

用户正文以简短表格列产品/件号、市场证据、状态和下一步，然后逐款附1688搜索包。不能只在附件藏搜索词，也不能给一段适用于所有产品的泛泛搜索教程。

需要保存批次时输出JSON，结构见 [example-candidates.json](../assets/example-candidates.json)。示例是历史事实的结构演示，不能据此报告现价、供应商或当轮合格品。

## 每款必填

- `id`、`part_number`、`product`、`identity`：完整范围、适配、左右/数量及核验程度。
- `status`：五种状态之一，`reason`说明依据；优先级不代替状态。
- `evidence`：URL、观测日期、事实、层级；没有证据的值用null，不补造。
- `checks`：identity/history/price/competition/demand/supplier，每项PASS、FAIL_OBSERVED、UNKNOWN或NOT_APPLICABLE。
- `missing`：field、cause、owner、needed。缺项写清需要什么来改变判断；INPUT_NOT_PROVIDED用于未给历史清单等输入，未知关系不冒充CONFLICT。
- `search_1688`：每款必有，以下字段不能省略。

|1688字段|内容|
|---|---|
|status|NOT_SEARCHED / SEARCHED_NO_MATCH_IN_SCOPE / MATCH_PENDING / MATCH_CONFIRMED / ACCESS_UNAVAILABLE|
|part_number_terms|准确件号原写法与去符号写法，逐个搜索；不得用待确认别名替换主号|
|confirmed_alias_terms|每项term+basis+confirmation_level（manufacturer或dealer）；表示来源明确的对应关系，不代表供应实物已核；没有填空数组|
|unconfirmed_aliases|待核号及疑点；不计既定互换、不用于合并竞争|
|chinese_terms|至少2条针对该产品的中文/中英组合词|
|image_search|reference_url可为空，但必须有instructions；缺准确图源就明确让用户用其准确目标图，不伪造|
|physical_checks|至少2项针对该产品的核对点|
|do_not_confuse|至少1项易混产品、规格或范围|
|searched_queries|实际在1688输入的词；没搜过用空数组，不把建议词当已执行词|
|supplier_urls|实际观察到的供应商商品详情；未实查填空数组|
|match_evidence|支持完整实物匹配的证据说明；未匹配可为null|

`NOT_SEARCHED`不得携带“已搜”查询或供应商结果。`MATCH_CONFIRMED`需要实际查询、真实详情URL及实物匹配说明；不能只凭件号或匹配标题。SEARCHED_NO_MATCH_IN_SCOPE只能描述已查范围。

报告里把供应匹配与搜索方案分开：货源没查不妨碍给出查询词；给出词不意味着供应已通过。已排除条目若作为审计结果列出，明确“停止研究，不建议再搜索”；不能通过搜索方案重推用户排除。

`QUALIFIED_SCREENING`需要所有适用项PASS，或有用户明确接受的需求例外：在`exceptions`数组保存`check: demand`、`accepted_by_user: true`、`basis`、`acceptance_record`（用户决定的可追溯出处）。原始年度未知仍保留，不能改成年量通过；已被用户接受的例外不再列为未解决筛选缺口。其他门槛修改应显式记录本轮规则，不能借需求例外绕过历史排除。

`REVIEW_READY`可以有UNKNOWN，但剩余均为明确人工项；没有明确硬性失败而BUDGET_NOT_RUN的候选留QUEUED_INCOMPLETE。校验器无法核网页真伪或用户接受记录是否真实，结论还需阅读证据。

默认保留到工作区的 `outputs/<本轮名称>/candidates.json` 和 `report.md`，同步现有状态表/LOG/TODO。不要为每轮再造一套互不兼容的字段，也不要把用户账号、私有浏览器状态或完整旧项目数据提交skill仓库。
