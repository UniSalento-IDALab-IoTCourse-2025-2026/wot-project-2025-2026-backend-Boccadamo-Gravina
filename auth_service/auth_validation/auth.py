import os
from dataclasses import dataclass, field
import logging
import jwt
from jwt import PyJWKClient

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
REQUIRED_CLAIMS = ["exp", "iss", "aud", "sub"]

logger = logging.getLogger("auth")
_jwks_client = PyJWKClient(JWKS_URL, timeout=5)

def validate_token(token: str) -> dict:
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=ALGORITHMS,
            audience=AUDIENCE,
            issuer=ISSUER,
            leeway=LEEWAY_SECONDS,
            options={"require": REQUIRED_CLAIMS},
        )
    except jwt.PyJWKClientConnectionError as exc:
        logger.error("JWKS non raggiungibile: %s", type(exc).__name__)
        raise AuthServiceUnavailable() from exc
    except jwt.PyJWTError as exc:
        logger.info("Token rifiutato: %s", type(exc).__name__)
        raise InvalidToken() from exc
