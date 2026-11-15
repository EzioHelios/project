# 仓储企业数据录入与组织碳核算发布记录

日期：2026-11-15。结论：系统、沃衡两基地演示数据及文档站已完成发布和验收。
最终镜像为 `2d01cf14`，数据库迁移head为 `f151115a001`；两基地录入、查询及组织碳核算通过，最终重复安装比较无差异。

## 1. 最终版本与备份

| 项目 | 最终记录 |
| --- | --- |
| 部署位置 | Huawei，`/root/warehouse`；`https://warehouse.nexlca.com/` |
| 应用提交 | `2d01cf14f2f703dab9ee3eb21ad01b279498959e` |
| 应用镜像 | `registry.xzzandzyc.store:5000/project/warehouse-carbon:2d01cf14` |
| 镜像digest | `sha256:882089ae30b6b3e9b2e7ca3ec3f9293fd744aa1262bb49cd2a4cf228608f93fb` |
| 数据库head | `f151115a001`；发布前为 `e061106a001` |
| 验证脚本提交 | `9ec5594`，已推送；无运行时变动，无需纳入应用镜像 |
| docs提交及版本 | `455ecfd2`；`20261115-154723-455ecfd` |
| 上一docs版本 | `20261115-120443-1686a89` |
| 数据库备份 | `/root/warehouse/backups/release-20261115-enterprise-entry/warehouse-all-tenants.dump` |
| 备份大小及SHA-256 | `319421663`字节；`0d6cdcda05f211b1435077b4237f80fc3b4fc536cd43375ca347decc98ad4240` |
| 发布前镜像 | app为 `317be047`，三个worker为 `72f85a3`；原配置及镜像记录已保留 |

Compose的app、migrator及三个worker统一使用APP_IMAGE；app与三个常驻worker镜像一致，健康检查正常。migrator独立成功退出后才更新业务服务，broker/cache未随本次发布重建。
北京时间17:00检查到 `pull_yunji_data` 和 `run_microgrid_forecast_cycle` 活跃任务，等待至17:00:21活跃数为0后才更新普通worker；其余worker也分别检查队列后更新，见 `deploy-r3.log`。
仓储React前端随应用镜像发布；docs独立发布。备份已做目录及解析检查，未将其表述为完成隔离恢复演练。

## 2. 提交分组

| 分组 | 提交 | 内容 |
| --- | --- | --- |
| 能源业务 | `1b4151fd` | 企业能源录入、导入及区间事实查询 |
| GHG与因子 | `6b24cebe` | 分类录入导入、幂等生成、因子选择及更正后重新核算 |
| 业务前端 | `5d8b87d6` | 能源与组织碳录入、查询及结果反馈 |
| 大屏结果 | `640365f6` | 展示对应沃衡租户的核算结果 |
| 手册与取证 | `17fd7271`、`cbd7507f` | 规范手册入口、截图脚本及普通账号验证 |
| 演示案例 | `ecd099f0` | 中文企业案例及安全重复安装 |
| 安装检查 | `64b36d5e` | 修复RLS事务上下文导致的检查误读 |
| 数据库迁移 | `9745365` | 三表ID序列修复，revision `f151115a001` |
| 旧help入口 | `d9aaaac` | 生产模式静态路由指向规范文档站 |
| 物料幂等性 | `2d01cf1` | 统一Decimal存储scale后的输入指纹比较，保留历史快照 |
| 验证脚本 | `9ec5594` | 修正租户可见性及边界内对象选择，不改变运行时代码 |
| 文档站 | `455ecfd2` | 手册、中文样表及截图发布 |

## 3. 两基地业务验收与范围

线上验证使用普通非superuser账号，校验当前租户与产品自然发送的租户请求头；临时记录按本次ID清理并回查。

| 验收项 | 泰州 | 湖州 |
| --- | --- | --- |
| 能源CRUD、导入、导出 | passed，19项检查 | passed，含新增、更正、预检、零值及重复冲突 |
| 能耗查询 | passed，5项检查；10月天然气18600 m³ | passed；10月天然气22400 m³ |
| GHG分类维护与导入 | passed，import阶段56项检查 | 本次线上未重复执行该阶段 |
| 活动生成与重复生成 | passed，generation阶段7项检查 | 本次线上未重复执行该阶段 |
| 页面核算 | passed，calculation阶段13项检查，含R32因子采用 | passed，calculation-only，沿用已选因子 |
| 新核算run | `CALC-2C3E84DD1CF545FA` | `CALC-B09C18FB03D54896` |
| 报告期／边界ID | 13／13 | 14／14 |
| 活动数与结果 | 8条，327124.8 kgCO₂e | 8条，256348.76 kgCO₂e |
| R32结果 | 2.4 kg，GWP675，1620 kgCO₂e | 1.8 kg，GWP675，1215 kgCO₂e |
| 临时记录回查 | 能源、临时活动及排放源残留均0 | 能源IDs 3313953、3313956、3313957残留均0 |
| 脚本截图 | 46张 | 16张 |

最终镜像上线后，内置浏览器实际刷新泰州并切换至湖州，两租户均显示上述新run、8条结果；页面分别显示327.12 t和256.35 t，2026-10年月、报告组织及边界准确。
最终图片为 `taizhou-carbon-final-online.jpg`、`huzhou-carbon-final-online.jpg`；此前查询回查确认企业案例4条能源事实，核算图表完整。
湖州核算阶段唯一业务写入为POST核算运行，正式run保留；没有重新生成活动、重新选因子或更改正式活动。
能源更正后同一活动更新、旧run数值和快照不变、新run反映更正，已有本地隔离测试；本次线上不声称覆盖了这组更正前后对照测试。

