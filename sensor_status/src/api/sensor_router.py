from fastapi import APIRouter, Depends, HTTPException, Request, status

from security.auth import CurrentUser, require_admin
from services.sensor_service import SensorService
from dto.sensor_dto import (
    SensorStatusDTO,
    SensorsOverviewDTO,
    SensorLocationUpdateDTO,
    SensorLocationResponseDTO,
)

router = APIRouter(prefix="/sensors", tags=["Sensors Status"])


def get_sensor_service(request: Request) -> SensorService:
    service: SensorService | None = getattr(request.app.state, "sensor_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servizio sensori non inizializzato",
        )
    return service


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


@router.put("/{device_id}/location", response_model=SensorLocationResponseDTO)
def upsert_sensor_location(
    device_id: str,
    body: SensorLocationUpdateDTO,
    admin: CurrentUser = Depends(require_admin),
    service: SensorService = Depends(get_sensor_service),
):
    try:
        return service.update_location(device_id=device_id, lat=body.lat, lon=body.lon)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc