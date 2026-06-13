# Admin Visual Refactor Goal Prompt

Use this prompt when starting a Codex goal for the backend admin visual refactor.

```text
目标：一次性批量推进 litestar-fullstack 后台管理平台视觉统一，优先全局控制，避免逐页小修。

约束：
- 不碰大屏页面，除非明确发现共享样式破坏大屏。
- 不重写业务逻辑、接口、表格列、表单字段和权限判断。
- 每批至少覆盖一个共享模板或 8-20 个同类调用点；不要一页一页改。
- 不要每改几页就 build。节奏是：扫描 → 批量改 → biome check --write 本批文件 → 继续下一批；只在阶段收口时运行 bun run build。
- 先运行：cd src/js/web && bun run audit:admin-visual。

优先级：
1. 共享组件入口优先：AdminTableToolbar、ContextBar、AdminPageScaffold、AdminPanel、ChartPanel、MetricStrip、AdminDataTable。
2. 筛选区统一：所有 AdminTableToolbar 用 fields API；首屏最多 4 个主筛选项，其余由“显示全部”展开；查询/新增/重置/导出放 actions。
3. 页面顺序统一：PageHeader → tabs → filters → metrics → primary content → secondary content。Tabs/筛选/指标卡片不得乱序。
4. 图表统一：不要页面内写 hex 调色、grid、axis、tooltip、legend 样式；迁移到 admin-chart-theme 或共享 chart builder。
5. 去 AI 味：删除可见说明性副标题、口径说明卡、使用说明卡、英文模板文案、彩色装饰卡、裸 Card 表格壳。
6. CRUD/ledger 统一：列表页面用 AdminPanel + AdminTableToolbar + AdminDataTable + AdminTableStateRow；详情抽屉显示业务标签，不直接暴露 raw JSON。

每批完成标准：
- bun run biome check --write <本批文件>
- git diff --check
- 更新 docs/design/migration-candidate-list.md
- 阶段收口再运行 bun run build；chunk warning 不阻塞。
```
