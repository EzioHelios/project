from __future__ import annotations

from typing import TYPE_CHECKING

from advanced_alchemy.extensions.litestar import repository, service

from app.domain.carbon import models as m
from app.lib.deps import CompositeServiceMixin

if TYPE_CHECKING:
    from uuid import UUID


class EnterpriseInfoService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.EnterpriseInfo]):
    """Handles database operations for EnterpriseInfo."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.EnterpriseInfo]):
        """EnterpriseInfo SQLAlchemy Repository."""
        model_type = m.EnterpriseInfo

    repository_type = Repo


class MonitorSectorService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.MonitorSector]):
    """Handles database operations for MonitorSector."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.MonitorSector]):
        """MonitorSector SQLAlchemy Repository."""
        model_type = m.MonitorSector

    repository_type = Repo


class AreaService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.MonitorSector]):
    """Master-data area service backed by MonitorSector."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.MonitorSector]):
        """Area SQLAlchemy Repository."""

        model_type = m.MonitorSector

    repository_type = Repo


class DeviceTypeService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.DeviceType]):
    """Handles database operations for DeviceType."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.DeviceType]):
        """DeviceType SQLAlchemy Repository."""
        model_type = m.DeviceType

    repository_type = Repo


class EnergyTypeService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.EnergyType]):
    """Handles database operations for EnergyType."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.EnergyType]):
        """EnergyType SQLAlchemy Repository."""
        model_type = m.EnergyType

    repository_type = Repo


class EnergyUnitConversionService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.EnergyUnitConversion]):
    """Handles database operations for EnergyUnitConversion."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.EnergyUnitConversion]):
        """EnergyUnitConversion SQLAlchemy Repository."""

        model_type = m.EnergyUnitConversion

    repository_type = Repo


class EnergyUseSystemService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.EnergyUseSystem]):
    """Handles database operations for EnergyUseSystem."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.EnergyUseSystem]):
        """EnergyUseSystem SQLAlchemy Repository."""

        model_type = m.EnergyUseSystem

    repository_type = Repo


class EnergyUseSystemBindingService(
    CompositeServiceMixin,
    service.SQLAlchemyAsyncRepositoryService[m.EnergyUseSystemBinding],
):
    """Handles database operations for EnergyUseSystemBinding."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.EnergyUseSystemBinding]):
        """EnergyUseSystemBinding SQLAlchemy Repository."""

        model_type = m.EnergyUseSystemBinding

    repository_type = Repo


class EnergyTariffPlanService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.EnergyTariffPlan]):
    """Handles database operations for EnergyTariffPlan."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.EnergyTariffPlan]):
        """EnergyTariffPlan SQLAlchemy Repository."""

        model_type = m.EnergyTariffPlan

    repository_type = Repo


class EnergyTariffSegmentService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.EnergyTariffSegment]):
    """Handles database operations for EnergyTariffSegment."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.EnergyTariffSegment]):
        """EnergyTariffSegment SQLAlchemy Repository."""

        model_type = m.EnergyTariffSegment

    repository_type = Repo


class EnergyIntervalFactService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.EnergyIntervalFact]):
    """Handles database operations for EnergyIntervalFact."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.EnergyIntervalFact]):
        """EnergyIntervalFact SQLAlchemy Repository."""

        model_type = m.EnergyIntervalFact

    repository_type = Repo


class EquipmentWorkloadFactService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.EquipmentWorkloadFact]):
    """Handles database operations for EquipmentWorkloadFact."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.EquipmentWorkloadFact]):
        """EquipmentWorkloadFact SQLAlchemy Repository."""

        model_type = m.EquipmentWorkloadFact

    repository_type = Repo


class MonitorEquipmentService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.MonitorEquipment]):
    """Handles database operations for MonitorEquipment."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.MonitorEquipment]):
        """MonitorEquipment SQLAlchemy Repository."""
        model_type = m.MonitorEquipment

    repository_type = Repo


class DeviceService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.MonitorEquipment]):
    """Master-data device service backed by MonitorEquipment."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.MonitorEquipment]):
        """Device SQLAlchemy Repository."""

        model_type = m.MonitorEquipment

    repository_type = Repo


