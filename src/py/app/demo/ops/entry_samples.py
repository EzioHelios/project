"""Fill the backend's actual category template with the canonical demo cases."""

from __future__ import annotations

import base64
import csv
from io import BytesIO
from typing import Any

from openpyxl import load_workbook

from app.demo.ops.enterprise_entry import CITY_NAMES, SAMPLE_ROOT, load_cases
from app.demo.showcase.builder import AREAS, EQUIPMENT
from app.domain.ghg_inventory.infrastructure.workbook import build_template_bytes, decode_and_preview

CATEGORY_NAMES = {"1.4": "制冷剂填报", "3.3": "员工通勤填报", "3.1": "入厂运输填报"}


def sample_context(city: str, category: str) -> dict[str, Any]:
    """Create portable context using stable business codes and catalog display names."""
    cases = [case for case in load_cases(city) if case.category == category]
    areas = [{"id": index, "code": spec.code, "name": spec.name} for index, spec in enumerate(AREAS, 1)]
    area_ids = {row["code"]: row["id"] for row in areas}
    equipment = [
        {"id": index, "code": spec.code, "name": spec.name, "area_id": area_ids[spec.area_code]}
        for index, spec in enumerate(EQUIPMENT, 1)
    ]
    return {
        "inventory_code": f"WOHENG-{city}-ENTRY-202610",
        "organization_code": f"WOHENG-{city}-ORG",
        "facility_code": cases[0].area_code,
        "iso_category_code": category,
        "reporting_profile_code": "CORPORATE_ISO14064_GHGP",
        "method_code": "F02_EF" if category == "1.4" else "F09_TRANSPORT_ACTIVITY",
        "period_start": "2026-10-01",
        "period_end": "2026-10-31",
        "boundary_method": "operational_control",
        "organization_name": f"沃衡汽车{CITY_NAMES[city]}生产基地",
        "areas": areas,
        "equipment": equipment,
        "area_codes": list(area_ids),
        "equipment_codes": [spec.code for spec in EQUIPMENT],
    }


def build_sample(city: str, category: str) -> bytes:
    """Populate only the backend-defined data sheet; preserve its metadata and rules."""
    context = sample_context(city, category)
    workbook = load_workbook(BytesIO(build_template_bytes(context)))
    sheet = workbook["03_活动数据"]
    columns = {str(cell.value): cell.column for cell in sheet[2]}
    area_names = {spec.code: spec.name for spec in AREAS}
    device_names = {spec.code: spec.name for spec in EQUIPMENT}
    cases = [case for case in load_cases(city) if case.category == category]
    for row_number, case in enumerate(cases, 3):
        row = {
            **case.payload,
            "record_code": case.record_code,
            "source_name": case.name,
            "activity_name": case.name,
            "area_name": area_names[case.area_code],
            "equipment_name": device_names.get(case.equipment_code),
            "period_start": case.start.isoformat(),
            "period_end": case.end.isoformat(),
            "activity_amount": float(case.amount),
            "activity_unit": case.unit,
            "remarks": case.payload.get("maintenance_record") or "2026年10月经营台账合计",
        }
        if category == "3.3":
            row["transport_direction"] = "员工通勤"
        elif category == "3.1":
            row["transport_direction"] = "上游运输"
        for code, value in row.items():
            if code in columns:
                sheet.cell(row=row_number, column=columns[code], value=value)
    stream = BytesIO()
    workbook.save(stream)
    data = stream.getvalue()
    preview, _digest = decode_and_preview(base64.b64encode(data).decode(), context)
    errors = [issue.message for issue in preview.issues if issue.severity == "error"]
    if errors:
        msg = f"{city}/{category}: {errors}"
        raise ValueError(msg)
    if len(preview.activities) != len(cases):
        msg = "导出样例活动行数与原始案例不一致"
        raise ValueError(msg)
    return data


def export_energy_sample(city: str) -> str:
    """Use exactly the Chinese columns offered by the energy page template."""
    area_names = {spec.code: spec.name for spec in AREAS}
    equipment_names = {spec.code: spec.name for spec in EQUIPMENT}
    energy_names = {"purchased_electricity": "外购电力", "natural_gas": "天然气", "diesel": "柴油"}
    path = SAMPLE_ROOT / f"{CITY_NAMES[city]}基地_能源导入.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["区域", "设备", "能源种类", "月份", "能源用量", "单位", "费用", "备注"])
        for case in load_cases(city):
            if case.energy_type:
                writer.writerow(
                    [
                        area_names[case.area_code],
                        equipment_names[case.equipment_code],
                        energy_names[case.energy_type],
                        case.start.strftime("%Y-%m"),
                        str(case.amount),
                        case.unit,
                        str(case.cost),
                        case.payload["business_record"].replace("；计量点GAS-METER-01", ""),  # noqa: RUF001 - Chinese source text
                    ]
                )
    return str(path)


def export_samples() -> list[str]:
    """Write import-ready files without a database connection."""
    paths = []
    for city, name in CITY_NAMES.items():
        paths.append(export_energy_sample(city))
        for category, category_name in CATEGORY_NAMES.items():
            path = SAMPLE_ROOT / f"{name}基地_{category_name}.xlsx"
            path.write_bytes(build_sample(city, category))
            paths.append(str(path))
    return paths


if __name__ == "__main__":
    for output_path in export_samples():
        print(output_path)  # noqa: T201 - explicit sample export command
