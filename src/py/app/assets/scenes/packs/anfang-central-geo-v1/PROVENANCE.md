# 安方中心库外观资产

2026-09-10 根据用户确认的江苏安方电力科技有限公司南厂区创建；地址吴陵南路888号，高德POI https://amap.com/place/B0HBMRN0U1 。

模型制作按外部安装的 map-to-3d 技能执行 Matt Shumer 公开的 Blender → Three.js 流程，原文 https://somethingbig.ai/3d-worlds 。提示词与制作过程保留在仓库外的 `~/Documents/map-to-3d-runs/anfang-south-wuling888-20260910/`。

GLB 为本次 Blender 生成工程的导出，不是第三方成品模型。几何轮廓和空间位置参考 Esri World Imagery 影像；当前 ground.glb 已移除外围卫星影像平面，底图由 Cesium 在线影像层提供；reference.jpg 为同处参考影像。影像服务 https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer ，zoom18，瓦片起点 x218369/y106088，1536×1536 像素范围，获取于2026-09-10，影像拍摄日期未核实。第三方影像不声明为自有或开放许可素材；当前通过授权端点供本地仓库应用展示，外部分发需核对图源许可。

原点 WGS84 [119.88676071167,32.42289881130]，Blender X东Y北Z上，glTF Y上。高度、门窗、植被形状为估计；室内、实测高度、功能区身份与设备业务绑定未确认，不得作为测绘/BIM或业务设备台账。

注册名称依用户确认显示为安方中心库。本包只通过 bindings.json 分配给对应 team UUID。新场景包可以使用自己的参考坐标、镜头、漫游入口、碰撞轮廓及灯光位置；租户信息不写入通用技能。

## 地理配准版本

本包通过外部 map-to-3d 技能的通用配准工具生成定位参数与资产副本。复用原版 anfang-central-v1 的建筑与园区几何，删除平面影像背景。Cesium 加载 Esri 在线地理瓦片，并用 WGS84 ENU 矩阵定位。运行证据保留在仓库外 /Users/eziohelios/Documents/map-to-3d-runs/anfang-south-wuling888-20260910/registered-v1。

高程0.20米为椭球面实验值；建筑高度沿用估计。坐标转换残差只反映同源影像的变换一致性，不是独立测绘精度。旧版本资产包已移至仓库外备份，不随当前应用分发。