文档站线上30页、163张图片、8份下载全部通过，201项SHA-256一致；旧help入口33项通过，规范跳转及目标页面一致。

## 4. 演示包重复安装与数据保护

最终镜像上两次full安装及其validate均退出0。`demo-final-comparison-after2.json` 为passed，业务分组、字段、保护项及登录元数据差异均为空。
首轮after1仅为泰州活动1078补齐 `source_payload.energy_type_code=purchased_electricity` 并更新 `updated_at`；数量、来源、因子及核算结果不变。原始字段差异保留，不能把首轮写成完全零变化。
第二次以after1为基线重复安装，所有已比较字段均无变化；该结论限于本次演示包、数据及比较范围，不泛化为任意模块和输入的幂等保证。

| 保护对象 | 最终结果 |
| --- | --- |
| 两基地企业案例 | 各4条能源事实、8条活动，报告期和已发布边界保持不变 |
| 历史核算 | 11个run、968条result、976条参数分配记录未改写 |
| 物料核算 | 8个物料run均保持revision2，历史快照不变；每基地8条作业、4个run、8条结果 |
| 客户GHG数据 | 受保护客户租户的活动内容、数量及核算运行比较无变化 |
| 既有账号和权限 | 密码及安全字段、既有成员关系和权限保护比较无变化 |

历史和物料精确比较见 `demo-final-semantic-after1.json` 及after2报告。保留after1原始差异，避免用语义相同掩盖实际字段更新。
运行小时仍为not_provided，证据文件存在warning；本次不宣称完整能效对标或证据齐备。

## 5. 发布中发现的问题及处理

| 问题 | 处理及证据 |
| --- | --- |
| RLS检查误读为零 | `64b36d5e` 修复；首轮在业务写入前停止，快照相同，不记为客户数据缺失 |
| 旧迁移遗漏三表ID序列 | `9745365` 修复；139个Sequence模型扫描仅发现3张空表缺失，5项真实PG迁移测试通过 |
| Decimal存储scale导致物料指纹变化 | `2d01cf1` 修复比较规则，历史快照保留；最终after2无差异 |
| 公共平台标题不含“沃衡” | 验证脚本改为严格账号、租户及自然请求头校验；首轮无业务写入，失败报告保留 |
| 泰州脚本选择边界外归集区域 | 后端正确拒绝422；脚本改选设备所属且在已发布边界内的区域，临时记录已清理 |
| 旧help返回SPA外壳 | 增加生产静态路由；33个旧入口线上验证通过 |

后端GHG/因子回归114项、更正重算专项16项通过，两者有交集，不重复相加。RLS修复11项隔离集成及60项单元测试通过。
物料修复共17项PG测试通过：首次16项通过、1项环境错误，该项单独重跑通过；保留两份日志，不写成首次17项全绿。
物料模块Pyright基线61项错误、修复后61项，零新增；不代表全仓类型检查通过或零错误。
登录前 `/api/me` 的401为预期会话探测；实际验收中认证后的业务请求无401、403或5xx。
登录页和业务页仍有相同hash的CSP内联脚本阻止执行错误。它是后续独立修复项，本轮不放宽CSP、不扩展UI重构，也不宣称控制台零错误。

## 6. 回退与证据目录

回退前核对数据库与旧镜像兼容性，按备份分别恢复app和worker版本；发布前两者版本不同，不能统一猜测回退tag。
数据库迁移不随镜像回退自动撤销，不能直接运行旧migrator代替回退。整库恢复会覆盖数据，须另行确认恢复范围；docs可回退至 `20261115-120443-1686a89`。
操作顺序见[线上发布Runbook](../usage/production-release-runbook.md)。证据根目录为 `.storage/release-20261115/`：

| 证据类别 | 文件或目录 |
| --- | --- |
| 备份与基线 | `backup-result.json`、`before.json`、`demo-before-baseline.sha256` |
| 最终版本及部署 | `release-r3.json`、`build-r3.log`、`deploy-r3.log` |
| 最终安装及校验 | `demo-final-install-{1,2}.log`、`demo-final-validate-{1,2}.log` |
| 重复安装与保护 | `demo-final-comparison-after{1,2}.json`、`demo-final-semantic-after1.json`、`demo-final-protection-*.json` |
| 两基地业务验收 | `online/taizhou/final-summary.md`、`online/huzhou/acceptance.json`及各阶段JSON、截图、清理回查 |
| 最终实际浏览器回查 | `taizhou-carbon-final-online.jpg`、`huzhou-carbon-final-online.jpg` |
| 文档及旧help | `docs-http-acceptance.json`、`help-online-acceptance.json` |
| 首次失败证据 | `demo-failed-install-comparison.json`、`demo-final-comparison-r3.json`、`online/huzhou/crud-firstpass/`、`online/taizhou/attempts/` |
| 物料测试及类型基线 | `material-repeat-fixed-tests.log`、`material-repeat-permission-recheck.log`、`material-repeat-pyright-comparison-final.json` |

`.storage`为忽略目录，证据及本次取证脚本不随代码或镜像分发；上述路径用于发布归档追溯，不是通用发布流程的依赖。
