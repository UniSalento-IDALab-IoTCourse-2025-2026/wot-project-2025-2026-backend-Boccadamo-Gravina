from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from security.auth import CurrentUser, require_admin, require_citizen
from storage.repository import DataRepository

router = APIRouter(prefix="/data", tags=["Data"])

# request è un oggetto che FastAPI passa automaticamente a ogni richiesta che viene ricevuta dal servizio,
# e contiene informazioni sulla richiesta stessa, tra cui header e app.state
# request.app.state è un oggetto condiviso dove main.py deposita le istanze create all'avvio,
# come il repository e il DataService, così che possano essere riutilizzate da altri moduli senza doverle ricreare ogni volta.
def get_repository(request: Request) -> DataRepository:

    # repository potrà essere solo di tipo DataRepository oppure None
    repository: DataRepository | None = getattr(request.app.state, "repository", None)
    if repository is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Repository non inizializzato",
        )
    return repository

# La dependency da require_citizen nei metodi sotto, fà in modo da eseguire automaticamente
# la require_citizen che dipende (e quindi chiama) la current_user (che poi al suo interno chiama la validate_token)
# dall'auth.py, e qua dentro ci prendiamo il valore di ritorno che ci ha dato questa catena di chiamate.

@router.get("/measurements")
def get_latest_measurements(
    limit: int = Query(default=100, ge=1, le=1000),
    user: CurrentUser = Depends(require_citizen),
    repository: DataRepository = Depends(get_repository),
):
    return repository.get_latest_measurements(limit=limit)

@router.get("/measurements/{device_id}")
def get_measurements_by_device(
    device_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
    user: CurrentUser = Depends(require_citizen),
    repository: DataRepository = Depends(get_repository),
):
    results = repository.get_measurements_by_device(device_id=device_id, limit=limit)
    if not results:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nessuna misurazione trovata per il sensore '{device_id}'",
        )
    return results
