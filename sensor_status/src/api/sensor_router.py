from fastapi import APIRouter, Depends, HTTPException, status

from security.auth import CurrentUser, require_admin
from storage.sensor_repository import SensorRepository
from services.sensor_service import SensorService
from dto.sensor_dto import SensorStatusDTO, SensorsOverviewDTO

router = APIRouter(prefix="/sensors", tags=["Sensors Status"])


# Dependency Injection (equivalente di @Autowired in Spring)
def get_sensor_service() -> SensorService:
    return SensorService(SensorRepository())


@router.get("/status", response_model=SensorsOverviewDTO)
def get_all_sensors_status(
    admin: CurrentUser = Depends(require_admin),
    service: SensorService = Depends(get_sensor_service),
):
    return service.get_overview()


@router.get("/{device_id}/status", response_model=SensorStatusDTO)
def get_sensor_status(
    device_id: str,
    admin: CurrentUser = Depends(require_admin),
    service: SensorService = Depends(get_sensor_service),
):
    result = service.get_sensor_by_id(device_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sensore '{device_id}' non trovato",
        )
    return result