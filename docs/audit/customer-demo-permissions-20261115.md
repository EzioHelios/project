# 沃衡客户演示账号权限与验收

## 账号范围

客户演示角色为 `energy-carbon-customer-demo`。账号只加入沃衡汽车泰州生产基地、湖州生产基地，均为普通成员。账号不授予超级管理员、租户所有者或系统管理角色。

| 功能范围 | 页面与可体验的操作 |
| --- | --- |
| 能源消费、强度、用能分析 | 能源事实录入、编辑、删除、导入、查询及分析 |
| 能效对标、能流、平衡、预算 | 标杆和预算维护、平衡边界配置、计算与分析 |
| 组织碳排放 | 排放源与分类活动维护、导入、生成、因子选择、核算、报告草稿和导出 |
| 产品碳足迹、供应链碳 | 产品、产量、价格、资源绑定、物资作业及研究/填报任务维护 |
| 核查支撑、碳资产 | 核查项目与资料整理、导出，资产及履约数据维护、成本测算 |
| 配套主数据 | 授权基地的企业、区域、设备、经营活动、企业自有因子 |

工作台按七项能源功能、五项碳管理功能展示。配套主数据入口是这些功能的录入入口，不另授予系统管理权限。能源种类与单位换算属于全局字典，客户只能查看。官方因子库沿用既有所有权校验，客户不能修改官方因子。

不开放系统管理、租户创建、平台任务、微电网、监测告警、视频识别、独立大屏、移动工作台、气候披露和减排扩展模块。报告审核、发布及核查批准不属于客户录入权限。

## 实现

继续使用 UserRole、RolePermission、TeamMember 及现有租户上下文和 RLS。新增资源权限登记在原权限表中，数据库迁移为 `f151115b002`。既有应用角色按明确名单获得原有业务读取权限；具备原配置权限的角色获得对应维护权限。新建角色不会自动获得这些授权。

`GET /api/me/permissions` 返回当前账号的有效授权。侧边栏、工作台入口、页面路由和审核按钮读取该结果，刷新时重新从服务端获取。接口使用同一组权限代码校验，查询和写入分别授权，不通过账号名称、客户端菜单或请求参数绕过权限。

新增配置命令：

```bash
app users provision-customer-demo --username woheng-demo --email customer.demo@woheng.example.com
app users provision-customer-demo --username woheng-demo --email customer.demo@woheng.example.com --apply
```

默认只检查并输出计划。首次创建通过环境变量 `CUSTOMER_DEMO_PASSWORD` 提供密码；重复执行保留原密码，仅同步专用角色权限。若同名账号不属于该专用角色，或已有成员范围不符合两个基地，命令中止，不接管其他账号。密码不进入仓库或测试报告。

## 验证方式

- 后端：`tests/integration/accounts/test_customer_demo_access.py` 与 `tests/integration/energy/test_entry_permissions.py`。验证角色、两个基地、跨租户拒绝、能源录入及导入、只读权限不能写入、禁止通过项目编辑写入批准结论、重复执行不重置密码。
- 前端：`bunx tsc --noEmit`、Biome 检查与 `bun run test`。权限过滤测试与实际侧边栏测试覆盖十二项入口及排除模块。
- 浏览器权限：`node scripts/qa/verify-customer-access.mjs`。通过登录表单登录，检查两个基地的核心页面和配套数据页面，记录异常接口，直接访问受限页面及调用受限接口，输出 `acceptance.json` 和工作台截图。
- 实际业务：沿用 `verify-energy-data-maintenance.mjs` 的 CRUD、CSV 预检及导入、重复导入、导出和清理；沿用 `verify-ghg-maintenance.mjs` 的组织碳核算案例。所有动作使用客户账号及沃衡租户，不操作真实仓库数据。

权限脚本参数为 `E2E_BASE_URL`、`E2E_CUSTOMER_USERNAME`、`E2E_CUSTOMER_PASSWORD`、`E2E_ACCESS_OUTPUT`。业务脚本使用现有 `E2E_ADMIN_EMAIL` / `E2E_ADMIN_PASSWORD` 变量名，但本轮传入的是普通客户账号，验收明确要求 `isSuperuser=false`。

本轮运行记录和截图保存于 `.storage/customer-access-20261115/`，不提交账户秘密或运行时数据。正式发布前备份华为 `/root/warehouse` 的数据库及配置，通过 `scripts/build_push_multiarch.sh` 构建、Compose 拉取、迁移和服务更新发布。发布后再次执行两个基地的权限及录入、核算验收，并比对其他租户活动数据及既有账号安全状态。
