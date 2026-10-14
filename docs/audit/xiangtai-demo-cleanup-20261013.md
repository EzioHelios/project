# 祥泰演示活动清理与演示租户限制

日期：2026-10-13。授权范围：移除已核验的67条祥泰演示活动，确保演示数据只能写入 demo ops 的沃衡租户。

## 线上数据处理：已完成

环境：Huawei `/root/warehouse`，`warehouse-app-1`。

- 将线上数据逐字段与[来源核验](xiangtai-activity-provenance-20261013.md)使用的快照比较，确认仍为原67条。
- 检查关联核算结果、参数分配、归集、证据链接和报告，均无引用。
- 数据库外键补查发现6条购电汇总引用演示电费活动。核实全部仅由对应单条演示活动生成，表计量为0，没有混入实测表计来源。
- 单事务删除67条活动；6条派生购电汇总设为 `is_current=false`、`status=superseded`，保留历史数值并记录退役原因及原活动编号。未把演示汇总重新包装成实测数据。
- 重复执行返回 `already_absent`、`deleted=0`。
- 复核祥泰活动数为0；安方组织碳相关数据与前次修复后的快照完全一致；祥泰其余被核查的组织碳表与删除前一致。
- 未修改电表读数、设备、区域、通勤、出入库台账，也未删除组织、报告期或边界样例。本轮不等于已清理祥泰全部历史演示对象。
- 对外 `/health` 返回 HTTP 200；未重启服务。

维护脚本：[remove_xiangtai_demo_activities.py](../../tools/maintenance/remove_xiangtai_demo_activities.py)。默认只读，写入需显式 `--apply`，输入快照必须满足固定SHA256，目标租户、原始记录、引用状况变化即拒绝。

备份位于服务器：

`/root/warehouse/backups/ghg-correction-20261013/xiangtai-deleted-67-20261013.json`

含完整67条活动及6条汇总原值；SHA256：`2123c3834de09d5cb6d5217286e30e7b6aaf8947295bd693a38697c24a88f742`。

同目录 `before.json` 为操作前已保存的完整核验快照，另保留本日此前创建的全库备份。此次操作没有执行任何数据库迁移或演示初始化。

本地证据目录：`.storage/warehouse-ghg-provenance-20261013/`，包含删除备份、`after-removal.json`、`retired-summaries.json`。

## 代码限制：已实现，尚未发布线上

统一业务写入校验位于 [demo_tenancy.py](../../src/py/app/lib/demo_tenancy.py)：

1. 只接受 `woheng-taizhou-production-base` 和 `woheng-huzhou-production-base`。
2. 必须显式指定有效、启用的租户，拒绝 tenant bypass，不回退默认租户。
3. 显式保护安方、祥泰固定ID，即使误改slug也不能作为演示租户。
4. 组织碳展示生成器、能源样例、能效样例、旧仓储盘查初始化、物资作业样例、微电网样例均在业务读写前校验。
5. demo ops 固定 `woheng-showcase` 包与 `woheng` namespace；cleanup 同时核验登记对象ID、租户ID和slug，防止错误manifest删除客户。
6. 删除 `app demo apply`、`install-showcase`、`verify-showcase`，删除旧 `ApplyDemoPackage` 编排、独立showcase建租户函数及 `tools/seed_carbon_data.py`。不转发兼容旧命令。

公开政策参考库、账号和权限等平台配置与租户业务事实分开，不把必要的公共配置初始化描述为客户业务数据生成。

本轮未构建、发布新镜像，不能称这些代码限制已经在线上生效。线上完成的是精准数据清理；防护代码需后续发布。当前线上旧演示命令仍不应使用。

## 验证

```sh
uv run pytest src/py/tests/unit/demo \
  src/py/tests/integration/material_allocation/test_allocation_usecase.py::test_demo_repeat_install_preserves_objects_and_user_changes \
  src/py/tests/integration/microgrid/test_demo_cycle.py -q -n 0 --no-cov
```

结果：34项通过。覆盖允许两个沃衡租户、拒绝客户租户、拒绝缺失/停用租户与bypass、保护客户固定ID、六个生成入口调用前拦截、namespace拒绝、plan只读及物资作业/微电网正向集成流程。

`app demo --help` 已只显示 `package`。涉及文件 Ruff lint 通过，`git diff --check` 通过。新增维护脚本与租户限制相关文件格式检查通过；`commands.py` 另有两处既有格式问题位于此次删除范围之外，未进行无关格式改动。不声称完成全仓回归或整个demo包全量重装。
