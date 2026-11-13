// 镜像只在数据目录首次初始化时执行此脚本。
db = db.getSiblingDB("knowledge_hub");

db.createUser({
  user: "knowledge_hub_user", // 后端连接knowledge_hub时使用的业务账号。
  pwd: "knowledge_hub_password",
  roles: [{ role: "readWrite", db: "knowledge_hub" }],
});

db.createCollection("kh_document"); // 按当前课程截图创建文档集合。
db.createCollection("kh_chunk"); // 按当前课程截图创建分块集合。
