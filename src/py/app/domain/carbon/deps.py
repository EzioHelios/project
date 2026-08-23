"""Carbon domain dependencies."""

from __future__ import annotations

from app.domain.carbon import services
from app.lib.deps import create_service_provider

provide_enterprise_info_service = create_service_provider(services.EnterpriseInfoService)
provide_monitor_sector_service = create_service_provider(services.MonitorSectorService)
provide_area_service = create_service_provider(services.AreaService)
provide_device_type_service = create_service_provider(services.DeviceTypeService)
provide_energy_type_service = create_service_provider(services.EnergyTypeService)
provide_energy_unit_conversion_service = create_service_provider(services.EnergyUnitConversionService)
provide_energy_use_system_service = create_service_provider(services.EnergyUseSystemService)
provide_energy_use_system_binding_service = create_service_provider(services.EnergyUseSystemBindingService)
provide_energy_tariff_plan_service = create_service_provider(services.EnergyTariffPlanService)
provide_energy_tariff_segment_service = create_service_provider(services.EnergyTariffSegmentService)
provide_energy_interval_fact_service = create_service_provider(services.EnergyIntervalFactService)
provide_equipment_workload_fact_service = create_service_provider(services.EquipmentWorkloadFactService)
provide_monitor_equipment_service = create_service_provider(services.MonitorEquipmentService)
provide_device_service = create_service_provider(services.DeviceService)
provide_device_point_service = create_service_provider(services.DevicePointService)
provide_alarm_event_service = create_service_provider(services.AlarmEventService)
provide_video_monitor_service = create_service_provider(services.VideoMonitorService)
provide_warning_rule_service = create_service_provider(services.WarningRuleService)
provide_monitor_sector_photo_service = create_service_provider(services.MonitorSectorPhotoService)
provide_api_result_key_mapping_service = create_service_provider(services.ApiResultKeyMappingService)
provide_vedio_alarm_event_service = create_service_provider(services.VedioAlarmEventService)
provide_energy_storage_value_service = create_service_provider(services.EnergyStorageValueService)
provide_scope2_meter_aggregate_service = create_service_provider(services.Scope2MeterAggregateService)
provide_emission_factor_service = create_service_provider(services.EmissionFactorService)
provide_carbon_factor_import_batch_service = create_service_provider(services.CarbonFactorImportBatchService)
provide_carbon_factor_library_service = create_service_provider(services.CarbonFactorLibraryService)
provide_carbon_factor_category_service = create_service_provider(services.CarbonFactorCategoryService)
provide_carbon_factor_raw_record_service = create_service_provider(services.CarbonFactorRawRecordService)
provide_employee_commute_service = create_service_provider(services.EmployeeCommuteService)
provide_in_money_service = create_service_provider(services.InMoneyService)
provide_out_money_service = create_service_provider(services.OutMoneyService)
provide_production_product_service = create_service_provider(services.ProductionProductService)
provide_product_price_service = create_service_provider(services.ProductPriceService)
provide_production_output_fact_service = create_service_provider(services.ProductionOutputFactService)
provide_production_resource_binding_service = create_service_provider(services.ProductionResourceBindingService)

__all__ = (
    "provide_alarm_event_service",
    "provide_api_result_key_mapping_service",
    "provide_area_service",
    "provide_carbon_factor_category_service",
    "provide_carbon_factor_import_batch_service",
    "provide_carbon_factor_library_service",
    "provide_carbon_factor_raw_record_service",
    "provide_device_point_service",
    "provide_device_service",
    "provide_device_type_service",
    "provide_emission_factor_service",
    "provide_employee_commute_service",
    "provide_energy_interval_fact_service",
    "provide_energy_storage_value_service",
    "provide_energy_tariff_plan_service",
    "provide_energy_tariff_segment_service",
    "provide_energy_type_service",
    "provide_energy_unit_conversion_service",
    "provide_energy_use_system_binding_service",
    "provide_energy_use_system_service",
    "provide_enterprise_info_service",
    "provide_equipment_workload_fact_service",
    "provide_in_money_service",
    "provide_monitor_equipment_service",
    "provide_monitor_sector_photo_service",
    "provide_monitor_sector_service",
    "provide_out_money_service",
    "provide_product_price_service",
    "provide_production_output_fact_service",
    "provide_production_product_service",
    "provide_production_resource_binding_service",
    "provide_scope2_meter_aggregate_service",
    "provide_vedio_alarm_event_service",
    "provide_video_monitor_service",
    "provide_warning_rule_service",
)
