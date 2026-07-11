
import asyncio
import os
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine

# Fix for Windows asyncio loop policy
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def verify():
    old_db_url = os.environ["OLD_DB_URL"]
    new_db_url = os.environ["NEW_DB_URL"]

    old_engine = create_engine(old_db_url)
    new_engine = create_async_engine(new_db_url)

    # Core tables to check
    mapping = {
        "dataapp_enterpriseinfo": "dataapp_enterpriseinfo",
        "dataapp_monitorsector": "dataapp_monitorsector",
        "dataapp_monitorequipment": "dataapp_monitorequipment",
        "dataapp_ammeterindexvalue": "dataapp_ammeterindexvalue",
        "dataapp_videomonitor": "dataapp_videomonitor",
        "dataapp_auditlog": "dataapp_carbonauditlog",
        "dataapp_emissionfactor": "dataapp_emissionfactor",
        "dataapp_scope1mobilecombustion": "dataapp_scope1mobilecombustion",
        "dataapp_scope1stationarycombustion": "dataapp_scope1stationarycombustion",
        "dataapp_scope1refrigerantleak": "dataapp_scope1refrigerantleak",
        "dataapp_scope2electricitybill": "dataapp_scope2electricitybill",
        "dataapp_scope3wastedisposal": "dataapp_scope3wastedisposal",
        "dataapp_scope3thirdpartytransport": "dataapp_scope3thirdpartytransport",
    }

    print(f"{'Table':<35} | {'Source':<10} | {'Target':<10} | {'Status':<10}")
    print("-" * 75)

    with old_engine.connect() as old_conn:
        async with new_engine.connect() as new_conn:
            for src_name, dst_name in mapping.items():
                try:
                    # Count source
                    src_count = old_conn.execute(text(f"SELECT count(*) FROM {src_name}")).scalar()

                    # Count target
                    dst_count_res = await new_conn.execute(text(f"SELECT count(*) FROM {dst_name}"))
                    dst_count = dst_count_res.scalar()

                    status = "OK" if src_count == dst_count else "MISMATCH"
                    print(f"{src_name:<35} | {src_count:<10} | {dst_count:<10} | {status}")
                except Exception as e:
                    print(f"{src_name:<35} | Error: {str(e)[:50]}...")

    # Check ALL 38 Views
    print("\nVerifying All 38 Views...")
    views_to_check = [
        "alarm_event_view", "crkje_day_sum_view", "crkje_month_sum_view", "crkje_week_sum_view", "crkje_year_sum_view",
        "hw_cdz_ammeter_day_hour_view", "hw_cdz_area_day_hour_sum_view", "hw_cdz_area_day_sum_view",
        "hw_cdz_area_month_sum_view", "hw_cdz_area_week_sum_view", "hw_cdz_area_year_sum_view",
        "hw_gf_ammeter_day_hour_view", "hw_gf_area_day_hour_sum_view", "hw_gf_area_day_sum_view",
        "hw_gf_area_month_sum_view", "hw_gf_area_week_sum_view", "hw_gf_area_year_sum_view",
        "hw_gf_day_hour_sum_view", "hw_gf_day_sum_view", "hw_gf_month_sum_view", "hw_gf_week_sum_view",
        "hw_gf_year_sum_view", "vedio_alarm_event_view", "yj_ammeter_day_hour_sum_view", "yj_ammeter_day_sum_view",
        "yj_ammeter_month_sum_view", "yj_ammeter_week_sum_view", "yj_ammeter_year_sum_view", "yj_area_day_hour_sum_view",
        "yj_area_day_sum_view", "yj_area_month_sum_view", "yj_area_week_sum_view", "yj_area_year_sum_view",
        "yj_day_hour_sum_view", "yj_day_sum_view", "yj_month_sum_view", "yj_week_sum_view", "yj_year_sum_view"
    ]

    async with new_engine.connect() as new_conn:
        for view in views_to_check:
            try:
                res = await new_conn.execute(text(f"SELECT count(*) FROM {view}"))
                count = res.scalar()
                print(f"{view:<35} | Rows: {count}")
            except Exception as e:
                print(f"{view:<35} | FAILED: {str(e).splitlines()[0][:60]}...")

    await new_engine.dispose()

if __name__ == "__main__":
    asyncio.run(verify())
