# 工作区提交整理

## 结论

本轮只审查和整理，不暂存、不提交、不修改业务数据。审查前工作区共有 9 个已跟踪文件修改、29 个未跟踪文件，集中于物资作业分摊和视觉识别接入两条主线。

视觉接入已具备已验证的功能基础，但不能将整个工作区认定为可直接发布。物资分摊用例和演示包存在明确提交阻断项；只提交视觉目录也会遗漏未提交的模型、迁移和演示前置依赖。

## 提交分组与顺序

| 顺序 | 建议提交 | 文件范围 | 当前判定 |
| --- | --- | --- | --- |
| 1 | `feat(materials): add handling allocation persistence` | `carbon/models.py` 的三个物资模型、`db/models/__init__.py` 对应导出、`f7a8b9c0d1e2` 迁移 | 可单独提取为数据库基础提交；应先将迁移改成显式冻结表结构，避免依赖未来 ORM 定义 |
| 2 | `feat(materials): implement validated handling allocation` | `domain/material_allocation/`、`test_allocation_usecase.py` 和测试目录初始化文件 | 暂缓，先修复下列业务问题并补测试 |
| 3 | `feat(demo): seed scoped material handling fixtures` | `demo/ops/woheng.py` 的全部新增物资相关内容 | 暂缓，先收紧清理范围、演示标记和发布映射 |
| 4 | `feat(vision): integrate camera recognition and bigscreen` | 视觉模型/迁移、`domain/vision/`、`test_vision.py`、摄像头接口保护、前端大屏及配置、`tools/vision/` | 相关定向检查通过；按完整依赖顺序提交，不单独遗漏基础模型 |
| 5 | `docs: record vision audit and verification` | 两份视觉审查/验证文档及本清单 | 文档本身可提交；实施验证文档建议跟随对应代码提交 |

第 4 批具体共享文件：

- `src/py/app/domain/carbon/models.py`：`LargeBinary` 导入、摄像头三个私有字段、`VisionObservation`。
- `src/py/app/db/models/__init__.py`：`VisionObservation` 导入与导出。
- `src/py/app/domain/carbon/controllers.py`、`schemas.py`：私有字段不进入普通序列化。
- `src/py/app/domain/master_data/controllers/master_data.py`：普通摄像头 CRUD 不允许旁路写识别配置；带观测记录的摄像头删除保护。
- `src/py/app/domain/carbon/services/_bigscreen.py`：大屏导航。
- `src/js/web/src/components/bigscreen/layout.tsx`、`components/platform/data-admin-pages.tsx`：导航、视频台账入口和配置抽屉。
- 新增 `components/vision/`、`lib/vision.ts`、`routes/_app/bigscreen/vision.tsx`、`f8a9b0c1d2e3` 迁移。

模型和导出文件必须按改动块分批暂存。迁移链为 `f6a7b8c9d0e1 -> f7a8b9c0d1e2 -> f8a9b0c1d2e3`。不能只凭完整工作区测试通过就宣称中间提交可独立运行；实际提交时还需检查各批暂存差异和依赖闭合。

## 提交前必须修复

1. **PATCH 改写来源及状态**：`material_allocation/usecases.py:101` 对部分更新仍注入 `manual` 来源、新来源键、`confirmed`、`measured`，并在 121、136 行重算时长和重置单位。仅改备注也会破坏视觉来源和既有业务值。需要部分更新回归测试。
2. **重复发布 PCF**：每次计算创建新 run/result，`usecases.py:369` 使用新 result ID 作为来源键，重复计算同一批数据会新增仍参与核算的清单。需要稳定业务键及重复计算/发布测试。
3. **期间分摊边界**：`usecases.py:194` 取相交作业的完整动因，320 行将相交小时能耗全量汇总；局部小时查询会纳入整小时能耗。必须明确并校验支持的期间，不能默默将部分期间按完整期间计算。还需检查能源事实单位。
4. **Demo 清理范围过大**：`woheng.py:3394` 删除租户全部分摊 run/result 和全部 `material_allocation` 来源 PCF 清单，不限本包拥有的记录。应只更新/清理当前包登记的数据，验证重复安装保留用户创建结果。
5. **Demo 业务语义**：功率与负载率推导的样例能耗、预制物资作业被标为 `measured`；八类物资作业统一写入电池托盘研究，缺少明确物资与研究归属。应标记模拟来源并明确发布映射，不能以有结果行代替业务正确。
6. **权限与输入边界补测**：物资控制器未声明业务动作 guard，原始 dict 进入用例且没有字段白名单；需明确普通成员/只读成员/管理员可执行动作，并补 HTTP 权限、跨租户写入和受保护字段测试。本轮未实测普通账号越权，不将代码缺口直接表述为已复现漏洞。

## 本轮检查

- 全部改动 Python 范围 Ruff 通过。
- 前端 6 个相关文件 Biome 通过；`bunx tsc --noEmit` 通过。
- `src/py/tests/integration/material_allocation`：8 passed。
- `tools/vision/test_tracking.py`：3 passed。
- `git diff --check` 通过。
- 未运行全仓库测试；现有 1 项分摊测试只覆盖一次计算/发布的正常案例，不覆盖上述边界。
- 上一轮已有 RTSP 实链路和内置浏览器记录；本轮没有重复浏览器演示或操作线上数据。

## 不纳入提交

`.storage/vision/` 中的截图、识别 outbox、进程文件和日志均被忽略。`__pycache__`、自动生成的 `routeTree.gen.ts` 也被忽略。视频、模型权重在源仓库，不复制入本仓库。本轮候选新增代码扫描未发现明文账号密码；运行凭据通过环境变量提供。

建议先解决第 2、3 批的阻断项，再依次提交。无需重做视觉大屏或全量重拍截图，也不要为清空工作区直接提交未完成的计算用例。
