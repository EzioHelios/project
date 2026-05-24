from __future__ import annotations

from dataclasses import dataclass

from app.domain.carbon import bigscreen_schemas as bs
from app.domain.carbon import huayi_bigscreen_schemas as hs


@dataclass(slots=True)
class HuayiBigscreenMetaService:
    def build(self) -> bs.BigscreenMetaPayload:
        return bs.BigscreenMetaPayload(
            title="城市零碳园区智慧神经中枢",
            short_name="HY",
            description="面向园区管理方展示能源、减碳、资源化、设备状态与公众参与的综合态势。",
            default_path="/bigscreen/huayi",
            show_weather=False,
            city="上海",
            nav_items=[
                bs.BigscreenNavItem(label="园区总览", path="/bigscreen/huayi"),
            ],
        )


@dataclass(slots=True)
class HuayiBigscreenOverviewService:
    def build(self) -> hs.HuayiBigscreenOverviewPayload:
        return hs.HuayiBigscreenOverviewPayload(
            park_name="华谊园区",
            photovoltaic_metrics=[
                hs.HuayiBigscreenKeyValue(label="当日发电时间", value=6, unit="h", tone="amber"),
                hs.HuayiBigscreenKeyValue(label="累计发电时间", value=10394, unit="h"),
                hs.HuayiBigscreenKeyValue(label="当日发电量", value=371.2, unit="kWh", tone="emerald"),
                hs.HuayiBigscreenKeyValue(label="累计发电量", value=113439, unit="kWh"),
                hs.HuayiBigscreenKeyValue(label="当日节省电费", value=388.55, unit="元", tone="amber"),
                hs.HuayiBigscreenKeyValue(label="累计节省电费", value=142306.9, unit="元"),
            ],
            charger_metrics=[
                hs.HuayiBigscreenKeyValue(label="使用", value=11, unit="台", tone="emerald"),
                hs.HuayiBigscreenKeyValue(label="闲置", value=5, unit="台"),
                hs.HuayiBigscreenKeyValue(label="充电收益", value=827.93, unit="元", tone="amber"),
            ],
            load_groups=[
                hs.HuayiBigscreenMetricGroup(
                    id="green-self-use",
                    title="绿电自用",
                    metrics=[
                        hs.HuayiBigscreenKeyValue(label="当日", value=1345, unit="度", tone="emerald"),
                        hs.HuayiBigscreenKeyValue(label="累计", value=149351, unit="度"),
                    ],
                ),
                hs.HuayiBigscreenMetricGroup(
                    id="green-grid",
                    title="绿电上网",
                    metrics=[
                        hs.HuayiBigscreenKeyValue(label="当日", value=447, unit="度", tone="cyan"),
                        hs.HuayiBigscreenKeyValue(label="累计", value=66989, unit="度"),
                    ],
                ),
                hs.HuayiBigscreenMetricGroup(
                    id="thermal-load",
                    title="火电使用",
                    metrics=[
                        hs.HuayiBigscreenKeyValue(label="当日", value=2687, unit="度", tone="amber"),
                        hs.HuayiBigscreenKeyValue(label="累计", value=236270, unit="度"),
                    ],
                ),
            ],
            carbon_stats=[
                hs.HuayiBigscreenKeyValue(label="全区碳排放监测量", value=11425, unit="kg CO2", tone="cyan"),
                hs.HuayiBigscreenKeyValue(label="全区碳排放减排量", value=3871, unit="kg CO2", tone="amber"),
                hs.HuayiBigscreenKeyValue(label="全区碳排放中和量", value=647, unit="kg CO2"),
                hs.HuayiBigscreenKeyValue(label="新能源减排量", value=3260, unit="kg CO2", tone="emerald"),
                hs.HuayiBigscreenKeyValue(label="环保减排量", value=1085, unit="kg CO2", tone="amber"),
            ],
            resource_cards=[
                hs.HuayiBigscreenMetricGroup(
                    id="reduction",
                    title="废弃物减量化",
                    metrics=[
                        hs.HuayiBigscreenKeyValue(label="当日减量", value=266.1, unit="kg", tone="cyan"),
                        hs.HuayiBigscreenKeyValue(label="累计减量", value=27315, unit="kg"),
                        hs.HuayiBigscreenKeyValue(label="当日收益", value=232.1, unit="元", tone="amber"),
                        hs.HuayiBigscreenKeyValue(label="累计收益", value=11863.96, unit="元"),
                    ],
                ),
                hs.HuayiBigscreenMetricGroup(
                    id="reuse",
                    title="废弃物利用化",
                    metrics=[
                        hs.HuayiBigscreenKeyValue(label="当日利用", value=217.5, unit="kg", tone="emerald"),
                        hs.HuayiBigscreenKeyValue(label="累计利用", value=21201, unit="kg"),
                        hs.HuayiBigscreenKeyValue(label="当日收益", value=63.5, unit="元", tone="amber"),
                        hs.HuayiBigscreenKeyValue(label="累计收益", value=8800.04, unit="元"),
                    ],
                ),
            ],
            device_status=[
                hs.HuayiBigscreenKeyValue(label="总设备", value=24, unit="台"),
                hs.HuayiBigscreenKeyValue(label="在线", value=19, unit="台", tone="emerald"),
                hs.HuayiBigscreenKeyValue(label="离线", value=5, unit="台", tone="amber"),
                hs.HuayiBigscreenKeyValue(label="告警", value=0, unit="台", tone="cyan"),
            ],
            benefit_items=[
                hs.HuayiBigscreenKeyValue(label="碳普惠碳汇", value=11439, unit="kg", tone="cyan"),
                hs.HuayiBigscreenKeyValue(label="绿证开发", value=127, unit="个", tone="emerald"),
            ],
            lifestyle_sections=[
                hs.HuayiBigscreenListSection(
                    id="green-traffic",
                    title="绿色交通",
                    items=[
                        hs.HuayiBigscreenKeyValue(label="人员参与", value=1352, unit="人"),
                        hs.HuayiBigscreenKeyValue(label="充电桩绿电", value=13993, unit="度"),
                        hs.HuayiBigscreenKeyValue(label="累计碳积分", value=103778, unit="分", tone="amber"),
                        hs.HuayiBigscreenKeyValue(label="累计交通减排", value=4975, unit="kg CO2"),
                    ],
                ),
                hs.HuayiBigscreenListSection(
                    id="new-workshop",
                    title="新生工坊",
                    items=[
                        hs.HuayiBigscreenKeyValue(label="废弃物利用", value=227, unit="件"),
                        hs.HuayiBigscreenKeyValue(label="减排量", value=1622, unit="kg CO2", tone="emerald"),
                        hs.HuayiBigscreenKeyValue(label="展厅节能", value=4906, unit="度"),
                        hs.HuayiBigscreenKeyValue(label="展厅减排量", value=1223, unit="kg CO2"),
                        hs.HuayiBigscreenKeyValue(label="展厅建设减排量", value=719, unit="kg CO2"),
                    ],
                ),
            ],
            alerts=[
                bs.BigscreenAlertItem(id="huayi-alert-1", title="充电桩#3离线", occurred_at="15:30", severity="warning"),
                bs.BigscreenAlertItem(id="huayi-alert-2", title="光伏#2低效运行", occurred_at="14:20", severity="info"),
                bs.BigscreenAlertItem(id="huayi-alert-3", title="储能系统完成夜间充电", occurred_at="09:00", severity="info"),
                bs.BigscreenAlertItem(id="huayi-alert-4", title="办公区负荷接近峰值阈值", occurred_at="08:45", severity="warning"),
                bs.BigscreenAlertItem(id="huayi-alert-5", title="工坊区温湿度传感器恢复在线", occurred_at="08:20", severity="info"),
                bs.BigscreenAlertItem(id="huayi-alert-6", title="停车区充电桩#1充电结束", occurred_at="07:55", severity="info"),
                bs.BigscreenAlertItem(id="huayi-alert-7", title="展厅区照明回路夜间节能模式开启", occurred_at="07:30", severity="info"),
                bs.BigscreenAlertItem(id="huayi-alert-8", title="公共区水泵能耗出现短时波动", occurred_at="07:05", severity="warning"),
                bs.BigscreenAlertItem(id="huayi-alert-9", title="储能逆变器切换至并网模式", occurred_at="06:40", severity="info"),
                bs.BigscreenAlertItem(id="huayi-alert-10", title="光伏阵列#1晨间自检完成", occurred_at="06:15", severity="info"),
            ],
            carbon_trend=[
                bs.BigscreenTrendPoint(period="05.16", energy_kwh=3620, carbon_co2e=1055, value=1055),
                bs.BigscreenTrendPoint(period="05.17", energy_kwh=3840, carbon_co2e=1120, value=1120),
                bs.BigscreenTrendPoint(period="05.18", energy_kwh=3975, carbon_co2e=1184, value=1184),
                bs.BigscreenTrendPoint(period="05.19", energy_kwh=3890, carbon_co2e=1106, value=1106),
                bs.BigscreenTrendPoint(period="05.20", energy_kwh=4120, carbon_co2e=1217, value=1217),
                bs.BigscreenTrendPoint(period="05.21", energy_kwh=4018, carbon_co2e=1169, value=1169),
                bs.BigscreenTrendPoint(period="05.22", energy_kwh=3950, carbon_co2e=1142, value=1142),
            ],
            area_distribution=[
                bs.BigscreenDistributionItem(name="办公区", value=1345),
                bs.BigscreenDistributionItem(name="工坊区", value=1132),
                bs.BigscreenDistributionItem(name="展厅区", value=867),
                bs.BigscreenDistributionItem(name="公共区", value=712),
                bs.BigscreenDistributionItem(name="停车区", value=441),
            ],
            storage_status=hs.HuayiBigscreenKeyValue(label="当前SOC", value=82, unit="%", tone="emerald", detail="额定容量 2.4 MWh / 实时功率 0.82 MW"),
        )
