# 候选结果输出约定 v2

用户正文推荐名单只列身份/历史/Amazon价格与有效卖家门槛通过的产品，然后逐款附1688搜索包。未通过Amazon关的记录不叫推荐，可在方法测试中列统计、失败原因及队列附件；用户明确询问某款怎么搜时仍交搜索包并标未通过。不能把通用搜索教程代替逐款词。

保存批次用 `schema_version: 2`，结构见 [example-candidates.json](../assets/example-candidates.json)。旧v1记录保留原始历史，不能作为v2通过证据；示例当前仍是未通过记录，不能据此报告现价或推荐。

## 每款必填

- `id`、`part_number`、`product`、`identity`：完整范围、适配、左右/数量及核验程度。
- `status`：五种状态之一，`reason`说明依据；优先级不代替状态。
- `evidence`：URL、观测日期、事实、层级；没有证据的值用null，不补造。
- `checks`：identity/history/price/competition/demand/supplier，每项PASS、FAIL_OBSERVED、UNKNOWN或NOT_APPLICABLE。
- `missing`：field、cause、owner、needed。缺项写清需要什么来改变判断；INPUT_NOT_PROVIDED用于未给历史清单等输入，未知关系不冒充CONFLICT。
- `search_1688`：每款必有，以下字段不能省略。
- `amazon_gate`：每款必填，用逐卖家报价支持门槛，不允许只给总数。

## Amazon卖家硬筛字段

- `status`: PASS / FAIL / UNVERIFIED，`seller_limit`: 10（本版只允许收紧至1–10，不可偷偷放宽）。
- `coverage`: COMPLETE / PARTIAL / UNAVAILABLE；`delivery_zip`: 实际确认值，PASS要求10001。
- `queries`: 实际查询对象，字段query、source_url、observed_at、coverage（COMPLETE或PARTIAL）。未执行不能列已查；是否完成含相关结果分页、同款详情和其他报价。
- `offers`: 逐报价对象，字段seller_id、asin、url、observed_at、match（EXACT/OTHER/UNKNOWN）、availability（ACTIVE/INACTIVE/UNKNOWN）、price_state（NORMAL/ABNORMAL/UNKNOWN）、item_price_usd、shipping_usd、evidence。未知价格/运费用null。ABNORMAL必须附exclusion_reason；不能因正常低价排除。
- 包装附加字段不改变schema v2必填结构：`pack_quantity`为每包相同完整替换件数量（正整数，未知null）；`unit_price_usd`为有限非负数或null。逐报价应记录包装数量，可用这两个可选字段；`item_price_usd`始终保留整包商品价，数量已确认时单件折算价为item_price_usd / pack_quantity，运费另列。未知数量不得假设1；包装不明须把match标UNKNOWN，阻止PASS。现有校验器允许这些附加字段，但不校验数量、除法或包装事实，需复读证据确认。
- `seller_id`默认记录页面实际卖家账号ID。唯一的直营归一例外：美国站明确显示“Sold by Amazon.com”且没有seller链接时，可填`AMAZON_US_RETAIL`；evidence必须说明它是本地保留归一键、保存页面售方原文与来源，不冒充平台opaque ID。不同ASIN的该键只计一个直营账号；禁止猜ID或将FBA/“Ships from Amazon”当作直营售方。

同seller_id跨ASIN及包装数量去重，不同seller_id即不同竞争卖家，不合并公司。相同完整替换件单只/双只/多只装均可EXACT并计入同品竞争，不按内含件数多计账号；只有实际零件、部位、适配或总成不同才据身份标OTHER。有效下界为EXACT+ACTIVE+NORMAL且正商品价的唯一账号；其他未明确排除行构成潜在上界。确认有效>10即可FAIL；PASS要求完整覆盖、无未解报价、至少1个且最多10个有效卖家。没有实际报价不能PASS。页面事实仍需人工式复读，校验器不验证网页真伪或覆盖声明真实性。

`checks.competition`须对应PASS→PASS、FAIL→FAIL_OBSERVED、UNVERIFIED→UNKNOWN。FAIL的候选必须停止，不能留成候选推荐。用户提供23卖家但没有逐行截图时，可按用户证据记录排除，不能伪造23行报价来使gate FAIL；gate保留UNVERIFIED，整体状态按用户反馈停止。

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

`REVIEW_READY`及`QUALIFIED_SCREENING`均强制identity/history/price PASS且amazon_gate PASS。REVIEW_READY仅需求/货源等末尾人工项可UNKNOWN，不能将缺Amazon计数包装成人工复核卡。无明确失败且BUDGET_NOT_RUN的候选留QUEUED_INCOMPLETE。缺Amazon访问同样不准进入推荐。校验器无法核网页真伪或用户接受记录是否真实。

默认保留到工作区的 `outputs/<本轮名称>/candidates.json` 和 `report.md`，同步现有状态表/LOG/TODO。不要为每轮再造一套互不兼容的字段，也不要把用户账号、私有浏览器状态或完整旧项目数据提交skill仓库。
