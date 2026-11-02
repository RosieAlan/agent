# D07：LLM Wiki来源版本与引用模型

日期2026-11-02，实际D07/日历D12。本块为用户指定Wiki专项D07来源建模，对接原课documents/document_chunks；摄入、检索、更新、评测实作D13至D16继续。

原始来源已重新核对：https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f 。原模式是LLM持续维护持久Markdown知识页，raw保存来源、wiki保存整理内容、schema规则约束流程；ingest/query/lint分别处理资料/问答/维护，index与log提供导航及演变记录。下述关系数据库设计为本项目教学设计，原文不规定这些表。

目标：必备来源/派生知识分开、引用定位具体来源版本、权限与生效日期；熟练跟踪资料更新及受影响知识页；熟悉内容hash去重、页修订和并发计数的不同用途。

合成例子：广告规范source doc-ad-policy；sv1每日预算300、主管审批，sv2每日预算500且11/05生效、主管审批保留。11/02上传sv2不能自动认定11/02预算500；当前依据sv1，页面应区分当前规则与将生效规则。来源没有明确生效/替代关系时标待确认，产生draft而非直接发布。

五类记录（设计候选，Python尚未实现）：documents为逻辑资料身份，沿用所属userId/租户；document_versions(id,document_id,version_no,content_hash,storage_path,effective_from,effective_to,status)冻结每版原文；wiki_pages(id,owner_id,title,current_revision_id)稳定知识页；wiki_revisions(id,page_id,revision_no,content,status,created_at)保存生成内容及审阅发布结果；wiki_citations(id,revision_id,source_version_id,locator,quote)关联页的具体修订与原文版本/位置。外键/复合租户约束实施时按选定方案落实，业务读写统一校验可访问作用域；外键存在性本身不提供授权。

引用链例：wiki页广告预算→修订wr1→引用c1→source_version sv1→doc-ad-policy→raw/v1原文第3页。R2可同时解释当前和未来规则并分别引用sv1/sv2。document_chunks后续改关联具体source_version，向量检索必须携带版本和权限作用域，原课直接documentId关系保留对照并安排迁移。

文件原型：raw/广告规范-v1.md与v2.md、wiki/广告预算.md、wiki/index.md、wiki/log.md、SCHEMA.md维护规则。本项目用数据库记录用户/版本/发布/引用，原文文件保存于存储中，Markdown页与索引为可生成浏览产物；单一权威内容和发布版本需明确，禁止文件/DB独立漂移。小规模先索引导航，后续可与原文RAG检索组合。

更新链：身份校验→保存新来源版本→定位引用旧版的页修订→生成新草稿→检查冲突/生效/引用/权限→审阅发布页修订与引用→记录变化。哈希辅助同内容重复摄入去重；作用域、解析模型版本和处理状态也纳入幂等判断。普通更新保留旧来源历史；删除/撤回需停止引用及清理或重建派生页和索引，授权删除遵循数据政策，不能以历史保留为由继续使用撤回来源。

需区分：来源版本v1/v2标识原始材料不同内容；wiki revision1/2标识整理页面修订；库存version1/2用于过期提交检测。模型文字持久保存会放大事实错误，引用与审阅必须校验，来源文本作为数据处理，执行指令由受控维护规则提供。

必背：LLM Wiki让模型把原始资料持续整理成可复用、相互关联的知识页。资料更新后追踪受影响页面并产生可审阅修订，每个结论引用到具体来源版本。企业应用还要校验权限、生效日期和撤回状态，并能从答案追溯到原文。

设计综合题与答案：新版上传而未来生效→当前按有效旧版，明确未来规则；回答缺引用→检查页修订/citations/来源位置和权限，来源不足待确认；同一资料再次上传→作用域及hash识别重复，按处理版本/状态判断复用或重跑；删除来源→停止检索和引用并更新受影响派生页/索引。

证据：核对原始设计及本地课表范围；本轮仅设计，无新API/迁移/模型调用/数据库写入。Wiki W01尚待建表和实际引用追溯验收。D07其余报表/任务入库及综合验收继续，完整独立通过1/32。

