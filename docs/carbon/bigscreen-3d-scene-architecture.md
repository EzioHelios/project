# 大屏三维场景与多租户资产架构

## 目标

大屏场景使用同一套 Cesium 渲染运行时，但允许每个租户拥有独立的空间数据、模型、镜头和视觉参数。现有 GeoJSON 是空间骨架，不因引入 glTF 或 3D Tiles 而废弃。

架构分为四层：

1. 平台工业模板：灯光、雾化、后处理、默认材质和性能参数。
2. 租户场景清单：园区中心、镜头、GeoJSON、模型实例和图层开关。
3. 平台资产库：许可证明确、可复用且本地托管的环境资产。
4. 业务绑定层：通过稳定的 `assetKey` / `semanticType` 将运行状态映射到场景对象。

## 目录约定

```text
public/
  maps/
    templates/
      industrial-v2.json
    tenants/
      <team-slug>/
        scene.json
        site.geojson
        buildings.geojson
        zones.geojson
        models/
    taizhou-warehouse/
      scene.json
      *.geojson
  models/
    <provider-or-pack>/
      catalog.json
      LICENSE.txt
      *.glb
```

租户解析顺序：

1. `maps/tenants/<team-slug>/scene.json`
2. `maps/tenants/<team-id>/scene.json`
3. `VITE_BIGSCREEN_DEFAULT_SCENE_MANIFEST` 指定的回退场景
4. 未配置环境变量时使用当前泰州场景

只有 404 会进入下一个候选。租户清单一旦存在但内容错误，运行时必须报错，不得静默显示其他租户的场景。

## 场景继承

租户清单通过 `extends` 继承平台模板：

```json
{
  "extends": "../../templates/industrial-v2.json",
  "sceneId": "tenant-campus",
  "revision": "1",
  "center": [120.0, 30.0],
  "warehouseLayer": { "dataUrl": "./warehouses.geojson" },
  "siteLayer": { "dataUrl": "./site.geojson" },
  "buildingLayer": { "dataUrl": "./buildings.geojson" },
  "modelLayer": {
    "assets": []
  }
}
```

相对 URL 始终以声明该资源的 manifest 为基准解析。因此平台模板中的模型仍属于平台资产命名空间，租户覆盖中的模型属于租户命名空间。

## 资产精度策略

- GeoJSON：园区边界、道路、建筑轮廓和业务分区，保持真实坐标。
- 程序化建筑：普通厂房和仓库体量，统一材质与构造语言。
- glTF / GLB：能源站、储能、变压器、屋顶设备和少量关键对象。
- 3D Tiles：倾斜摄影、BIM、点云或规模较大的外部模型。
- 通用环境资产：只用于树木、车辆、围栏和不承载业务结论的细节。

不得把通用下载模型直接绑定为真实业务设备。只有在租户数据能确认对象身份、位置和类型时，才能设置业务 `assetKey`。

## 模型交付约束

- Web 运行格式优先 `.glb`，禁止生产运行时加载 FBX/OBJ。
- 单个关键模型建议小于 2 MB，普通道具建议小于 300 KB。
- 重复对象使用实例化或 3D Tiles，不重复下载相同网格。
- 纹理以 1K/2K 为主；大面积重复材质应使用可平铺纹理。
- 建议使用 KTX2/Basis 纹理压缩和 Meshopt/Draco 几何压缩。
- 模型必须使用真实米制比例，原点和朝向保持一致。
- 每项外部资产必须保留来源、许可证和允许再分发的证据。

## 安全边界

当前 `public/` 目录适用于公开或可随前端分发的资产，不构成租户授权机制。涉及厂区保密模型时，应改为：

1. 后端根据当前 `X-Team-Id` 返回场景引用；
2. 对象存储使用短期签名 URL 或受保护代理；
3. manifest 只返回当前租户允许访问的资源；
4. 缓存键必须包含租户和场景版本。

前端的 slug/id 命名空间用于资源组织和回退，不得替代后端权限校验。

## 当前实现

- 平台模板：`src/js/web/public/maps/templates/industrial-v2.json`
- 当前租户绑定：`src/js/web/public/maps/tenants/default-tenant/scene.json`
- 租户解析：`src/js/web/src/lib/bigscreen/map/scene-resolver.ts`
- manifest 继承和资源解析：`src/js/web/src/lib/bigscreen/map/scene.ts`
- Cesium 模型与 3D Tiles 加载：`src/js/web/src/lib/bigscreen/map/cesium-engine.ts`
