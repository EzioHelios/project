"""Build two fictional Woheng factory campuses for the tenant scene viewer.

The geometry is an illustrative demo composition, not a survey of real parcels.
Run with: blender -b --python scripts/scenes/build_woheng_campuses.py
"""

# ruff: noqa: ANN001, ANN201, INP001, RUF001, T201

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
PACKS = ROOT / "src/py/app/assets/scenes/packs"
WORK = Path.home() / "Documents/map-to-3d-runs/woheng-campuses-20261113"
PLACEMENTS = {
    "taizhou": {
        "revision": "2026-11-13.2",
        "heading_degrees": 0,
        "orbit_position": [240, 185, 240],
        "origin": [119.92300272, 32.36004393],
        "address": "江苏省泰州市泰州港经济开发区 · 演示选址",
        "source": "泰州港经济开发区许庄片区，Esri World Imagery 2026-11-13 检视的开敞地",
    },
    "huzhou": {
        "revision": "2026-11-13.3",
        "heading_degrees": -25,
        "orbit_position": [319, 185, 116],
        "origin": [119.98303056, 30.91592199],
        "address": "浙江省湖州市南太湖新区 · 演示选址",
        "source": "南太湖新区杨家埠片区，Esri World Imagery 2026-11-13 检视的开敞地",
    },
}
IMAGERY_URL = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"


def material(name: str, color: tuple[float, float, float], *, metal: float = 0.0):
    result = bpy.data.materials.new(name)
    result.diffuse_color = (*color, 1)
    result.use_nodes = True
    shader = result.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Metallic"].default_value = metal
    shader.inputs["Roughness"].default_value = 0.72 if metal else 0.9
    return result


def group(name: str):
    result = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(result)
    return result


def move(obj, target):
    for old in tuple(obj.users_collection):
        old.objects.unlink(obj)
    target.objects.link(obj)
    return obj


def box(name: str, x0: float, y0: float, x1: float, y1: float, z0: float, z1: float, mat, target):
    bpy.ops.mesh.primitive_cube_add(size=1, location=((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = (x1 - x0, y1 - y0, z1 - z0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    move(obj, target)
    return obj


def cylinder(name: str, x: float, y: float, z: float, radius: float, depth: float, mat, target, vertices=12):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=(x, y, z))
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    return move(obj, target)


def beam(name: str, start, end, radius: float, mat, target):
    a, b = Vector(start), Vector(end)
    direction = b - a
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=radius, depth=direction.length, location=(a + b) / 2)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    obj.data.materials.append(mat)
    return move(obj, target)


def roof(name: str, x0: float, y0: float, x1: float, y1: float, eave: float, rise: float, mat, target):
    mid = (y0 + y1) / 2
    verts = [
        (x0, y0, eave),
        (x0, mid, eave + rise),
        (x0, y1, eave),
        (x1, y0, eave),
        (x1, mid, eave + rise),
        (x1, y1, eave),
    ]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], [(0, 3, 4, 1), (1, 4, 5, 2), (0, 1, 2), (3, 5, 4), (0, 2, 5)])
    mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    target.objects.link(obj)
    obj.modifiers.new("roof thickness", "SOLIDIFY").thickness = 0.22
    return obj


