# 沃衡汽车统一演示数据包

`app.demo` 是能碳平台的跨领域演示编排层。客户向演示统一使用 `woheng-showcase`，品牌口径为“沃衡汽车能碳管理平台”。

## 推荐入口

```bash
app demo package list
app demo package plan woheng-showcase --namespace woheng --profile full --action install
app demo package install woheng-showcase --namespace woheng --profile full --apply
app demo package validate woheng-showcase --namespace woheng --profile full
```

截图入口：

```bash
cd src/js/web
bun run qa:evidence:woheng-showcase:isolated
```

## 租户结构

`woheng-showcase` 会生成两个演示子租户：

- `woheng-taizhou-production-base`：沃衡汽车泰州生产基地，重点展示整车装配、厂内物流、MQTT 电表接入、分区分项用能监测、点位配置和告警闭环。
- `woheng-huzhou-production-base`：沃衡汽车湖州生产基地，重点展示零部件制造、经营活动台账、非电活动数据导入、组织碳核算、报告导出和减排绩效。

两个租户共用同一套组织碳、能源、监测告警、报告、公开碳价模拟和后续产品碳足迹联动口径。企业主体复用 `litestar-microservice` 演示包中的“沃衡汽车有限公司 / Voryntis Mobility”资料，生产基地、采集协议、MQTT 点位、经营活动和排放结构做差异化。

## 数据归属

演示包写入的租户和安装摘要会登记到 `demo_manifest`。`cleanup` 只清理 manifest 中登记为本包拥有的沃衡汽车演示租户，避免误删历史客户数据。

```bash
app demo package cleanup woheng-showcase --namespace woheng --profile full
app demo package cleanup woheng-showcase --namespace woheng --profile full --apply
```

## 兼容入口

历史客户向演示入口仅保留用于追溯旧材料。新增客户演示、截图和材料生成应使用 `woheng-showcase`。
