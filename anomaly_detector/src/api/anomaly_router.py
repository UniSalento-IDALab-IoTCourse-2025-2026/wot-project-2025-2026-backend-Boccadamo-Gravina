from fastapi import APIRouter, Depends, HTTPException, Request, status

from security.auth import CurrentUser, require_admin
from services.anomaly_service import AnomalyDetectionService

router = APIRouter(prefix="/anomalies", tags=["Anomaly Detection"])


def get_anomaly_service(request: Request) -> AnomalyDetectionService:
    return request.app.state.anomaly_service


@router.delete("/{device_id}/memory")
def reset_device_memory(
    device_id: str,
    admin: CurrentUser = Depends(require_admin),
    service: AnomalyDetectionService = Depends(get_anomaly_service),
):
    removed = service.reset_device_memory(device_id)
    if removed == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nessuna memoria trovata per il dispositivo '{device_id}'",
        )
    return {
        "status": "ok",
        "device_id": device_id,
        "removed_keys": removed,
    }