def hall(name: str, bounds, height: float, palette, buildings, *, doors=6, solar=False, skylights=False):
    x0, y0, x1, y1 = bounds
    wall, metal, trim, glass, dark, panel = (palette[key] for key in ("wall", "roof", "trim", "glass", "dark", "panel"))
    box(f"{name}_wall", x0, y0, x1, y1, 0.08, height, wall, buildings)
    roof(f"{name}_roof", x0 - 0.7, y0 - 0.7, x1 + 0.7, y1 + 0.7, height, 1.4, metal, buildings)
    for x in range(math.ceil(x0 + 3), math.floor(x1 - 1), 5):
        beam(
            f"{name}_roof_rib_{x}",
            (x, y0 - 0.7, height + 0.07),
            (x, (y0 + y1) / 2, height + 1.5),
            0.035,
            trim,
            buildings,
        )
        beam(
            f"{name}_roof_rib_back_{x}",
            (x, (y0 + y1) / 2, height + 1.5),
            (x, y1 + 0.7, height + 0.07),
            0.035,
            trim,
            buildings,
        )
    beam(
        f"{name}_ridge",
        (x0 - 0.7, (y0 + y1) / 2, height + 1.52),
        (x1 + 0.7, (y0 + y1) / 2, height + 1.52),
        0.065,
        trim,
        buildings,
    )
    for index in range(doors):
        x = x0 + 4 + (index + 0.5) * (x1 - x0 - 8) / doors
        box(
            f"{name}_dock_{index}",
            x - 1.7,
            y0 - 0.28,
            x + 1.7,
            y0 - 0.06,
            0.28,
            min(height - 1.3, 4.4),
            dark,
            buildings,
        )
        box(f"{name}_dock_lintel_{index}", x - 1.95, y0 - 0.48, x + 1.95, y0 - 0.04, 4.35, 4.58, trim, buildings)
        box(f"{name}_dock_ramp_{index}", x - 2.0, y0 - 3.5, x + 2.0, y0 - 0.5, 0.10, 0.28, panel, buildings)
    for index, x in enumerate(range(math.ceil(x0 + 3), math.floor(x1 - 2), 8)):
        box(
            f"{name}_clerestory_{index}",
            x,
            y1 + 0.04,
            x + 3.6,
            y1 + 0.12,
            height - 2.6,
            height - 1.35,
            glass,
            buildings,
        )
    if skylights:
        for x in range(math.ceil(x0 + 10), math.floor(x1 - 8), 17):
            box(
                f"{name}_skylight_{x}",
                x,
                (y0 + y1) / 2 - 1.1,
                x + 6,
                (y0 + y1) / 2 + 1.1,
                height + 1.52,
                height + 1.62,
                glass,
                buildings,
            )
    if solar:
        solar_mat = palette["solar"]
        mid = (y0 + y1) / 2
        for x in range(math.ceil(x0 + 7), math.floor(x1 - 6), 6):
            for y in range(math.ceil(mid + 3), math.floor(y1 - 3), 3):
                z = height + 1.4 * (y1 - y) / (y1 - mid) + 0.20
                tile = box(f"{name}_solar_{x}_{y}", x, y, x + 4.7, y + 2.2, z, z + 0.10, solar_mat, buildings)
                tile.rotation_euler.x = -math.atan2(1.4, (y1 - y0) / 2)


def road(name, bounds, palette, ground):
    x0, y0, x1, y1 = bounds
    box(name, x0, y0, x1, y1, 0.02, 0.13, palette["road"], ground)


def stripes(name, x0, x1, y, palette, ground, *, step=14):
    for x in range(math.ceil(x0), math.floor(x1), step):
        box(f"{name}_{x}", x, y, min(x + 5, x1), y + 0.18, 0.14, 0.18, palette["stripe"], ground)


def tree(name, x, y, palette, ground):
    cylinder(f"{name}_trunk", x, y, 1.45, 0.25, 2.9, palette["bark"], ground, 8)
    for level, radius, z in ((0, 1.5, 3.1), (1, 1.2, 4.3)):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=radius, location=(x, y, z))
        obj = bpy.context.object
        obj.name = f"{name}_foliage_{level}"
        obj.data.materials.append(palette["tree"])
        move(obj, ground)


def lamp(name, x, y, palette, ground):
    cylinder(f"{name}_post", x, y, 3.4, 0.10, 6.7, palette["dark"], ground, 8)
    beam(f"{name}_arm", (x, y, 6.65), (x + 1.1, y, 6.65), 0.075, palette["dark"], ground)
    box(f"{name}_light", x + 0.8, y - 0.25, x + 1.35, y + 0.25, 6.52, 6.67, palette["stripe"], ground)


def vehicle(name, x, y, palette, ground, *, truck=False):
    length = 8 if truck else 4.4
    width = 2.4 if truck else 1.8
    box(f"{name}_body", x, y, x + length, y + width, 0.28, 1.6 if truck else 1.3, palette["vehicle"], ground)
    box(
        f"{name}_glass",
        x + (5.8 if truck else 1.5),
        y + 0.12,
        x + length - 0.3,
        y + width - 0.12,
        1.6 if truck else 1.3,
        2.75 if truck else 2.05,
        palette["glass"],
        ground,
    )
    for wx in (x + 0.9, x + length - 0.9):
        for wy in (y - 0.1, y + width + 0.1):
            cylinder(
                f"{name}_wheel_{wx}_{wy}", wx, wy, 0.40, 0.42, 0.23, palette["dark"], ground, 12
            ).rotation_euler.x = math.pi / 2


