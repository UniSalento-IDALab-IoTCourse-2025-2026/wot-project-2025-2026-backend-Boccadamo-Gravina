from dataclasses import dataclass, field
import jwt
from jwt import PyJWKClient, PyJWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import config


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
JWKS_URL = config.OIDC_JWKS_URL

# Indirizzo dell'issuer, che deve coincidere con il campo "iss" del JWT
ISSUER = config.OIDC_ISSUER

# Destinatario atteso. Ricordarsi di creare un client con questo audience
# per ogni servizio da proteggere con l'autenticazione OIDC
AUDIENCE = config.OIDC_AUDIENCE

ALGORITHMS = ["RS256"]

# Tolleranza sul controllo scadenza token
LEEWAY_SECONDS = 10

# Claims che devono essere presenti nel JWT, altrimenti il JWT non è valido
# REQUIRED_CLAIMS = ["exp", "iss", "aud", "sub"]
REQUIRED_CLAIMS = ["exp", "iss", "sub"]

security_scheme = HTTPBearer()
jwks_client = PyJWKClient(JWKS_URL)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
) -> CurrentUser:
    token = credentials.credentials
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=ALGORITHMS,
            issuer=ISSUER,
            # audience=AUDIENCE,
            leeway=LEEWAY_SECONDS,
            options={"verify_aud": False, "require": REQUIRED_CLAIMS},
        )
    except jwt.PyJWKClientError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Keycloak non raggiungibile",
        ) from e
    except PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token non valido: {str(e)}",
        ) from e

    roles = frozenset(payload.get("realm_access", {}).get("roles", []))
    return CurrentUser(
        id=payload["sub"],
        username=payload.get("preferred_username"),
        email=payload.get("email"),
        roles=roles,
        claims=payload,
    )


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.has_role("admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accesso riservato agli amministratori",
        )
    return user