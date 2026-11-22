import os
from dataclasses import dataclass, field
import logging
import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Manca la variabile d'ambiente {name}")
    return value

# Eccezioni custom
class AuthError(Exception):
    pass

class InvalidToken(AuthError):
    pass

class AuthServiceUnavailable(AuthError):
    pass

# L'oggetto di tipo CurrentUser è quello che gli endpoint che richiedono auth
# riceveranno dopo una validazione riuscita del JWT
@dataclass(frozen=True)
class CurrentUser:
    id: str
    username: str | None
    email: str | None
    roles: frozenset[str]
    claims: dict = field(repr=False)

    def has_role(self, role: str) -> bool:
        return role in self.roles

# Indirizzo da cui scaricare le public keys
JWKS_URL = _required_env("OIDC_JWKS_URL")

# Indirizzo dell'issuer, che deve coincidere con il campo "iss" del JWT
ISSUER = _required_env("OIDC_ISSUER").rstrip("/")

# Destinatario atteso. Ricordarsi di creare un client con questo audience
# per ogni servizio da proteggere con l'autenticazione OIDC
AUDIENCE = _required_env("OIDC_AUDIENCE")

ALGORITHMS = ["RS256"]

# Tolleranza sul controllo scadenza token
LEEWAY_SECONDS = 10

# Claims che devono essere presenti nel JWT, altrimenti il JWT non è valido
REQUIRED_CLAIMS = ["exp", "iss", "sub"]

logger = logging.getLogger("auth")
_jwks_client = PyJWKClient(JWKS_URL, timeout=5)

def validate_token(token: str) -> dict:
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)

        # Questo è il payload del JWT
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=ALGORITHMS,
            # audience=AUDIENCE,
            issuer=ISSUER,
            leeway=LEEWAY_SECONDS,
            options={"require": REQUIRED_CLAIMS, "verify_aud": False},
        )
    except jwt.PyJWKClientConnectionError as exc:
        logger.error("JWKS non raggiungibile: %s", type(exc).__name__)
        raise AuthServiceUnavailable() from exc
    except jwt.PyJWTError as exc:
        logger.info("Token rifiutato: %s", type(exc).__name__)
        raise InvalidToken() from exc

def build_user(claims: dict) -> CurrentUser:
    realm_access = claims.get("realm_access") or {}
    roles = realm_access.get("roles") or []
    return CurrentUser(
        id=claims["sub"],
        username=claims.get("preferred_username"),
        email=claims.get("email"),
        roles=frozenset(roles),
        claims=claims,
    )

# Consente a FastAPI di estrarre autonomamente il token che arriva
# da una richiesta, tramite l'header Authorization
# Il JWT è a tutti gli effetti il valore della riga Authorization,
# che poi è l'header della richiesta HTTP che FastAPI riceve
_bearer = HTTPBearer(auto_error=False)

def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token non valido o mancante",
        headers={"WWW-Authenticate": "Bearer"},
    )

# Verifica token e credenziali
def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    if credentials is None:
        raise _unauthorized()
    try:
        claims = validate_token(credentials.credentials)
    except InvalidToken:
        raise _unauthorized()
    except AuthServiceUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servizio di autenticazione non disponibile",
        )
    return build_user(claims)

# Funzione che genera un checker per il ruolo specifico passato
def require_role(role: str):
    def checker(user: CurrentUser = Depends(current_user)) -> CurrentUser:
        if not user.has_role(role):
            logger.info("Accesso negato: utente=%s ruolo_richiesto=%s", user.id, role)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permesso negato",
            )
        return user
    return checker

# Scorciatoie per ruoli
require_admin = require_role("admin")
require_citizen = require_role("citizen")