def utility(name, bounds, palette, buildings):
    x0, y0, x1, y1 = bounds
    box(f"{name}_slab", x0, y0, x1, y1, 0.14, 0.24, palette["panel"], buildings)
    for index, x in enumerate(range(math.ceil(x0 + 4), math.floor(x1 - 2), 7)):
        box(f"{name}_cabinet_{index}", x, y0 + 3, x + 3.5, y0 + 6, 0.24, 3.0, palette["dark"], buildings)
        box(f"{name}_cabinet_face_{index}", x + 0.5, y0 + 2.85, x + 3, y0 + 3.0, 1.2, 2.5, palette["trim"], buildings)
    box(f"{name}_control", x0 + 3, y1 - 10, x0 + 14, y1 - 3, 0.2, 4.0, palette["wall"], buildings)
    box(f"{name}_control_roof", x0 + 2.5, y1 - 10.5, x0 + 14.5, y1 - 2.5, 4.0, 4.25, palette["roof"], buildings)


def perimeter(palette, ground):
    for x0, y0, x1, y1 in (
        (-114, -84, 114, -83.5),
        (-114, 83.5, 114, 84),
        (-114, -84, -113.5, 84),
        (113.5, -84, 114, 84),
    ):
        box("campus_perimeter", x0, y0, x1, y1, 0.13, 1.55, palette["dark"], ground)
    for x in range(-111, 113, 15):
        for y in (-83.7, 83.7):
            cylinder(f"fence_post_{x}_{y}", x, y, 1.10, 0.11, 2.2, palette["trim"], ground, 8)


def base(palette, ground):
    box("campus_base", -116, -86, 116, 86, -0.18, 0.0, palette["concrete"], ground)
    for bounds in ((-108, -75, 108, -64), (-108, 61, 108, 72), (-104, -62, -93, 61), (93, -62, 104, 61)):
        road("campus_ring_road", bounds, palette, ground)
    for bounds in ((-111, 73, 111, 81), (-111, -81, 111, -76)):
        x0, y0, x1, y1 = bounds
        box("landscape_verge", x0, y0, x1, y1, 0.01, 0.12, palette["grass"], ground)
    perimeter(palette, ground)
    for x in range(-97, 103, 18):
        for y in (-78, 78):
            tree(f"perimeter_tree_{x}_{y}", x, y, palette, ground)
    for x, y in ((-100, -65), (-50, -65), (10, -65), (65, -65), (-100, 64), (-40, 64), (30, 64), (90, 64)):
        lamp(f"yard_lamp_{x}_{y}", x, y, palette, ground)
    stripes("south_road_mark", -85, 85, -69, palette, ground)
    box("main_gatehouse", -108, -83, -95, -73, 0.12, 3.4, palette["wall"], ground)
    box("gatehouse_glass", -107, -83.2, -97, -83.0, 1.1, 2.6, palette["glass"], ground)
    box("gatehouse_roof", -109, -84, -94, -72, 3.4, 3.75, palette["roof"], ground)


def office(name, bounds, palette, buildings, *, floors=2):
    x0, y0, x1, y1 = bounds
    height = 4.0 * floors
    box(f"{name}_wall", x0, y0, x1, y1, 0.08, height, palette["wall"], buildings)
    box(f"{name}_roof", x0 - 0.4, y0 - 0.4, x1 + 0.4, y1 + 0.4, height, height + 0.36, palette["roof"], buildings)
    for floor in range(floors):
        for x in range(math.ceil(x0 + 3), math.floor(x1 - 2), 5):
            box(
                f"{name}_window_{floor}_{x}",
                x,
                y0 - 0.11,
                x + 2.5,
                y0 + 0.02,
                1.25 + floor * 4,
                3.1 + floor * 4,
                palette["glass"],
                buildings,
            )
    box(f"{name}_entrance", x0 + 2, y0 - 0.25, x0 + 5, y0, 0.1, 3.2, palette["dark"], buildings)


def add_parked_vehicles(palette, ground, *, x0=35, y0=42, count=8):
    box("parking_pavement", x0 - 4, y0 - 4, x0 + count * 7.5 + 2, y0 + 14, 0.07, 0.13, palette["panel"], ground)
    for index in range(count + 1):
        x = x0 + index * 7.5
        box(f"parking_line_{index}", x, y0, x + 0.16, y0 + 11, 0.14, 0.18, palette["stripe"], ground)
    if count > 1:
        vehicle("parked_car_one", x0 + 1, y0 + 3, palette, ground)
        vehicle("parked_car_two", x0 + 16, y0 + 3, palette, ground)


