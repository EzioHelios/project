# 大屏三维场景与租户资产

2026-09-11：安方中心库、祥泰仓库均已配置为带 WGS84 地理定位的 Blender GLB + Cesium 资产包，加载 Esri 在线卫星瓦片。旧 Three.js 包和旧 Cesium 包已移至仓库外备份，应用只分发当前绑定的两处资产。业务接口、React/Vite、Litestar 和 PostgreSQL 不变。

## 运行架构

`当前 team UUID → 授权场景 API → 该租户资产包 → 按需加载 Three.js 或 Cesium → 通用大屏`

- `TenantCampusScene` 使用当前租户 UUID 请求 manifest，按 UUID 重建组件。
- Three.js 入口移植自已确认的建模预览，保留日夜、总览/北向俯视、卫星对照、漫游入口、WASD/QE 和步行碰撞。
- Cesium 原有地理引擎及 GeoJSON 解析保留，通过授权资源 URL 加载。平台不需要整体更换引擎。
- Three.js 动态导入，仅在该引擎的场景中加载；模型材质、相机和几何按原预览路线迁移，不通过 iframe 嵌套外部预览。
- 相机、入口、像素到米制换算、建筑碰撞轮廓、水域边界、灯光位置放在资产包 manifest，不在组件里写安方坐标。
- 当前 Three.js 资产生成约定使用 `ground.glb` 地面和其他建筑 GLB；运行时相应设置薄面和细部阴影，资产均为嵌入纹理的 GLB。

## 资产位置和绑定

资产从前端公开目录迁入私有后端目录：

```
src/py/app/assets/scenes/
  bindings.json
  packs/
    anfang-central-geo-v1/
      scene.json
      buildings.glb
      ground.glb
      reference.jpg
      PROVENANCE.md
      registration-report.json
      checksums.json
    xiangtai-warehouse-geo-v1/
      （同上结构）
```

绑定按数据库已确认的 UUID：

| 租户 | UUID | 资产包 |
| --- | --- | --- |
| 安方中心库 | 00000000-0000-7000-8000-000000000002 | anfang-central-geo-v1 |
| 祥泰仓库 | 00000000-0000-7000-8000-000000000001 | xiangtai-warehouse-geo-v1 |

其他租户未配置时显示未配置状态。旧的 slug/id → 全局厂区 fallback 不再用于大屏布局，避免其他租户看见安方或祥泰。旧公开 `maps/taizhou-warehouse` 与 `maps/tenants/default-tenant/scene.json` 已迁移移除，更早的 `maps/bigscreen/scene.json` 与 `warehouses.geojson` 也已移除，历史副本在仓库外备份，不再公开分发。通用模板和不含厂区数据的底图样式继续保留。

部署可以设置 `SCENE_ASSET_ROOT` 指向服务器挂载的私有目录，结构与上例一致。此目录不得再挂为 Web 静态目录。新增租户时准备独立版本包，在 `bindings.json` 将实际 team UUID 绑定包名；绑定更新和资产文件应作为一次原子部署完成。当前为部署配置管理，没有新增后台上传、审批、版本历史管理 UI，也没有新增数据库表或迁移。

## 授权与生命周期

- `GET /api/teams/{team_id}/scene`：返回该租户的场景清单。
- `GET /api/teams/{team_id}/scene/assets/{asset_name}`：每次读取都重新校验当前用户及 team 访问权限。
- 复用现有 `requires_authenticated_user` 和 `resolve_tenant_context`：成员只能访问自己的 team；超级管理员可以显式选择 team。
- URL 中的 team UUID 是授权对象；请求头不能把别家资源伪装成自己的租户。复制 URL 不绕过授权。
- 仅返回 manifest 允许的文件，禁止任意目录/符号链接逃逸。响应 `Cache-Control: private, no-store`，并包含 Cookie/Authorization/X-Team-Id 的 Vary。
- manifest 给资源带 revision 参数；旧 revision 请求失败，避免同名文件更新时混用新版本。
- 客户端固定请求所属 team，检查服务端返回的 teamId 和资源 URL。切换租户即卸载旧画布、取消请求、撤销图片 Blob URL、释放几何/纹理/事件/动画和 WebGL 上下文。
- 异步创建的旧 Cesium 引擎也会在卸载后被销毁，不会继续挂载。

这是真正的后端读取授权，目录名仅组织资源。当前使用文件代理，不引入对象存储、签名服务或新的部署系统。未来容量增长时可替换存储层为私有对象存储，沿用租户授权接口。

## 精度和业务绑定

安方包来源见包内 `PROVENANCE.md`。主建筑和布局依据卫星影像；高度、立面与植被是估计。原始 Blender 工程、生成代码、原提示词和对照记录保留在 `~/Documents/map-to-3d-runs/anfang-south-wuling888-20260910/`，没有把提示词写入业务仓库或把安方参数写入通用 skill。

“东北侧厂房”等方向标签不代表已经确认的业务设施身份。后续把真实能耗、告警和设备映射到模型时，必须由台账明确 `assetKey` 和业务对象，不能根据几何外观自动冒认设备。

## 验证