class DevicePointService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.DevicePoint]):
    """Handles database operations for DevicePoint."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.DevicePoint]):
        """DevicePoint SQLAlchemy Repository."""
        model_type = m.DevicePoint

    repository_type = Repo


class AlarmEventService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.AlarmEvent]):
    """Handles database operations for AlarmEvent."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.AlarmEvent]):
        """AlarmEvent SQLAlchemy Repository."""
        model_type = m.AlarmEvent

    repository_type = Repo


class VideoMonitorService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.VideoMonitor]):
    """Handles database operations for VideoMonitor."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.VideoMonitor]):
        """VideoMonitor SQLAlchemy Repository."""
        model_type = m.VideoMonitor

    repository_type = Repo


class WarningRuleService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.WarningRule]):
    """Handles database operations for WarningRule."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.WarningRule]):
        """WarningRule SQLAlchemy Repository."""
        model_type = m.WarningRule

    repository_type = Repo


class MonitorSectorPhotoService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.MonitorSectorPhoto]):
    """Handles database operations for MonitorSectorPhoto."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.MonitorSectorPhoto]):
        """MonitorSectorPhoto SQLAlchemy Repository."""
        model_type = m.MonitorSectorPhoto

    repository_type = Repo


class ApiResultKeyMappingService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.ApiResultKeyMapping]):
    """Handles database operations for ApiResultKeyMapping."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.ApiResultKeyMapping]):
        """ApiResultKeyMapping SQLAlchemy Repository."""
        model_type = m.ApiResultKeyMapping

    repository_type = Repo


class VedioAlarmEventService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.VedioAlarmEvent]):
    """Handles database operations for VedioAlarmEvent."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.VedioAlarmEvent]):
        """VedioAlarmEvent SQLAlchemy Repository."""
        model_type = m.VedioAlarmEvent

    repository_type = Repo


class EnergyStorageValueService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.EnergyStorageValue]):
    """Handles database operations for EnergyStorageValue."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.EnergyStorageValue]):
        """EnergyStorageValue SQLAlchemy Repository."""
        model_type = m.EnergyStorageValue

    repository_type = Repo


class Scope1MobileCombustionService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.Scope1MobileCombustion]):
    """Handles database operations for Scope1MobileCombustion."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.Scope1MobileCombustion]):
        """Scope1MobileCombustion SQLAlchemy Repository."""
        model_type = m.Scope1MobileCombustion

    repository_type = Repo


class Scope1StationaryCombustionService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.Scope1StationaryCombustion]):
    """Handles database operations for Scope1StationaryCombustion."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.Scope1StationaryCombustion]):
        """Scope1StationaryCombustion SQLAlchemy Repository."""
        model_type = m.Scope1StationaryCombustion

    repository_type = Repo


class Scope1RefrigerantLeakService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.Scope1RefrigerantLeak]):
    """Handles database operations for Scope1RefrigerantLeak."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.Scope1RefrigerantLeak]):
        """Scope1RefrigerantLeak SQLAlchemy Repository."""
        model_type = m.Scope1RefrigerantLeak

    repository_type = Repo


class Scope2ElectricityBillService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.Scope2ElectricityBill]):
    """Handles database operations for Scope2ElectricityBill."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.Scope2ElectricityBill]):
        """Scope2ElectricityBill SQLAlchemy Repository."""
        model_type = m.Scope2ElectricityBill

    repository_type = Repo


class Scope2PurchasedEnergyService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.Scope2PurchasedEnergy]):
    """Handles database operations for Scope2PurchasedEnergy."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.Scope2PurchasedEnergy]):
        """Scope2PurchasedEnergy SQLAlchemy Repository."""
        model_type = m.Scope2PurchasedEnergy

    repository_type = Repo


class Scope2MeterAggregateService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.Scope2MeterAggregate]):
    """Handles database operations for Scope2MeterAggregate."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.Scope2MeterAggregate]):
        """Scope2MeterAggregate SQLAlchemy Repository."""
        model_type = m.Scope2MeterAggregate

    repository_type = Repo


