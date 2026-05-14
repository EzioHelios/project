"""Carbon domain dependencies."""

from __future__ import annotations

from . import services
from app.lib.deps import create_service_provider

provide_enterprise_info_service = create_service_provider(services.EnterpriseInfoService)
provide_monitor_sector_service = create_service_provider(services.MonitorSectorService)
provide_monitor_equipment_service = create_service_provider(services.MonitorEquipmentService)
provide_ammeter_index_value_service = create_service_provider(services.AmmeterIndexValueService)
provide_alarm_event_service = create_service_provider(services.AlarmEventService)
provide_video_monitor_service = create_service_provider(services.VideoMonitorService)
provide_warning_rule_service = create_service_provider(services.WarningRuleService)
provide_monitor_sector_photo_service = create_service_provider(services.MonitorSectorPhotoService)
provide_api_result_key_mapping_service = create_service_provider(services.ApiResultKeyMappingService)
provide_vedio_alarm_event_service = create_service_provider(services.VedioAlarmEventService)
provide_energy_storage_value_service = create_service_provider(services.EnergyStorageValueService)
provide_scope1_mobile_combustion_service = create_service_provider(services.Scope1MobileCombustionService)
provide_scope1_stationary_combustion_service = create_service_provider(services.Scope1StationaryCombustionService)
provide_scope1_refrigerant_leak_service = create_service_provider(services.Scope1RefrigerantLeakService)
provide_scope2_electricity_bill_service = create_service_provider(services.Scope2ElectricityBillService)
provide_scope2_meter_aggregate_service = create_service_provider(services.Scope2MeterAggregateService)
provide_scope3_waste_disposal_service = create_service_provider(services.Scope3WasteDisposalService)
provide_scope3_third_party_transport_service = create_service_provider(services.Scope3ThirdPartyTransportService)
provide_emission_factor_service = create_service_provider(services.EmissionFactorService)
provide_carbon_factor_import_batch_service = create_service_provider(services.CarbonFactorImportBatchService)
provide_carbon_factor_library_service = create_service_provider(services.CarbonFactorLibraryService)
provide_carbon_factor_category_service = create_service_provider(services.CarbonFactorCategoryService)
provide_carbon_factor_raw_record_service = create_service_provider(services.CarbonFactorRawRecordService)
provide_iot_telemetry_service = create_service_provider(services.IotTelemetryService)
provide_carbon_audit_log_service = create_service_provider(services.CarbonAuditLogService)
provide_employee_commute_service = create_service_provider(services.EmployeeCommuteService)
provide_in_money_service = create_service_provider(services.InMoneyService)
provide_out_money_service = create_service_provider(services.OutMoneyService)

__all__ = (
    "provide_alarm_event_service",
    "provide_ammeter_index_value_service",
    "provide_api_result_key_mapping_service",
    "provide_carbon_audit_log_service",
    "provide_carbon_factor_category_service",
    "provide_carbon_factor_import_batch_service",
    "provide_carbon_factor_library_service",
    "provide_carbon_factor_raw_record_service",
    "provide_emission_factor_service",
    "provide_employee_commute_service",
    "provide_energy_storage_value_service",
    "provide_enterprise_info_service",
    "provide_in_money_service",
    "provide_iot_telemetry_service",
    "provide_monitor_equipment_service",
    "provide_monitor_sector_photo_service",
    "provide_monitor_sector_service",
    "provide_out_money_service",
    "provide_scope1_mobile_combustion_service",
    "provide_scope1_refrigerant_leak_service",
    "provide_scope1_stationary_combustion_service",
    "provide_scope2_electricity_bill_service",
    "provide_scope2_meter_aggregate_service",
    "provide_scope3_third_party_transport_service",
    "provide_scope3_waste_disposal_service",
    "provide_vedio_alarm_event_service",
    "provide_video_monitor_service",
    "provide_warning_rule_service",
)
