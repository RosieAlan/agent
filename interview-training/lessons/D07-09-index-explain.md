# D07-09 库存索引与执行计划（2026-11-02）
学生提交冲突409；教师只读确认实际库stock20/version2，之前25/1→当前20/2加冲突证据已收，成功HTTP200输出仍未单独提交。版本接口本地闭环有运行证据，完整D07其他内容继续。
辅助编辑：VSCode Windows Shift+Alt+Right逐级扩大语法选区，Shift+Alt+Left缩小；重复到目标函数，Ctrl+K Ctrl+S查绑定；Ctrl+A全文件需辨别。
原5.3查询/索引及岗位慢查询要求：索引提供按列组织的查找路径，联合索引store_id,sku适合按店铺商品定位。唯一约束已经建立同列唯一B-tree索引，当前无需重复创建。WHERE权限与版本检查继续保留；id主键索引查id，联合索引查店铺商品。
DBeaver SQL编辑器逐句执行：
```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public' AND tablename = 'inventory';
```
```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT i.stock, i.version
FROM inventory AS i
JOIN stores AS s ON s.id = i.store_id
WHERE s.user_id = 'user-001'
  AND i.store_id = 'store-A'
  AND i.sku = 'SKU-DEMO-001';
```
EXPLAIN显示计划，ANALYZE实际执行并收集行数时间，BUFFERS显示读缓存/磁盘页情况。此处SELECT只读；对UPDATE DELETE使用ANALYZE会真实执行修改。看Index Scan/索引名、actual rows、loops、Execution Time；cost为估计开销且非毫秒，actual time和Execution Time单位毫秒。缓存命中不是应用cache；Seq Scan在小表或大量结果时也可能合理。按实际数据量和统计信息评估，避免强制用索引。
教师只读实际结果：inventory_pkey(id)，inventory_store_id_sku_key(store_id,sku)；当前计划库存用联合索引Index Scan，店铺用stores_pkey再过滤user_id，结果1行，单次执行0.470ms。单次小数据结果只作观察，线上性能需代表性数据与多次测量；业务源码及数据未改，模型API0次。
索引提高匹配查询效率，同时占空间并增加写入维护开销；按查询、排序和约束需求建立并验证。左侧列顺序与条件组合影响联合索引效果，store_id条件通常适用前缀，跨店仅sku需结合实际计划另行评估。
必背：通过EXPLAIN ANALYZE检查数据库访问路径、实际行数和耗时，先结合数据量确认慢在哪里，再针对WHERE/JOIN/排序设计索引并复测，考虑写入成本；ORM查询也需要同样分析。
学生贴两条SQL结果并说明用到的索引即可。后续慢查询大数据演练、连接池/事务与原核心模型仍保留。

