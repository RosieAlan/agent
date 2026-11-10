# 运营助手部署与运维

本目录把 Vue 工作台、FastAPI、独立任务 Worker、MySQL、PG/pgvector 与 Elasticsearch 部署到同一台 Linux 主机。业务数据为 synthetic_demo；企业账号权限与外部业务连接器继续按课程上线专项接入。

## 发布顺序

在项目源码根目录构建版本镜像；资源较小的服务器可在开发机构建，再通过 `docker save`、SCP、`docker load` 交付。私密配置存入 `.env.production`，权限设为600，凭据与备份均由Git忽略。

```bash
cd infra/deploy
export COMPACT=1 COMPOSE_PROGRESS=plain
bash create-auth.sh admin
bash dc.sh config --quiet
bash dc.sh up -d mysql postgres search
# 等数据库健康，再执行一次性增量迁移。
bash dc.sh run --rm --no-deps migrate
bash dc.sh up -d --no-build --wait --wait-timeout 180 api worker gateway
bash dc.sh ps
```

`COMPACT=1`启用资源上限；数据卷及网络使用独立Compose项目名。MySQL、PG、ES仅在内部网络监听，网关默认绑定服务器127.0.0.1:8088。首次发布后定时计划处于关闭状态，由工作台保存后生效。

## 私有访问与HTTPS

本机终端执行下列命令并保持运行，浏览器访问 `http://127.0.0.1:18088`，输入独立网关账号密码。

```powershell
ssh -N -L 18088:127.0.0.1:8088 root@123.207.247.84
```

域名解析和有效证书准备后，使用`compose.tls.yml`提供HTTPS入口。公网企业使用前落实用户认证、数据范围授权、审批审计、限流及备份异地保存。当前BasicAuth用于私有演练入口，用户/租户级业务授权单列验收。

## 日常排查

```bash
export COMPACT=1
bash dc.sh ps
bash dc.sh logs --tail 100 api worker
docker stats --no-stream
bash dc.sh restart worker
```

`/health/live`检查进程；`/health/ready`检查业务表和已启用知识库；Worker通过数据库心跳验活。请求日志带request_id、路径、HTTP状态与耗时；容器日志每份10MB、最多3份。可观测平台、报警通知、长期压测仍按后续课程专项完成。

## 备份与恢复演练

```bash
bash backup.sh
# 用上一步输出的目录；脚本在独立临时数据库恢复并查表，然后清理该临时库。
bash verify-backup.sh backups/实际时间目录
# 真正恢复前预览目标；执行需要明确匹配数据库名。
bash restore.sh --target mysql --file backups/实际时间目录/mysql.sql --database ops_assistant
```

MySQL使用事务一致性导出；PG使用自定义格式。PG恢复后把所有文档登记为关键词索引待办，下次检索或`python -m scripts.sync_knowledge_search`重建ES。定期把加密备份复制到独立存储并验证恢复。

## 版本与CI

`release.sh 新版本 上个版本`构建、启动并等待健康；失败时尝试恢复上个镜像版本，数据库迁移保持向前兼容。首次部署使用`first`，数据库回滚需要单独经过恢复方案。

仓库`.github/workflows/operations-check.yml`负责Python编译、Vue类型检查/构建、Compose与Shell检查、镜像构建；GitHub实际运行结果在推送后查看，云端部署仍由当前受控发布步骤执行。

MySQL8默认认证采用RSA依赖，requirements使用`PyMySQL[rsa]`，依据[PyMySQL官方安装说明](https://pymysql.readthedocs.io/en/latest/user/installation.html)。Vue检查使用与现有vue-tsc兼容的TypeScript5.9.3并锁定版本，依据[Vue TypeScript说明](https://vuejs.org/guide/typescript/overview)。
