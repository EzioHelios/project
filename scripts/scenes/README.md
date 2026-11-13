# 沃衡汽车虚构生产基地场景

本目录中的 Blender 脚本生成泰州生产基地和湖州生产基地两座**虚构**厂区。模型用于沃衡演示租户的三维园区展示；基地所在城市是演示设定，建筑形状、面积、道路和设备位置不对应任何真实地块。

## 场景内容

| 基地 | 场景重点 | 租户标识 | 资源包 |
| --- | --- | --- | --- |
| 泰州生产基地 | 整车装配、物流收发、检验发运、充电设施和供配电 | `woheng-taizhou-production-base` | `woheng-taizhou-v1` |
| 湖州生产基地 | 电池托盘、电驱、物料收发、质量办公和动力站 | `woheng-huzhou-production-base` | `woheng-huzhou-v1` |

场景通过 `src/py/app/assets/scenes/bindings.json` 按租户标识绑定。服务端读取当前授权租户的标识后返回对应资源包。两座场景均使用 `cesium-campus` 引擎，将 GLB 放置在实景卫星底图的示意选址上。选址仅用于演示，不代表沃衡实际拥有或使用该地块；详见[选址与配准记录](placement.md)。

## 重建与预览

在仓库根目录运行：

```bash
blender -b --python scripts/scenes/build_woheng_campuses.py
python3 -m http.server 18114 --bind 127.0.0.1
```

然后打开 `http://127.0.0.1:18114/scripts/scenes/preview.html`。预览页面可切换两座基地。脚本输出 `ground.glb`、`buildings.glb`、`scene.json` 和 `checksums.json` 至 `src/py/app/assets/scenes/packs/` 对应目录；可编辑 `.blend` 文件和 Blender 静态预览保存在用户的 `Documents/map-to-3d-runs/woheng-campuses-20261113/` 目录。

登录沃衡演示账号后，也可以在 `/bigscreen/model` 中通过租户切换查看两座基地。更新场景接口代码后，需重启本地应用服务，才能让运行中的 Python 进程加载新绑定逻辑。

## 数据边界

目前模型可在租户三维场景接口中加载、切换视角和漫游。建筑位置是演示布局，尚未将具体建筑网格绑定到能源设备、测点或碳数据；业务指标仍由平台原有接口提供。后续若需点击建筑查看指标，应先确认演示包中的区域、设备编码及其关系，再给对应网格增加稳定业务标识。