- 后端 HTTP 测试：自身读取、跨租户复制 URL、伪造 team header、匿名、停用账户、未配置、文件白名单、超级管理员显式访问、符号链接逃逸、过期 revision。
- 前端测试：切换租户销毁与请求取消、旧请求晚到、无跨租户 fallback、Cesium 延迟创建后的释放。
- 类型检查、局部 Biome/Ruff、前端完整构建。
- 已在登录后的正式大屏确认场景加载、租户切换、滚轮缩放与拖动响应；独立建模预览的画面和漫游已在前一轮检查。

## 祥泰仓库真实地块接入（2026-09-10）

祥泰模型位于官河路与泰事达路交叉口南侧，西侧沿河。当前包 `xiangtai-warehouse-geo-v1` 的来源、估计范围和哈希见包内 PROVENANCE.md 与 checksums.json。与安方保持独立坐标、GLB和manifest；旧包仅保留仓库外备份。

斜向建筑之间的步行通道使用真实多边形轮廓加0.7米行走间距判断，替换原先轴对齐包围框的过大禁行范围；该间距是交互参数，不是消防或工程标准。

## Cesium 地理资产接入（2026-09-11）

通过仓库外通用 map-to-3d 技能的 `export_registered_ground.py` 和 `prepare_registration.py` 分别生成两处园区的 ground.glb 副本、地理参数及数学核对报告，再装配新的私有资产包。提示词、技能模板、工具源代码和客户运行资料未混放。

新引擎标识为 `cesium-campus`，与历史 `cesium` GeoJSON 引擎明确区分。`georegistration` 保存 WGS84 原点、椭球高、ENU 尺度、GLB 轴向及影像服务；前端验证支持的坐标系和轴向。运行时先通过当前租户的鉴权端点读取 GLB，再用 Blob URL 交给 Cesium，保持模型实际尺度。园区 ground 只去掉平面影像背景，底图由 Cesium 全球 XYZ 影像层绘制。

总览、俯视、日夜、卫星对照、各入口漫游、WASD/QE 与方向按钮复用原 React 控件。地图漫游使用相同的局部米制坐标与建筑、水域碰撞约束，通过 ENU 转换设置地理相机。租户切换中止下载、销毁 Viewer、解除监听并撤销 GLB Blob URL；迟到模型被销毁。`园区模型` 已加入默认大屏导航。

当前地形为 WGS84 椭球面，整体0.20米是实验高程。影像平面对齐已验证；独立控制点、实测地面高程、影像屋顶投影误差仍未验证。日夜为显示模式，不用于太阳时刻或照度分析。

### 本次验证范围

- 技能元数据校验、原始提示词哈希校验；独立合成样本检验原点、尺度、GLB、坐标体系及输入拒绝，发现的通用性问题已修正。
- 前端定向测试14项通过：坐标轴/真实资产角点变换、manifest校验、租户切换生命周期与碰撞；后端场景授权HTTP测试11项通过。后端定向执行使用 `--no-cov`，没有将该子集当成全项目覆盖率验收。
- TypeScript检查、局部Biome/Ruff、完整前端构建通过。构建仍有既有大体积Cesium包警告。
- 浏览器：技能生成的预览正常；本地交互验收页直接导入正式 TenantCampusScene 和 Cesium runtime，验证两处资产、在线影像、入口、按钮移动、日夜和租户切换，未记录错误。该隔离验收页使用本地fixture，不代替生产鉴权测试。
- 后续已在有效登录会话下检查正式18101大屏：场景加载、租户切换和相机缩放/拖动生效。总览页隐藏工具栏时仍接收鼠标输入，点击场景后 Esc 恢复总览；两侧业务面板继续接收自身交互。

## 提交前清理（2026-09-11）

- 移除无调用方的 `scene-resolver.ts` 及其旧回退测试；`BigscreenSceneCanvas` 不再默认请求已删除的公共祥泰资源，场景入口由调用方显式提供。
- 仅保留 bindings.json 引用的两个地理资产包。三个未绑定旧包（`anfang-central-v1`、`xiangtai-warehouse-v1`、`xiangtai-legacy-v2`，约13.3 MiB）先复制、逐文件核对 SHA-256 后移出仓库。
- 本地备份位置：`~/Documents/map-to-3d-runs/retired-scene-packs-20260911/`，内含20个原始文件及校验清单。回滚需先还原相应资产包，再恢复对应租户绑定；不能只修改包名。
- Three.js GLB 和 Cesium GeoJSON 的通用加载能力仍有受支持的 manifest 分支与测试，继续保留。通用技能和原始提示词位于仓库外，不包含在本项目提交中。

### 本次提交前复核

2026-09-11 清理后执行：前端 `bun run test -- tests/bigscreen` 共27项通过；后端场景授权与大屏数据定向测试共16项通过（`--no-cov`，不代表全仓库覆盖率）。TypeScript、局部 Biome/Ruff、资产绑定与全部 SHA-256 核验通过。

同期业务修正包括：租户切换后请求和缓存按 team UUID 隔离并取消旧请求；缺失电量/碳排以 null 和空态展示，实测0值仍显示0；账期标签与累计年份依据实际有数据的月份；移除主场景上重复的业务悬浮标签。