def taizhou(palette, ground, buildings):
    base(palette, ground)
    road("taizhou_cross_road", (-88, -35, 91, -25), palette, ground)
    road("taizhou_west_link", (-80, -60, -69, 60), palette, ground)
    stripes("assembly_lane", -65, 85, -29.5, palette, ground)
    hall("vehicle_assembly", (-65, -16, 45, 27), 12.5, palette, buildings, doors=8, solar=True, skylights=True)
    hall("inbound_logistics", (-105, -10, -72, 49), 8.7, palette, buildings, doors=4, solar=False)
    hall("inspection_and_dispatch", (51, -12, 91, 26), 8.8, palette, buildings, doors=4, skylights=True)
    office("north_office", (-37, 39, 29, 57), palette, buildings, floors=3)
    utility("power_station", (48, -57, 87, -39), palette, buildings)
    box("charging_pavement", 39, 34, 100, 59, 0.06, 0.13, palette["panel"], ground)
    for index in range(6):
        x = 45 + index * 8.5
        box(f"charger_{index}", x, 52, x + 0.9, 53, 0.14, 2.0, palette["trim"], buildings)
        box(f"charger_screen_{index}", x + 0.15, 51.92, x + 0.75, 52.0, 1.15, 1.65, palette["glass"], buildings)
        box(f"charging_stall_{index}", x - 2.2, 37, x - 2.0, 49, 0.14, 0.18, palette["stripe"], ground)
    vehicle("assembly_output_car", 62, -33, palette, ground)
    vehicle("logistics_truck", -102, -49, palette, ground, truck=True)
    vehicle("yard_truck", 2, -53, palette, ground, truck=True)
    return [
        ("vehicle-assembly", (-65, -16, 45, 27), 14),
        ("inbound-logistics", (-105, -10, -72, 49), 10),
        ("inspection-dispatch", (51, -12, 91, 26), 10),
        ("office", (-37, 39, 29, 57), 13),
        ("power-station", (48, -57, 87, -39), 4.5),
    ]


def huzhou(palette, ground, buildings):
    base(palette, ground)
    road("huzhou_center_road", (-104, -38, 103, -28), palette, ground)
    road("huzhou_process_lane", (-5, -24, 6, 51), palette, ground)
    stripes("huzhou_road_mark", -88, 87, -33, palette, ground)
    hall("battery_tray_line", (-91, -19, -9, 34), 10.5, palette, buildings, doors=6, solar=True)
    hall("electric_drive_line", (9, -19, 88, 34), 11.2, palette, buildings, doors=6, solar=True, skylights=True)
    hall("material_receiving", (-91, -60, -45, -43), 7.5, palette, buildings, doors=3)
    office("quality_and_office", (-31, 45, 42, 60), palette, buildings, floors=2)
    utility("compressed_air_and_power", (43, -59, 88, -42), palette, buildings)
    add_parked_vehicles(palette, ground, x0=38, y0=43, count=7)
    for index in range(5):
        x = -80 + index * 9
        box(f"tray_outbound_stack_{index}", x, -57, x + 5.8, -51, 0.13, 1.2, palette["panel"], ground)
    vehicle("tray_truck", -97, -70, palette, ground, truck=True)
    vehicle("drive_unit_truck", 27, -69, palette, ground, truck=True)
    return [
        ("battery-tray-line", (-91, -19, -9, 34), 12),
        ("electric-drive-line", (9, -19, 88, 34), 13),
        ("material-receiving", (-91, -60, -45, -43), 9),
        ("quality-office", (-31, 45, 42, 60), 9),
        ("power-station", (43, -59, 88, -42), 4.5),
    ]


def camera(name, location, target, scale):
    data = bpy.data.cameras.new(name)
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()
    data.type = "ORTHO"
    data.ortho_scale = scale
    return obj


def export(target, path):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in target.objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = next(iter(target.objects))
    bpy.ops.export_scene.gltf(
        filepath=str(path), export_format="GLB", use_selection=True, export_apply=True, export_yup=True
    )
    bpy.ops.object.select_all(action="DESELECT")


