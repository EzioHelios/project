"""
碳数据种子脚本（对应 xtck_deploy dataapp/management/commands/seed_carbon_data.py）。

用法（在项目根目录 litestar-fullstack）:
  uv run python tools/seed_carbon_data.py              # 每类 10 条
  uv run python tools/seed_carbon_data.py --count 30   # 每类 30 条
  uv run python tools/seed_carbon_data.py --clear      # 先清空再生成
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import random
import sys
from decimal import Decimal

sys.path.insert(0, "src/py")

# 枚举与 xtck_deploy seed_carbon_data 一致
FUEL_MOBILE = ["diesel_0", "gas_92", "gas_95", "ng"]
FUEL_STATION = ["pipe_ng", "lpg", "diesel"]
FUEL_UNIT = {"pipe_ng": "m3", "lpg": "kg", "diesel": "m3", "diesel_0": "L", "gas_92": "L", "gas_95": "L", "ng": "m3"}
REFRIGERANTS = ["R22", "R410A", "R134a", "R404A", "R32"]
LEAK_TYPES = ["initial", "operation", "retire"]
WASTES = ["waste_paper", "waste_metal", "domestic", "hazardous"]
TREATMENTS = ["landfill", "incineration", "recycle"]
VEHICLES = ["heavy_truck", "light_truck"]
STATUSES = ["draft", "pending", "approved", "rejected"]
DATA_SOURCES = ["measured", "metered", "calculated", "estimated", "default"]
COLLECTION_METHODS = ["manual", "system", "auto"]
CONFIDENCE = ["high", "medium", "low"]

FACTORS = [
    {"scope": "scope1", "category": "fuel", "sub_category": "diesel_0", "unit": "L", "factor_value": Decimal("2.63"), "factor_unit": "kgCO2e/L", "year": 2024, "source": "生态环境部2023"},
    {"scope": "scope1", "category": "fuel", "sub_category": "gas_92", "unit": "L", "factor_value": Decimal("2.31"), "factor_unit": "kgCO2e/L", "year": 2024, "source": "生态环境部2023"},
    {"scope": "scope1", "category": "fuel", "sub_category": "ng", "unit": "m3", "factor_value": Decimal("2.162"), "factor_unit": "kgCO2e/m3", "year": 2024, "source": "生态环境部2023"},
    {"scope": "scope1", "category": "refrigerant", "sub_category": "R22", "unit": "kg", "factor_value": Decimal("1810"), "factor_unit": "kgCO2e/kg", "year": 2024, "source": "IPCC2021 AR6"},
    {"scope": "scope1", "category": "refrigerant", "sub_category": "R410A", "unit": "kg", "factor_value": Decimal("2088"), "factor_unit": "kgCO2e/kg", "year": 2024, "source": "IPCC2021 AR6"},
    {"scope": "scope2", "category": "electricity", "sub_category": "grid_electricity", "unit": "kWh", "factor_value": Decimal("0.581"), "factor_unit": "kgCO2e/kWh", "year": 2024, "source": "华东电网2024"},
    {"scope": "scope3", "category": "waste", "sub_category": "domestic", "unit": "t", "factor_value": Decimal("468"), "factor_unit": "kgCO2e/t", "year": 2024, "source": "IPCC2021"},
    {"scope": "scope3", "category": "transport", "sub_category": "heavy_truck", "unit": "t·km", "factor_value": Decimal("0.123"), "factor_unit": "kgCO2e/t·km", "year": 2024, "source": "交通运输部2023"},
]


def rnd_date() -> datetime.date:
    return datetime.date(2024, 1, 1) + datetime.timedelta(days=random.randint(0, 364))


def rnd_feature() -> dict:
    return {
        "data_source": random.choice(DATA_SOURCES),
        "collection_method": random.choice(COLLECTION_METHODS),
        "confidence_level": random.choice(CONFIDENCE),
        "data_year_type": "actual",
    }


async def run(count: int, clear: bool) -> None:
    from app.config import alchemy
    from app.db import models as m

    try:
        from faker import Faker
        fake = Faker("zh_CN")
    except ImportError:
        print("请安装 faker: uv add faker")
        return

    async with alchemy.get_session() as session:
        if clear:
            from sqlalchemy import delete
            for model in [
                m.Scope1MobileCombustion, m.Scope1StationaryCombustion, m.Scope1RefrigerantLeak,
                m.Scope2ElectricityBill, m.Scope3WasteDisposal, m.Scope3ThirdPartyTransport,
            ]:
                await session.execute(delete(model))
                print(f"   已清空 {model.__tablename__}")
            await session.commit()

        # 排放因子（幂等）
        for f in FACTORS:
            from sqlalchemy import select
            stmt = select(m.EmissionFactor).where(
                m.EmissionFactor.scope == f["scope"],
                m.EmissionFactor.sub_category == f["sub_category"],
                m.EmissionFactor.year == f["year"],
            )
            r = await session.execute(stmt)
            if r.scalars().first() is None:
                session.add(m.EmissionFactor(**f, is_active=True))
        await session.commit()
        print("   排放因子: 已补齐")

        # Scope1 移动源
        for _ in range(count):
            fuel = random.choice(FUEL_MOBILE)
            st = random.choice(STATUSES)
            session.add(m.Scope1MobileCombustion(
                record_date=rnd_date(),
                asset_id=f"ASSET-{random.randint(1000, 9999)}",
                asset_name=random.choice(["叉车", "货车", "轿车", "摩托车"]) + f"-{random.randint(1, 20):02d}",
                fuel_type=fuel,
                amount=Decimal(str(round(random.uniform(10, 500), 2))),
                unit=FUEL_UNIT[fuel],
                mileage_km=Decimal(str(round(random.uniform(50, 1000), 2))),
                status=st,
                reject_reason="数据有误，请重新提交" if st == "rejected" else None,
                remark=fake.sentence(nb_words=5),
                **rnd_feature(),
            ))
        await session.commit()
        print(f"   Scope1 移动源燃烧: +{count} 条")

        # Scope1 固定源
        for _ in range(count):
            fuel = random.choice(FUEL_STATION)
            s = rnd_date()
            e = s + datetime.timedelta(days=random.randint(1, 30))
            session.add(m.Scope1StationaryCombustion(
                facility_name=random.choice(["1#锅炉", "2#锅炉", "备用发电机", "食堂天然气灶"]),
                period_start=s, period_end=e, fuel_type=fuel,
                amount=Decimal(str(round(random.uniform(50, 2000), 2))),
                unit=FUEL_UNIT[fuel],
                status=random.choice(STATUSES),
                remark=fake.sentence(nb_words=4),
                **rnd_feature(),
            ))
        await session.commit()
        print(f"   Scope1 固定源燃烧: +{count} 条")

        # Scope1 制冷剂
        for _ in range(count):
            session.add(m.Scope1RefrigerantLeak(
                device_id=f"AC-{random.randint(100, 999)}",
                device_name=random.choice(["1F中央空调", "2F精密空调", "冷库主机A", "机房空调"]),
                refrigerant_type=random.choice(REFRIGERANTS),
                amount_kg=Decimal(str(round(random.uniform(0.5, 15), 2))),
                leak_type=random.choice(LEAK_TYPES),
                fill_date=rnd_date(),
                status=random.choice(STATUSES),
                remark=fake.sentence(nb_words=4),
                **rnd_feature(),
            ))
        await session.commit()
        print(f"   Scope1 制冷剂逸散: +{count} 条")

        # Scope2 电费
        for i in range(count):
            session.add(m.Scope2ElectricityBill(
                account_number=f"0391{random.randint(10000000, 99999999)}",
                billing_month=f"2024-{(i % 12) + 1:02d}",
                total_kwh=Decimal(str(round(random.uniform(5000, 80000), 2))),
                peak_kwh=Decimal(str(round(random.uniform(1000, 20000), 2))),
                flat_kwh=Decimal(str(round(random.uniform(2000, 30000), 2))),
                valley_kwh=Decimal(str(round(random.uniform(500, 10000), 2))),
                amount_cny=Decimal(str(round(random.uniform(3000, 60000), 2))),
                status=random.choice(STATUSES),
                remark=fake.sentence(nb_words=4),
                **rnd_feature(),
            ))
        await session.commit()
        print(f"   Scope2 电费账单: +{count} 条")

        # Scope3 废弃物
        for _ in range(count):
            session.add(m.Scope3WasteDisposal(
                date=rnd_date(),
                category=random.choice(WASTES),
                weight_ton=Decimal(str(round(random.uniform(0.1, 20), 3))),
                treatment_method=random.choice(TREATMENTS),
                vendor_name=fake.company() + "环保公司",
                status=random.choice(STATUSES),
                remark=fake.sentence(nb_words=4),
                **rnd_feature(),
            ))
        await session.commit()
        print(f"   Scope3 废弃物处理: +{count} 条")

        # Scope3 外购运输
        cities = ["泰兴", "南京", "上海", "杭州", "苏州", "无锡", "常州", "镇江", "扬州"]
        for _ in range(count):
            origin = random.choice(cities)
            dest = random.choice([c for c in cities if c != origin])
            session.add(m.Scope3ThirdPartyTransport(
                waybill_no=f"WB{fake.numerify('##########')}",
                origin=origin, destination=dest,
                vehicle_type=random.choice(VEHICLES),
                distance_km=Decimal(str(round(random.uniform(50, 800), 1))),
                load_ton=Decimal(str(round(random.uniform(1, 30), 2))),
                fuel_amount=Decimal(str(round(random.uniform(10, 200), 2))),
                status=random.choice(STATUSES),
                remark=fake.sentence(nb_words=4),
                **rnd_feature(),
            ))
        await session.commit()
        print(f"   Scope3 外购运输: +{count} 条")

    print(f"\n完成：每类 {count} 条\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="碳数据种子（对应 xtck_deploy seed_carbon_data）")
    parser.add_argument("--count", type=int, default=10, help="每类生成条数")
    parser.add_argument("--clear", action="store_true", help="生成前先清空相关表")
    args = parser.parse_args()
    asyncio.run(run(args.count, args.clear))


if __name__ == "__main__":
    main()
