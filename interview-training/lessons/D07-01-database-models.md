# D07：从写死库存到数据库建模。日期：10/26

原课程5.1、5.2、5.3及2章存储：PostgreSQL持久化业务/消息/文件元数据/任务，用户系统由原user-system维护；chat库只保存user_id不额外重复建用户，跨服务用户id不设本地User外键。原conversations/messages/documents/document_chunks/task_events五核心表全部保留去向，向量细节D13；本单元完整覆盖SQL/关系/事务/索引/作用域/会话任务/Wiki来源模型；Prisma Schema和迁移解释后映射SQLAlchemy2/Alembic。

第一块聚焦店铺与库存；实际数据源仍标synthetic_demo，存入真实数据库不会使样例变真实业务数据。模型继续只传sku，工具后端查询数据。当前sku唯一演示，真实查询要用服务端确认的user/store范围。两店同sku独立，用UNIQUE(store_id,sku)。

表=同类记录，行=一条记录，列=字段；SQL=数据库指令；PRIMARY KEY=唯一定位且非空；NOT NULL=必填；REFERENCES=外键引用现存店铺；CHECK=约束数值；UNIQUE=字段组合不能重复。

以下为目标建表设计，实际PostgreSQL初始化/配置和迁移下一块接入；学生本轮先读懂关联，业务源码保持原样。

```sql
CREATE TABLE stores (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL
);

CREATE TABLE inventory (
    id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL REFERENCES stores(id),
    sku TEXT NOT NULL,
    stock INTEGER NOT NULL CHECK (stock >= 0),
    threshold INTEGER NOT NULL CHECK (threshold >= 0),
    data_source TEXT NOT NULL,
    UNIQUE (store_id, sku)
);
```

本地SQLite内存仅验证通用主键/外键/唯一/非负约束，真实PostgreSQL与API联调尚待进行。调用目标/ads/chat→run_ad_tool→inventory_tool→库存查询服务→PostgreSQL→字典→ToolMessage→模型答复。文件职责：main入口；llm_service编排；ad_tools工具；后续db.py连接及会话、models.py数据模型、repository.py查询函数，增加文件时给完整调用图。

必背：数据库持久保存业务记录，表模型表达实体和关系；店铺归属服务端确认用户，库存按店铺加SKU唯一，查询同时校验所属用户/店铺。检查相同SKU不同店铺可以独立保存；同店同SKU重复插入受唯一约束拦截。