def build(site: str):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    buildings = group("buildings")
    ground = group("ground")
    palette = {
        "concrete": material("site concrete", (0.50, 0.55, 0.55)),
        "road": material("dark roadway", (0.22, 0.30, 0.32)),
        "panel": material("light paved yards", (0.58, 0.64, 0.63)),
        "grass": material("planting", (0.21, 0.40, 0.32)),
        "tree": material("tree foliage", (0.16, 0.37, 0.28)),
        "bark": material("tree trunks", (0.35, 0.32, 0.27)),
        "stripe": material("road and parking markings", (0.91, 0.89, 0.73)),
        "wall": material("factory insulated wall", (0.69, 0.75, 0.75)),
        "roof": material("standing seam roof", (0.37, 0.49, 0.53), metal=0.35),
        "trim": material("blue steel trim", (0.14, 0.34, 0.39), metal=0.35),
        "glass": material("factory glazing", (0.13, 0.31, 0.36), metal=0.18),
        "dark": material("doors and metal framing", (0.20, 0.28, 0.30), metal=0.3),
        "solar": material("solar panel blue glass", (0.07, 0.19, 0.30), metal=0.25),
        "vehicle": material("fleet vehicle white", (0.79, 0.83, 0.81), metal=0.16),
    }
    building_specs = taizhou(palette, ground, buildings) if site == "taizhou" else huzhou(palette, ground, buildings)
    pack = PACKS / f"woheng-{site}-v1"
    pack.mkdir(parents=True, exist_ok=True)
    work = WORK / site
    work.mkdir(parents=True, exist_ok=True)
    export(ground, pack / "ground.glb")
    export(buildings, pack / "buildings.glb")

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.world = bpy.data.worlds.new(f"{site} daylight")
    scene.world.color = (0.64, 0.71, 0.74)
    scene.view_settings.view_transform = "AgX"
    sunlight = bpy.data.lights.new("sun", type="SUN")
    sun = bpy.data.objects.new("sun", sunlight)
    scene.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(26), math.radians(-32), math.radians(-20))
    sunlight.energy = 2.3
    scene.camera = camera("isometric preview", (210, -205, 205), (0, 0, 0), 310)
    bpy.ops.wm.save_as_mainfile(filepath=str(work / f"woheng-{site}.blend"))
    scene.render.filepath = str(work / "preview.png")
    bpy.ops.render.render(write_still=True)

    title = "沃衡汽车泰州生产基地" if site == "taizhou" else "沃衡汽车湖州生产基地"
    placement = PLACEMENTS[site]
    scene_json = {
        "sceneId": f"woheng-{site}",
        "revision": placement["revision"],
        "engine": "cesium-campus",
        "title": title,
        "address": placement["address"],
        "attribution": "沃衡汽车虚构厂区演示模型；建筑布局与尺寸为演示设定；底图由 Esri World Imagery 提供",
        "assets": ["ground.glb", "buildings.glb"],
        "world": {
            "origin": [0, 0],
            "originPixel": [0, 0],
            "metresPerPixel": 1,
            "buildings": [
                {"id": name, "polygon": [[x0, -y0], [x1, -y0], [x1, -y1], [x0, -y1]], "height": height}
                for name, (x0, y0, x1, y1), height in building_specs
            ],
            "water": [],
            "walkBounds": [-111, 111, -81, 81],
            "orbitPosition": placement["orbit_position"],
            "orbitTarget": [0, 0, 0],
            "entries": [
                {"id": "main-gate", "label": "主入口", "pixel": [-96, 76], "yaw": 0},
                {"id": "production-road", "label": "生产区通道", "pixel": [0, 34], "yaw": 0},
            ],
            "lights": [[-100, 65], [-50, 65], [10, 65], [65, 65], [-100, -64], [30, -64]],
        },
        "georegistration": {
            "version": 2,
            "crs": "EPSG:4326",
            "origin": placement["origin"],
            "headingDegrees": placement["heading_degrees"],
            "scale": [1, 1, 1],
            "ellipsoidHeight": 0.2,
            "heightStatus": "estimated",
            "upAxis": "Y",
            "forwardAxis": "X",
            "terrain": "ellipsoid",
            "imagery": {"url": IMAGERY_URL, "credit": "Esri World Imagery", "maximumLevel": 18},
            "placement": {
                "kind": "fictional-demonstration",
                "basis": placement["source"],
                "imageryDate": "unknown",
                "parcelOwnership": "unverified",
            },
        },
    }
    (pack / "scene.json").write_text(json.dumps(scene_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    checksums = {
        name: hashlib.sha256((pack / name).read_bytes()).hexdigest()
        for name in ("ground.glb", "buildings.glb", "scene.json")
    }
    (pack / "checksums.json").write_text(json.dumps(checksums, indent=2) + "\n", encoding="utf-8")
    print(f"Built {site}: {pack}, {work}")


for selected in ("taizhou", "huzhou"):
    build(selected)