class Scope3WasteDisposalService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.Scope3WasteDisposal]):
    """Handles database operations for Scope3WasteDisposal."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.Scope3WasteDisposal]):
        """Scope3WasteDisposal SQLAlchemy Repository."""
        model_type = m.Scope3WasteDisposal

    repository_type = Repo


class Scope3ThirdPartyTransportService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.Scope3ThirdPartyTransport]):
    """Handles database operations for Scope3ThirdPartyTransport."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.Scope3ThirdPartyTransport]):
        """Scope3ThirdPartyTransport SQLAlchemy Repository."""
        model_type = m.Scope3ThirdPartyTransport

    repository_type = Repo


class EmissionFactorService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.EmissionFactor]):
    """Handles database operations for EmissionFactor."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.EmissionFactor]):
        """EmissionFactor SQLAlchemy Repository."""
        model_type = m.EmissionFactor

    repository_type = Repo


class CarbonFactorImportBatchService(
    CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.CarbonFactorImportBatch]
):
    """Handles database operations for CarbonFactorImportBatch."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.CarbonFactorImportBatch]):
        """CarbonFactorImportBatch SQLAlchemy Repository."""
        model_type = m.CarbonFactorImportBatch

    repository_type = Repo


class CarbonFactorLibraryService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.CarbonFactorLibrary]):
    """Handles database operations for CarbonFactorLibrary."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.CarbonFactorLibrary]):
        """CarbonFactorLibrary SQLAlchemy Repository."""
        model_type = m.CarbonFactorLibrary

    repository_type = Repo


class CarbonFactorCategoryService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.CarbonFactorCategory]):
    """Handles database operations for CarbonFactorCategory."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.CarbonFactorCategory]):
        """CarbonFactorCategory SQLAlchemy Repository."""
        model_type = m.CarbonFactorCategory

    repository_type = Repo


class CarbonFactorRawRecordService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.CarbonFactorRawRecord]):
    """Handles database operations for CarbonFactorRawRecord."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.CarbonFactorRawRecord]):
        """CarbonFactorRawRecord SQLAlchemy Repository."""
        model_type = m.CarbonFactorRawRecord

    repository_type = Repo


class CarbonAuditLogService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.CarbonAuditLog]):
    """Handles database operations for CarbonAuditLog."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.CarbonAuditLog]):
        """CarbonAuditLog SQLAlchemy Repository."""
        model_type = m.CarbonAuditLog

    repository_type = Repo


class EmployeeCommuteService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.EmployeeCommute]):
    """Handles database operations for EmployeeCommute."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.EmployeeCommute]):
        """EmployeeCommute SQLAlchemy Repository."""
        model_type = m.EmployeeCommute

    repository_type = Repo


class InMoneyService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.InMoney]):
    """Handles database operations for InMoney."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.InMoney]):
        """InMoney SQLAlchemy Repository."""
        model_type = m.InMoney

    repository_type = Repo


class OutMoneyService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.OutMoney]):
    """Handles database operations for OutMoney."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.OutMoney]):
        """OutMoney SQLAlchemy Repository."""
        model_type = m.OutMoney

    repository_type = Repo


class ProductionProductService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.ProductionProduct]):
    """Handles database operations for ProductionProduct."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.ProductionProduct]):
        """ProductionProduct SQLAlchemy Repository."""

        model_type = m.ProductionProduct

    repository_type = Repo


class ProductPriceService(CompositeServiceMixin, service.SQLAlchemyAsyncRepositoryService[m.ProductPrice]):
    """Handles database operations for ProductPrice."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.ProductPrice]):
        """ProductPrice SQLAlchemy Repository."""

        model_type = m.ProductPrice

    repository_type = Repo


class ProductionOutputFactService(
    CompositeServiceMixin,
    service.SQLAlchemyAsyncRepositoryService[m.ProductionOutputFact],
):
    """Handles database operations for ProductionOutputFact."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.ProductionOutputFact]):
        """ProductionOutputFact SQLAlchemy Repository."""

        model_type = m.ProductionOutputFact

    repository_type = Repo


class ProductionResourceBindingService(
    CompositeServiceMixin,
    service.SQLAlchemyAsyncRepositoryService[m.ProductionResourceBinding],
):
    """Handles database operations for ProductionResourceBinding."""

    class Repo(repository.SQLAlchemyAsyncRepository[m.ProductionResourceBinding]):
        """ProductionResourceBinding SQLAlchemy Repository."""

        model_type = m.ProductionResourceBinding

    repository_type = Repo
