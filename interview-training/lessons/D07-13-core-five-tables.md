# D07：原课5.3五张核心表与关联设计

日期2026-11-02。实际D07/日历D12。已逐项核对原文5.3.1、5.3.2、5.3.3。

先校正：version只负责提交修改时的过期版本检查；普通查询的数据可见性由事务隔离决定。学生此项表达仍需综合题复测。

必备：conversations绑定用户；messages按conversationId归属会话；documents绑定上传用户并记录文件处理状态；document_chunks按documentId归属文件并保存content/chunkIndex/embedding；task_events保存异步任务事件与时间顺序。

一对多：一会话多消息、一文档多分块、一业务任务可有多事件。用户来源于服务端校验登录凭据后的身份；先限定userId和conversationId，再读取消息；分块通过JOIN documents限定userId后检索。当前Python库存服务身份仍演示值，五表尚未迁移接入。

字段全貌沿原课：conversations(id,userId,title,createdAt,updatedAt)；messages(id,conversationId,role,content,metadata?,createdAt)；documents(id,userId,filename,mimeType,size,filePath?,storageType,status,chunkCount,createdAt)；document_chunks(id,documentId,content,chunkIndex,embedding?)；task_events(id,userId,taskType,taskId,status,message?,metadata?,createdAt,readAt?)。

Prisma标记解释：@id主键，@default默认值，?可空，[]集合关系，@relation通过关联字段定义关系，@@index索引，@updatedAt由Prisma更新时维护（Python映射需独立实现），enum约束固定取值。对照SQLAlchemy mapped_column(primary_key=True/nullable/server_default)、ForeignKey(ondelete)、Index和对应关系。字段命名映射明确后才写迁移；本块仅设计讲授。

设计细节：会话删除级联消息、文件记录删除级联分块；对象存储文件及外部向量副本清理由业务另安排。documents.status用字符串便于扩展，业务仍校验状态转换；role和TaskStatus原课用枚举。embedding可空支持先分块后向量化，检索过滤NULL并匹配模型/维度版本；切模型需重算存量向量、规划索引和分库/列策略，具体D13-16。跨微服务userId采用字符串关联，身份有效性和删除协调由服务负责。

task_events允许同taskId多行记录pending/processing/done/error；每行id独立，taskId聚合一次业务任务，metadata可记录documentId等；事件表用于进度/历史，状态恢复另需任务/检查点设计。任务记录与SSE实时推送应分别保存/发送；失败恢复和可靠投递后续展开。

完整调用链：上传SOP→校验登录→documents登记pending→创建task_events→解析分块存document_chunks→向量化完成更新documents→保存完成事件并推送；用户聊天→鉴权验证conversations→读messages→检索当前用户documents的chunks→模型→写messages→返回。各数据库事务保持短，外部模型处理在事务外，失败状态如实记录。

教学示例文件、会话及事件均为设计示意，尚无新增数据库运行证据。本块不修改业务文件；前块事务学生结果待收。下一块Wiki来源/版本引用数据模型，再按计划实现报表/任务入库及综合验收。完整独立通过1/32。

