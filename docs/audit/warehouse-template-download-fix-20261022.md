# 碳活动填报模板下载修复

日期：2026-10-22。环境：`https://warehouse.nexlca.com`，华为 `/root/warehouse`。

## 原因与修复

客户账号可以访问碳活动分类和导入页面，但下载空白模板的 GET 接口
`/api/ghg-inventory/import/template` 错误地仅要求 `carbon.inventory.import`。
线上安方、祥泰两个租户均复现 HTTP 403（Insufficient privileges）。

下载接口改为接受 `carbon.inventory.view` 或 `carbon.inventory.import`，与模板只读行为一致。
导入预检、提交依旧要求导入权限。未修改账号角色、租户权限、业务数据、计算方法或模板内容。

## 验证

- 45项定向单元测试通过：36组分类/方法组合的模板生成、4项既有工作簿预检测试、5项权限边界测试。
- Ruff检查、格式检查及`git diff --check`通过。
- 线上客户账号两个租户各36次下载，共72次HTTP 200；验证Excel MIME、附件响应头、工作簿可解析、分类/方法/组织/设施等元数据与请求一致。
- 未登录下载HTTP 401。
- 应用健康检查成功，重启次数0，发布后检查未发现新增ERROR/Traceback/Exception日志。
- 浏览器工具启动超时，本次线上验收使用真实客户登录后的HTTPS下载和Excel解析，不声称完成浏览器按钮点击验收。

## 发布与回滚

本地源码基线为`c4fbe47a`，发布前与线上控制器原文件SHA-256一致：
`df66da395c2bcedd5681f3d1afc562f8d209483e689b127e05f08ed15d701c75`。

完整构建因基础依赖下载等待而中止，随后通过仓库构建脚本制作单文件补丁镜像。
镜像仓库TLS握手超时，未完成推送。最终通过SSH传输已验证控制器和Dockerfile，
以服务器当前生产镜像为基础离线构建，仅COPY这一个控制器文件。

- 运行镜像：`warehouse-carbon:template-fix-20261022`。
- 运行image ID：`sha256:e2526895902490ddd35288e02661c4454d0c2ba90341526d6529d0d11c95f6ce`。
- 新控制器SHA-256：`80480e80c8d7d60beea51b3125a924e142662357d564e1b31f1aed0ad39dd729`，线上与本地一致。
- 补丁构建材料：`/root/warehouse/releases/template-download-20261022`。
- 原配置备份：`/root/warehouse/backups/template-download-20261022`。
- 回滚镜像：`warehouse-carbon:rollback-template-20261022`。
- 修改APP_IMAGE并验证Compose配置，仅重建app；worker、mqtt-ingest-worker、缓存和EMQX未重建。无数据库迁移或数据修复。
- 回滚时恢复备份`.env`，在`/root/warehouse`执行`docker compose config --quiet`和`docker compose up -d --no-deps --pull never app`。
- 当前补丁镜像仅保存在生产服务器及本机构建环境，未推送镜像仓库；后续正式发布须包含本次源码修复。首次上线时尚未提交Git；随后按用户要求将控制器修复、两份测试文件和本记录作为独立提交纳入版本管理。

本地验收材料位于gitignored `.storage/template-download-20261022/`：
`online-download-checks.json`、样本Excel、构建日志、部署日志与验收脚本。
